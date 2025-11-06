#!/usr/bin/env python3

#################################################################################
#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.          #
#   Copyright AWS DeepRacer Community. All Rights Reserved.                     #
#                                                                               #
#   Licensed under the Apache License, Version 2.0 (the "License").             #
#   You may not use this file except in compliance with the License.            #
#   You may obtain a copy of the License at                                     #
#                                                                               #
#       http://www.apache.org/licenses/LICENSE-2.0                              #
#                                                                               #
#   Unless required by applicable law or agreed to in writing, software         #
#   distributed under the License is distributed on an "AS IS" BASIS,           #
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.    #
#   See the License for the specific language governing permissions and         #
#   limitations under the License.                                              #
#################################################################################

import logging
import importlib
import sys
import time
import os
from threading import Event, Lock
from typing import List, Tuple
import traceback

import rclpy
from rclpy.node import Node, Subscription, TopicEndpointInfo, QoSProfile
from rclpy.qos import HistoryPolicy
from rclpy.time import Duration
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup, MutuallyExclusiveCallbackGroup
from rclpy.logging import LoggingSeverity

import rosbag2_py
from rcl_interfaces.msg import ParameterDescriptor, ParameterType

from std_msgs.msg import String
from std_srvs.srv import Trigger

from deepracer_interfaces_pkg.srv import USBFileSystemSubscribeSrv, USBMountPointManagerSrv
from deepracer_interfaces_pkg.msg import USBFileSystemNotificationMsg

import bag_log_pkg.constants as constants
from bag_log_pkg.constants import RecordingState, NodeState, LoggingMode


class BagLogNode(Node):
    """
    This node is used to log a topic to a rosbag2.

    The `BagLogNode` class is responsible for logging a specified topic to a rosbag2 file.
    It provides functionality to monitor changes in the topic, start and stop the recording,
    and handle USB file system notifications.

    Attributes:
        _shutdown (Event): An event to signal the shutdown of the node.
        _target_edit_state (RecordingState): The target state of the recording (Running or Stopped).
        _state (NodeState): The current state of the node (Starting, Scanning, or Running).
        _topic_subscriptions (List[Subscription]): A list of topic subscriptions.
        _topics_type_info (List[Tuple[str, TopicEndpointInfo]]): A list of topic names and their type information.
        _topics_to_scan (List[str]): A list of topics to scan for.
        _bag_lock (Lock): A lock to ensure thread safety when accessing the rosbag2 file.

    """
    _shutdown = Event()
    _target_edit_state = RecordingState.Stopped
    _state = NodeState.Starting

    _topic_subscriptions: List[Subscription] = []
    _topics_type_info: List[Tuple[str, TopicEndpointInfo]] = []
    _topics_to_scan: List[str] = []
    _bag_lock = Lock()
    _bag_writer = None
    _topic_counter = 0
    _pause_until = time.time()

    _usb_path = False

    def __init__(self):
        """
        Initializes the BagLogNode.

        This constructor initializes the BagLogNode by declaring and retrieving several parameters
        related to logging configuration, such as output path, USB monitor settings, logging mode,
        monitor topic, file name topic, monitor topic timeout, and log topics. It also sets up
        internal variables based on these parameters.

        Parameters:
        - output_path (str): The path where logs will be stored. Default is defined in constants.LOGS_DEFAULT_FOLDER.
        - disable_usb_monitor (bool): Flag to disable USB monitoring. Default is False.
        - logging_mode (str): The mode of logging. Default is "Always".
        - monitor_topic (str): The topic to monitor for inference results. Default is '/inference_pkg/rl_results'.
        - file_name_topic (str): The topic to monitor for file names. Default is '/inference_pkg/model_name'.
        - monitor_topic_timeout (int): The timeout duration for the monitor topic in seconds. Default is 1.
        - log_topics (list of str): The list of topics to log. Default is ['/ctrl_pkg/servo_msg'].
        - logging_provier (str): The logging provider to use. Default is 'sqlite3'.

        Sets:
        - self._output_path (str): The resolved output path for logs.
        - self._disable_usb_monitor (bool): The resolved flag for USB monitoring.
        - self._logging_mode (LoggingMode): The resolved logging mode.
        - self._monitor_topic (str): The resolved monitor topic.
        - self._file_name_topic (str): The resolved file name topic.
        - self._monitor_topic_timeout (int): The resolved monitor topic timeout.
        - self._monitor_timeout_duration (Duration): The duration object for monitor topic timeout.
        - self._monitor_last_received (Time): The timestamp of the last received monitor message.
        - self._log_topics (list of str): The resolved list of topics to log.
        - self._logging_provider (str): The resolved logging provider.
        - self._topics_to_scan (list of str): The list of topics to scan, excluding the monitor topic.
        - self._bag_name (str): The default bag name defined in constants.
        """
        super().__init__('bag_log_node')

        self.declare_parameter(
            'output_path', constants.LOGS_DEFAULT_FOLDER,
            ParameterDescriptor(type=ParameterType.PARAMETER_STRING))
        self._output_path = self.get_parameter('output_path').value

        self.declare_parameter(
            'disable_usb_monitor', False,
            ParameterDescriptor(type=ParameterType.PARAMETER_BOOL))
        self._disable_usb_monitor = self.get_parameter('disable_usb_monitor').value

        self.declare_parameter(
            'logging_mode', "Always",
            ParameterDescriptor(type=ParameterType.PARAMETER_STRING))
        self._logging_mode = LoggingMode(self.get_parameter('logging_mode').value)

        self.declare_parameter(
            'monitor_topic', '/inference_pkg/rl_results',
            ParameterDescriptor(type=ParameterType.PARAMETER_STRING))
        self._monitor_topic = self.get_parameter('monitor_topic').value

        self.declare_parameter(
            'file_name_topic', '/inference_pkg/model_name',
            ParameterDescriptor(type=ParameterType.PARAMETER_STRING))
        self._file_name_topic = self.get_parameter('file_name_topic').value

        self.declare_parameter(
            'monitor_topic_timeout', 15,
            ParameterDescriptor(type=ParameterType.PARAMETER_INTEGER))
        self._monitor_topic_timeout = self.get_parameter('monitor_topic_timeout').value
        self._monitor_timeout_duration = Duration(seconds=self._monitor_topic_timeout)
        self._monitor_last_received = self.get_clock().now()

        self.declare_parameter(
            'log_topics', ['/ctrl_pkg/servo_msg'],
            ParameterDescriptor(type=ParameterType.PARAMETER_STRING_ARRAY))
        self._log_topics = self.get_parameter('log_topics').value

        self.declare_parameter(
            'logging_provider', 'sqlite3',
            ParameterDescriptor(type=ParameterType.PARAMETER_STRING))
        self._logging_provider = self.get_parameter('logging_provider').value

        self._topics_to_scan += self._log_topics
        if self._topics_to_scan.count(self._monitor_topic) > 0:
            self._topics_to_scan.remove(self._monitor_topic)

        self._bag_name = constants.DEFAULT_BAG_NAME

    def __enter__(self):
        """
        Enter the runtime context related to this object.

        This method sets up various subscriptions, clients, and timers required for the node's operation.
        It subscribes to the monitor topic, starts scanning if the logging mode is set to 'Always', and 
        sets up a guard condition to monitor changes. It also creates a subscription to the file name topic.

        If USB monitoring is not disabled, it sets up clients and subscriptions related to USB file system 
        monitoring and mount point management. It waits for these services to become available and subscribes 
        to notifications for USB file system changes. Additionally, it adds the "models" folder to the USB 
        file system watchlist.

        Returns:
            self: The instance of the class.
        """

        # Subscription to monitor topic.
        self._main_cbg = ReentrantCallbackGroup()
        self._st_cbg = MutuallyExclusiveCallbackGroup()

        # Start the scan
        if self._logging_mode == LoggingMode.Always:
            self._state = NodeState.Scanning
            self._scan_timer = self.create_timer(1.0, callback=self._scan_for_topics_cb,
                                                 callback_group=self._main_cbg)

        # Monitor changes
        self._change_gc = self.create_guard_condition(callback=self._change_cb,
                                                      callback_group=self._st_cbg)

        self.get_logger().info('Node started. Mode \'{}\'. Provider \'{}\'. Monitor \'{}\'. Additionally logging {}.'
                               .format(self._logging_mode.name, self._logging_provider, self._monitor_topic, str(self._topics_to_scan)))

        # Create a subscription to the file name topic
        self._file_name_sub = self.create_subscription(String, self._file_name_topic,
                                                       self._file_name_cb, 1)

        self._stop_logging_svc = self.create_service(Trigger, 'stop_logging',
                                                     self._stop_logging_cb, callback_group=self._main_cbg)

        if not self._disable_usb_monitor:
            # Client to USB File system subscription service that allows the node to add the "models"
            # folder to the watchlist. The usb_monitor_node will trigger notification if it finds
            # the files/folders from the watchlist in the USB drive.
            self._usb_sub_cb_group = ReentrantCallbackGroup()
            self._usb_file_system_subscribe_client = self.create_client(
                USBFileSystemSubscribeSrv, constants.USB_FILE_SYSTEM_SUBSCRIBE_SERVICE_NAME,
                callback_group=self._usb_sub_cb_group)
            while not self._usb_file_system_subscribe_client.wait_for_service(timeout_sec=1.0):
                self.get_logger().info("File System Subscribe not available, waiting again...")

            # Client to USB Mount point manager service to indicate that the usb_monitor_node can safely
            # decrement the counter for the mount point once the action function for the file/folder being
            # watched by model_loader_node is succesfully executed.
            self._usb_mpm_cb_group = ReentrantCallbackGroup()
            self._usb_mount_point_manager_client = self.create_client(USBMountPointManagerSrv,
                                                                      constants.USB_MOUNT_POINT_MANAGER_SERVICE_NAME,
                                                                      callback_group=self._usb_mpm_cb_group)
            while not self._usb_mount_point_manager_client.wait_for_service(timeout_sec=1.0):
                self.get_logger().info("USB mount point manager service not available, waiting again...")

            # Subscriber to USB File system notification publisher to recieve the broadcasted messages
            # with file/folder details, whenever a watched file is identified in the USB connected.
            self._usb_notif_cb_group = ReentrantCallbackGroup()
            self._usb_file_system_notification_sub = self.create_subscription(
                USBFileSystemNotificationMsg, constants.USB_FILE_SYSTEM_NOTIFICATION_TOPIC, self.
                _usb_file_system_notification_cb, 10, callback_group=self._usb_notif_cb_group)

            # Add the "models" folder to the watchlist.
            usb_file_system_subscribe_request = USBFileSystemSubscribeSrv.Request()
            usb_file_system_subscribe_request.file_name = constants.LOGS_SOURCE_LEAF_DIRECTORY
            usb_file_system_subscribe_request.callback_name = constants.LOGS_DIR_CB
            usb_file_system_subscribe_request.verify_name_exists = True
            self._usb_file_system_subscribe_client.call_async(usb_file_system_subscribe_request)

        return self

    def __exit__(self, ExcType, ExcValue, Traceback):
        """
        Method to handle the cleanup and shutdown process when exiting the context.

        Args:
            ExcType (type): The exception type that caused the context to exit.
            ExcValue (Exception): The exception instance that caused the context to exit.
            Traceback (traceback): The traceback object associated with the exception.

        The method performs the following actions:
        - Logs the reason for stopping the node.
        - Stops the bag recording if it is running.
        - Sets the shutdown event.
        - Destroys the change_gc object.
        - Destroys the timeout check timer if it exists.
        - Destroys all topic subscriptions.

        In case of an exception during the cleanup process, logs the stack trace.
        Finally, logs that the node cleanup is done and the context is exiting.
        """

        self.get_logger().info('Stopping the node due to {}.'.format(ExcType.__name__))

        try:
            if self._target_edit_state == RecordingState.Running:
                self._stop_bag()

            self._shutdown.set()
            self._change_gc.destroy()

            if hasattr(self, '_timeout_check_timer'):
                self._timeout_check_timer.destroy()

            for sub in self._topic_subscriptions:
                sub.destroy()

        except:  # noqa E722
            self.get_logger().error(traceback.format_stack())
        finally:
            self.get_logger().info('Node cleanup done. Exiting.')

    def _file_name_cb(self, filename_msg: String):
        """
        Callback function to handle the reception of a new filename message.

        This function is triggered when a new filename message is received. If the 
        current recording state is 'Running', it stops the recording and triggers 
        a garbage collection change. It then extracts the bag name from the 
        received filename message and logs the new filename and bag name.

        Args:
            filename_msg (String): The message containing the new filename.

        Raises:
            Logs an error message if an exception occurs during the process.
        """
        try:
            if self._target_edit_state == RecordingState.Running:
                self._target_edit_state = RecordingState.Stopped
                self._change_gc.trigger()
                self.get_logger().info("Received new file name. Triggering stop of recording.")

            parts = filename_msg.data.split(os.sep)
            self._bag_name = parts[-2]
            self.get_logger().info(f"New filename received: {filename_msg.data} -> {self._bag_name}")

        except:  # noqa E722
            self.get_logger().error(traceback.format_stack())

    def _usb_file_system_notification_cb(self, notification_msg):
        """
        Callback for messages triggered whenever usb_monitor_node identifies a file/folder
        thats being tracked.

        Args:
            notification_msg (USBFileSystemNotificationMsg): Message containing information about the
                                                             file identified by the usb_monitor_node.
        """
        self.get_logger().info("File system notification:"
                               f" {notification_msg.path}"
                               f" {notification_msg.file_name}"
                               f" {notification_msg.node_name}"
                               f" {notification_msg.callback_name}")
        if notification_msg.file_name == constants.LOGS_SOURCE_LEAF_DIRECTORY and \
           notification_msg.callback_name == constants.LOGS_DIR_CB:
            self._output_path = os.path.join(notification_msg.path, notification_msg.file_name)
            self.set_parameters([rclpy.parameter.Parameter('output_path', rclpy.Parameter.Type.STRING, self._output_path)])
            self.get_logger().info(f"New output path: {self._output_path}")

        if self._logging_mode == LoggingMode.USBOnly and self._state == NodeState.Starting:
            self.get_logger().info("USB folder mounted, starting scanning for topics.")
            self._state = NodeState.Scanning
            self._scan_timer = self.create_timer(1.0, callback=self._scan_for_topics_cb,
                                                 callback_group=self._main_cbg)

    def _stop_logging_cb(self, req: Trigger.Request, res: Trigger.Response) -> Trigger.Response:
        """
        Callback function to handle the stop logging service request.

        This function is triggered when a request is received to stop the logging process.
        It stops the recording and sets the target edit state to 'Stopped'.

        Args:
            req (Trigger.Request): The request message.
            res (Trigger.Response): The response message.

        Returns:
            res (Trigger.Response): The response message.
        """
        try:
            res.success = True
            self._pause_until = time.time() + constants.PAUSE_AFTER_FORCE_STOP
            pause_time_str = time.strftime('%H:%M:%S', time.localtime(self._pause_until))

            if self._target_edit_state == RecordingState.Stopped:
                res.message = "Logging already stopped. Pausing until {}.".format(pause_time_str)
                self.get_logger().info("Logging already stopped. Pausing until {}.".format(pause_time_str))
                return res                                 

            self._target_edit_state = RecordingState.Stopped
            res.message = "Logging stopped successfully. Pausing until {}.".format(pause_time_str)

            self.get_logger().info("Stopping logging on service. Closing bag file. Pausing until {}.".format(pause_time_str))
            self._change_gc.trigger()
            return res

        except Exception as e:  # noqa E722
            self.get_logger().error(traceback.format_stack())
            res.success = False
            res.message = f"Failed to stop logging: {e}"
            return res


    def _scan_for_topics_cb(self):
        """
        Callback function to scan for topics and create subscriptions.

        This function is responsible for scanning the specified topics and creating
        subscriptions to them. It also sets up a timer to check for timeouts and logs
        the status of the monitoring and logging processes.

        The function performs the following steps:
        1. If the node state is `Scanning`, it retrieves the publishers' information
           for the monitoring topic and creates a subscription for it. It also sets up
           a timer to check for timeouts and logs the monitoring status.
        2. For each topic in the list of topics to scan, it retrieves the publishers'
           information and creates a subscription for the topic. It then removes the
           topic from the list and logs the logging status.
        3. If the node state is `Running` and all topics have been scanned, it logs
           the number of active subscriptions and destroys the scan timer.

        Exceptions:
            Logs an error message with the traceback if an exception occurs.

        Raises:
            None
        """

        try:
            if self._state == NodeState.Scanning:
                topic_endpoints: List[TopicEndpointInfo] = self.get_publishers_info_by_topic(self._monitor_topic)

                for topic_endpoint in topic_endpoints[:1]:
                    self._create_subscription(self._monitor_topic, topic_endpoint)

                    # Check if timeout receiver thread
                    self._timeout_check_timer = self.create_timer(
                        self._monitor_topic_timeout/10, callback=self._timeout_check_timer_cb,
                        callback_group=self._main_cbg)

                    self.get_logger().info('Monitoring {} of type {} with timeout {} seconds'.format(
                                           self._monitor_topic, topic_endpoint.topic_type, self._monitor_topic_timeout))

                    self._state = NodeState.Running

            for scan_topic in self._topics_to_scan[:]:
                topic_endpoints: List[TopicEndpointInfo] = self.get_publishers_info_by_topic(scan_topic)

                for topic_endpoint in topic_endpoints[:1]:
                    self._create_subscription(scan_topic, topic_endpoint)

                    self._topics_to_scan.remove(scan_topic)
                    self.get_logger().info('Logging {} of type {}.'.format(scan_topic,
                                           topic_endpoint.topic_type))

            if self._state == NodeState.Running and len(self._topics_to_scan) == 0:
                self.get_logger().info('All topics found. {} subscriptions active.'
                                       .format(len(self._topics_type_info)))
                self._scan_timer.destroy()

        except:  # noqa E722
            self.get_logger().error(traceback.format_stack())

    def _create_subscription(self, topic_name: str, topic_endpoint: TopicEndpointInfo):
        """
        Creates a subscription to a specified topic.

        This method dynamically imports the topic type module and class based on the 
        provided topic endpoint information. It then creates a subscription to the 
        topic with the specified QoS settings and appends the subscription to the 
        list of topic subscriptions.

        Args:
            topic_name (str): The name of the topic to subscribe to.
            topic_endpoint (TopicEndpointInfo): An object containing information 
                                                about the topic endpoint, including 
                                                the topic type and QoS profile.

        Returns:
            None
        """
        module_name, class_name = topic_endpoint.topic_type.replace('/', '.').rsplit(".", 1)
        type_module = importlib.import_module(module_name)
        topic_class = getattr(type_module, class_name)

        topic_sub_qos = QoSProfile(depth=10)
        topic_sub_qos.reliability = topic_endpoint.qos_profile.reliability
        topic_sub_qos.history = HistoryPolicy.KEEP_ALL

        self._topic_subscriptions.append(self.create_subscription(
            topic_class, topic_name,
            lambda msg: self._receive_topic_callback(msg, topic=topic_name),
            qos_profile=topic_sub_qos,
            callback_group=self._main_cbg, raw=True))
        self._topics_type_info.append((topic_name, topic_endpoint))

    def _receive_topic_callback(self, msg, topic: str):
        """
        Callback function to handle incoming messages on subscribed topics.

        This function is called whenever a message is received on any of the subscribed topics.
        It logs the reception of the message, updates the monitoring state, and writes the message
        to the bag file if recording is active.

        Args:
            msg: The message received from the topic.
            topic (str): The name of the topic on which the message was received.

        Raises:
            Exception: If an error occurs during the processing of the message, it logs the error
                       and ensures that any acquired locks are released.
        """
        try:
            if self.get_logger().is_enabled_for(LoggingSeverity.DEBUG):
                self.get_logger().debug("Got message on {}.". format(topic))
            time_recv = self.get_clock().now()

            if topic == self._monitor_topic:
                self._monitor_last_received = time_recv
                if self._target_edit_state == RecordingState.Stopped:

                    if self._pause_until > time.time():
                        pause_time = time.strftime('%H:%M:%S', time.localtime(self._pause_until))
                        self.get_logger().info(f"Pausing until {pause_time}.", throttle_duration_sec=1.0)
                        return

                    self._target_edit_state = RecordingState.Running
                    self._change_gc.trigger()
                    self.get_logger().info("Got callback from {}. Triggering start.". format(self._monitor_topic))

            # Check that we are running and that bag is open.
            if self._target_edit_state == RecordingState.Running and self._bag_writer is not None:
                self._bag_lock.acquire()
                self._bag_writer.write(topic, msg, time_recv.nanoseconds)
                self._bag_lock.release()

        except Exception as e:  # noqa E722
            if self._bag_lock.locked():
                self._bag_lock.release()
            self.get_logger().error(traceback.format_stack())
            self.get_logger().error("Exception occurred in _receive_topic_callback: {}".format(e))

    def _timeout_check_timer_cb(self):
        """
        Callback function for the timeout check timer.

        This function is called periodically to check if the duration since the last received message
        exceeds the specified timeout duration. If the timeout duration is exceeded and the recording
        state is currently running, it stops the recording and triggers guard condition.

        Raises:
            Exception: Logs an error message if an exception occurs during the execution of the callback.
        """
        try:
            dur_since_last_message = self.get_clock().now() - self._monitor_last_received

            if (dur_since_last_message > self._monitor_timeout_duration) and \
                    self._target_edit_state == RecordingState.Running:
                self._target_edit_state = RecordingState.Stopped
                self._change_gc.trigger()
                self.get_logger().info("Timeout. Triggering stop of recording.". format(self._monitor_topic))

        except:  # noqa E722
            self.get_logger().error("{} occurred in _timeout_check_timer_cb.".format(sys.exc_info()[1]))

    def _change_cb(self):
        """
        Callback function triggered by a guard condition.

        This function is called when a specific guard condition is met. It checks if the shutdown event is not set,
        logs the state change, and either starts or stops the bag recording based on the target edit state.

        Raises:
            Exception: Logs an error message if an exception occurs during the state change process.
        """
        if not self._shutdown.is_set():
            try:
                self.get_logger().info("Changing state to {}"
                                       .format(self._target_edit_state.name))
                if self._target_edit_state == RecordingState.Running:
                    self._start_bag()
                else:
                    self._stop_bag()
            except:  # noqa E722
                self.get_logger().error("{} occurred in _change_cb.".format(sys.exc_info()[1]))

    def _start_bag(self):
        """
        Starts a new bag for logging data.

        This method initializes and opens a new ROS2 bag file for logging data. It ensures that
        only one bag is open at a time by acquiring a lock. If a bag is already open, it logs
        a warning and exits. Otherwise, it creates the necessary directories, sets up the 
        serialization and storage options, and opens a new bag file. It also creates topics 
        in the bag based on the provided topic type information.

        Raises:
            Exception: If any error occurs during the process, it logs the error and releases 
                       the lock if it is held.
        """
        try:
            self._bag_lock.acquire()

            if self._bag_writer is not None:
                self._logger.warning("Bag already open. Will not open again.")
                self._bag_lock.release()
                return

            serialization_format = 'cdr'

            bag_path = os.path.join(self._output_path, constants.LOGS_BAG_FOLDER_NAME_PATTERN.format(
                self._bag_name, time.strftime("%Y%m%d-%H%M%S")))
            if not os.path.exists(self._output_path):
                os.makedirs(self._output_path)

            converter_options = rosbag2_py.ConverterOptions(
                input_serialization_format=serialization_format,
                output_serialization_format=serialization_format)

            storage_options = rosbag2_py.StorageOptions(uri=bag_path, storage_id=self._logging_provider)

            self._bag_writer = rosbag2_py.SequentialWriter()
            self._bag_writer.open(storage_options, converter_options)

            for topic_type_info in self._topics_type_info:
                self.create_topic(self._bag_writer, topic_type_info[0], topic_type_info[1])

            self._bag_lock.release()
        except:  # noqa E722
            self.get_logger().error("{} occurred in _start_bag.".format(sys.exc_info()[1]))
            if self._bag_lock.locked():
                self._bag_lock.release()

    def _stop_bag(self):
        """
        Stops the bag logging process by setting the bag writer to None.
        This effectively stops any further data from being written to the bag.
        """

        self._bag_writer = None
        self._topic_counter = 0

    def create_topic(self, writer, topic_name:str, topic_type_info: TopicEndpointInfo, serialization_format:str='cdr'):
        """
        Creates a new topic in the ROS2 bag file.

        Args:
            writer: The writer object used to create the topic.
            topic_name (str): The name of the topic to be created.
            topic_type_info (TopicEndpointInfo): Information about the topic type.
            serialization_format (str, optional): The serialization format to be used. Defaults to 'cdr'.

        Returns:
            None
        """

        self._topic_counter += 1

        if os.environ["ROS_DISTRO"] == "jazzy":
            topic = rosbag2_py.TopicMetadata(id=self._topic_counter, name=topic_name, type=topic_type_info.topic_type,
                                            serialization_format=serialization_format)
        else:
            topic = rosbag2_py.TopicMetadata(name=topic_name, type=topic_type_info.topic_type,
                                            serialization_format=serialization_format)

        writer.create_topic(topic)


def main(args=None):
    """
    Entry point for the ROS2 node.

    This function initializes the ROS2 Python client library, creates an instance of the BagLogNode,
    and starts spinning the node using a MultiThreadedExecutor. It handles keyboard interrupts and
    logs any exceptions that occur during the node's execution. Finally, it ensures that the ROS2
    client library is properly shut down.

    Args:
        args (list, optional): Command-line arguments passed to the ROS2 node. Defaults to None.

    Raises:
        Exception: Logs any exception that occurs during the node's execution.
    """

    try:
        rclpy.init(args=args)
        with BagLogNode() as bag_log_node:
            executor = MultiThreadedExecutor()
            rclpy.spin(bag_log_node, executor)
        # Destroy the node explicitly
        bag_log_node.destroy_node()
    except KeyboardInterrupt:
        pass
    except:  # noqa: E722
        logging.exception("Error in Node")
    finally:
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
