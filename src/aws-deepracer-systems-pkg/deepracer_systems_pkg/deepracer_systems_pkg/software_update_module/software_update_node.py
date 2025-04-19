#!/usr/bin/env python

#################################################################################
#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.          #
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

"""
software_update_node.py

This module creates the software_update_node which is responsible for managing
the update system for DeepRacer packages. It provides services and functions to
check for software update, execute software update, provide status of the current
software update state and installation state, install signed packages from USB drive.

The node defines:
    update_check_timer: A timer created to periodically schedule the software update
                        check function to look for software updates for the DeepRacer
                        pacakges.
    software_update_pct_publisher: A publisher to publish the installation state and
                                   the percentage.
    software_update_check_service: A service that is called to identify if there is
                                   a software update available for the DeepRacer
                                   packages.
    begin_update_service: A service that is called to execute the software update
                          and install latest DeepRacer packages.
    software_update_state_service: A service that returns the current software update
                                   state that the node is aware of.
"""

import os
import time
import glob
import threading
import apt
import json
import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import (ReentrantCallbackGroup,
                                   MutuallyExclusiveCallbackGroup)
from rclpy.qos import (QoSReliabilityPolicy,
                       QoSProfile,
                       QoSHistoryPolicy)

from deepracer_interfaces_pkg.srv import (SoftwareUpdateCheckSrv,
                                          BeginSoftwareUpdateSrv,
                                          SoftwareUpdateStateSrv,
                                          SetStatusLedBlinkSrv,
                                          SetStatusLedSolidSrv,
                                          USBFileSystemSubscribeSrv,
                                          USBMountPointManagerSrv)
from deepracer_interfaces_pkg.msg import (NetworkConnectionStatus,
                                          SoftwareUpdatePctMsg,
                                          USBFileSystemNotificationMsg)
from deepracer_systems_pkg import (constants,
                                   scheduler,
                                   utility)
from deepracer_systems_pkg.software_update_module import (cache_update_progress,
                                                          cache_open_progress,
                                                          fetch_progress,
                                                          install_progress,
                                                          software_update_utils,
                                                          software_update_config)

#########################################################################################
# Software update class


class SoftwareUpdateNode(Node):
    """Node responsible for the software update system managing the aws-deepracer-core,
       aws-deepracer-webserver, aws-deepracer-util and aws-deepracer-sample-models packages.
    """

    def __init__(self):
        """Create a SoftwareUpdateNode.
        """
        super().__init__("software_update_process")
        self.get_logger().info("software_update_process started")

        # Scheduler to queue the function calls and run them in a separate thread.
        self.scheduler = scheduler.Scheduler(self.get_logger())

        # Threading lock object to safely update the update_state variable.
        self.state_guard = threading.Lock()
        self.update_state = software_update_config.SoftwareUpdateState.UPDATE_UNKNOWN

        # Threading Event object to indicate if the software update check is completed.
        self.check_complete = threading.Event()
        # Flag to indicate software update check in progress.
        self.check_in_progress = False

        # List of packages that have updates available.
        self.update_list = list()

        # Flag to identify if the network is connected.
        self.is_network_connected = False
        # Flag to identify if software update check has to performed
        # again when network is connected.
        self.reschedule_software_update_check = False

        # The apt cache object.
        self.cache = apt.Cache()

        # Double buffer object containing the current update percentage and progress state.
        self.pct_dict_db = utility.DoubleBuffer(clear_data_on_get=False)
        self.pct_dict_db.put({software_update_config.PROG_STATE_KEY:
                              software_update_config.PROGRESS_STATES[0],
                              software_update_config.PROG_PCT_KEY: 0.0})

        # Timer to periodically check for software update.
        if software_update_config.ENABLE_PERIODIC_SOFTWARE_UPDATE:
            self.get_logger().info("Schedule the software update check every "
                                   f"{software_update_config.SOFTWARE_UPDATE_PERIOD_IN_SECONDS} "
                                   "seconds.")
            self.schedule_update_check_cb = ReentrantCallbackGroup()
            self.update_check_timer = \
                self.create_timer(software_update_config.SOFTWARE_UPDATE_PERIOD_IN_SECONDS,
                                  self.schedule_update_check,
                                  callback_group=self.schedule_update_check_cb)

        # Publisher that sends software update pct and status.

        # Guaranteed delivery is needed to send messages to late-joining subscription.
        qos_profile = QoSProfile(depth=1)
        qos_profile.history = QoSHistoryPolicy.KEEP_LAST
        qos_profile.reliability = QoSReliabilityPolicy.RELIABLE
        self.pct_obj = SoftwareUpdatePctMsg()
        self.software_update_pct_pub_cb = ReentrantCallbackGroup()
        self.software_update_pct_publisher = \
            self.create_publisher(SoftwareUpdatePctMsg,
                                  software_update_config.SOFTWARE_UPDATE_PCT_TOPIC_NAME,
                                  qos_profile=qos_profile,
                                  callback_group=self.software_update_pct_pub_cb)

        # Service to check if there is a software update available.
        self.software_update_check_cb_group = ReentrantCallbackGroup()
        self.software_update_check_service = \
            self.create_service(SoftwareUpdateCheckSrv,
                                software_update_config.SOFTWARE_UPDATE_CHECK_SERVICE_NAME,
                                self.software_update_check,
                                callback_group=self.software_update_check_cb_group)

        # Service to execute the software update and install latest packages.
        self.begin_update_service_cb_group = ReentrantCallbackGroup()
        self.begin_update_service = \
            self.create_service(BeginSoftwareUpdateSrv,
                                software_update_config.BEGIN_SOFTWARE_UPDATE_SERVICE_NAME,
                                self.begin_update,
                                callback_group=self.begin_update_service_cb_group)

        # Service to get the current software update state.
        self.software_update_state_service_cb_group = ReentrantCallbackGroup()
        self.software_update_state_service = \
            self.create_service(SoftwareUpdateStateSrv,
                                software_update_config.SOFTWARE_UPDATE_STATE_SERVICE_NAME,
                                self.software_update_state,
                                callback_group=self.software_update_state_service_cb_group)

        self.nw_con_status_cb_group = ReentrantCallbackGroup()
        self.network_connection_status_sub = \
            self.create_subscription(NetworkConnectionStatus,
                                     software_update_config.NETWORK_CONNECTION_STATUS_TOPIC_NAME,
                                     self.network_connection_status_cb,
                                     10,
                                     callback_group=self.nw_con_status_cb_group)

        # Clients to Status LED services that are called to indicate progress/success/failure
        # status while loading model.
        self.led_cb_group = MutuallyExclusiveCallbackGroup()
        self.led_blink_service = self.create_client(SetStatusLedBlinkSrv,
                                                    constants.LED_BLINK_SERVICE_NAME,
                                                    callback_group=self.led_cb_group)
        self.led_solid_service = self.create_client(SetStatusLedSolidSrv,
                                                    constants.LED_SOLID_SERVICE_NAME,
                                                    callback_group=self.led_cb_group)
        while not self.led_blink_service.wait_for_service(timeout_sec=1.0):
            self.get_logger().info("Led blink service not available, waiting again...")
        while not self.led_solid_service.wait_for_service(timeout_sec=1.0):
            self.get_logger().info("Led solid service not available, waiting again...")
        self.led_blink_request = SetStatusLedBlinkSrv.Request()
        self.led_solid_request = SetStatusLedSolidSrv.Request()

        # Client to USB File system subscription service that allows the node to install
        # signed software packages(*.deb.gpg) present in the USB. The usb_monitor_node
        # will trigger notification if it finds the "update" folder from the watchlist
        # in the USB drive.
        self.usb_sub_cb_group = ReentrantCallbackGroup()
        self.usb_file_system_subscribe_client = self.create_client(USBFileSystemSubscribeSrv,
                                                                   constants.USB_FILE_SYSTEM_SUBSCRIBE_SERVICE_NAME,
                                                                   callback_group=self.usb_sub_cb_group)
        while not self.usb_file_system_subscribe_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info("File System Subscribe not available, waiting again...")

        # Client to USB Mount point manager service to indicate that the usb_monitor_node can safely
        # decrement the counter for the mount point once the action function for the "update" folder
        # file being watched by software_update_node is succesfully executed.
        self.usb_mpm_cb_group = ReentrantCallbackGroup()
        self.usb_mount_point_manager_client = self.create_client(USBMountPointManagerSrv,
                                                                 constants.USB_MOUNT_POINT_MANAGER_SERVICE_NAME,
                                                                 callback_group=self.usb_mpm_cb_group)
        while not self.usb_mount_point_manager_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info("USB mount point manager service not available, waiting again...")

        # Subscriber to USB File system notification publisher to recieve the broadcasted messages
        # with file/folder details, whenever a watched file is identified in the USB connected.
        self.usb_notif_cb_group = ReentrantCallbackGroup()
        self.usb_file_system_notification_sub = self.create_subscription(USBFileSystemNotificationMsg,
                                                                         constants.USB_FILE_SYSTEM_NOTIFICATION_TOPIC,
                                                                         self.usb_file_system_notification_cb,
                                                                         10,
                                                                         callback_group=self.usb_notif_cb_group)

        # Add the "update" folder to the watchlist.
        usb_file_system_subscribe_request = USBFileSystemSubscribeSrv.Request()
        usb_file_system_subscribe_request.file_name = software_update_config.UPDATE_SOURCE_DIRECTORY
        usb_file_system_subscribe_request.callback_name = software_update_config.SCHEDULE_USB_UPDATE_SCAN_CB
        usb_file_system_subscribe_request.verify_name_exists = True
        self.usb_file_system_subscribe_client.call_async(usb_file_system_subscribe_request)

        # Set the power led to blue.
        self.led_solid_request.led_index = constants.LEDIndex.POWER_LED
        self.led_solid_request.color = constants.LEDColor.BLUE
        self.led_solid_request.hold = 0.0
        self.led_solid_service.call_async(self.led_solid_request)

        # Heartbeat timer.
        self.timer_count = 0
        self.timer = self.create_timer(5.0, self.timer_callback)

        # Schedule update check.
        if software_update_config.ENABLE_PERIODIC_SOFTWARE_UPDATE:
            self.schedule_update_check()

        self.get_logger().info("Software Update node successfully created")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Called when the object is destroyed.
        """
        self.destroy_timer(self.timer)
        self.scheduler.schedule_exit()

        if software_update_config.ENABLE_PERIODIC_SOFTWARE_UPDATE:
            self.destroy_timer(self.update_check_timer)

    def timer_callback(self):
        """Heartbeat function to keep the node alive.
        """
        self.get_logger().debug(f"Timer heartbeat {self.timer_count}")
        self.timer_count += 1

    def usb_file_system_notification_cb(self, notification_msg):
        """Callback for messages triggered whenever usb_monitor_node identifies a file/folder
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
        if notification_msg.file_name == software_update_config.UPDATE_SOURCE_DIRECTORY and \
           notification_msg.callback_name == software_update_config.SCHEDULE_USB_UPDATE_SCAN_CB:
            self.schedule_usb_update_scan(path=notification_msg.path,
                                          name=notification_msg.file_name,
                                          node_name=notification_msg.node_name)

    def network_connection_status_cb(self, data):
        self.is_network_connected = data.network_connected
        if self.is_network_connected and self.reschedule_software_update_check:
            self.reschedule_software_update_check = False
            self.schedule_update_check()

    def software_update_check(self, req, res):
        """Callback for the software_update_check service. Returns the software update state
           details.

        Args:
            req (SoftwareUpdateCheckSrv.Request): Request object with the force_update_check
                                                  flag to indicate to trigger force update check
                                                  immediately.
            res (SoftwareUpdateCheckSrv.Response): Response object with software_update_state(int)
                                                   with the software udpate state information.

        Returns:
            SoftwareUpdateCheckSrv.Response: Response object with software_update_state(int)
                                             with the software udpate state information.
        """
        self.get_logger().info(f"software_update_check({req.force_update_check})")
        res.software_update_state = self.get_update_state(req.force_update_check)
        return res

    def begin_update(self, req, res):
        """Callback for the begin_update service. Handles scheduling execute_update function call.

        Args:
            req (BeginSoftwareUpdateSrv.Request): Request object with the sleep_time_before_reboot(int)
                                                  value passed as parameter.
            res (BeginSoftwareUpdateSrv.Response): Response object with response status(bool) indicating
                                                   if the execute_update is scheduled.

        Returns:
            BeginSoftwareUpdateSrv.Response: Response object with response status(bool) indicating
                                             if the execute_update is scheduled.
        """
        self.get_logger().info(f"begin_update({req.sleep_time_before_reboot})")
        self.pct_dict_db.put({software_update_config.PROG_STATE_KEY: software_update_config.PROGRESS_STATES[2],
                              software_update_config.PROG_PCT_KEY: 0.0})
        res.response_status = self.schedule_software_update(req.sleep_time_before_reboot)
        return res

    def software_update_state(self, req, res):
        """Callback for the console_model_action service. Handles the upload model and delete model
           actions from the console.

        Args:
            req (SoftwareUpdateStateSrv.Request): Request object with the request flag set.
            res (SoftwareUpdateStateSrv.Response): Response object with update_state(int)
                                                   with the software udpate state information.

        Returns:
            SoftwareUpdateStateSrv.Response: Response object with update_state(int)
                                             with the software udpate state information.
        """
        self.get_logger().info(f"software_update_state({req.request})")
        try:
            with utility.AutoLock(self.state_guard):
                update_state = self.update_state
                res.update_state = update_state
                self.get_logger().info(f"software_update_state response({update_state})")
            return res
        except Exception:
            self.get_logger().error("Invalid update status")
            res.update_state = software_update_config.SoftwareUpdateState.UPDATE_UNKNOWN
            return res

    def get_state_description(self, state):
        """Helper method to return state description mapped to the software update state passed.

        Args:
            state (int): SoftwareUpdateState value.

        Returns:
            str: SOFTWARE_UPDATE_STATE_MSG mapping for the SoftwareUpdateState value.
        """
        try:
            return software_update_config.SOFTWARE_UPDATE_STATE_MSG[state]
        except Exception:
            return f"Unexpected software update state: {state}"

    def schedule_update_check(self):
        """Wrapper function to schedule the do_update_check function.
        """
        self.get_logger().info("Scheduling routine software update check ...")
        self.scheduler.schedule_action(self.do_update_check)
        self.get_logger().info("Routine software update check scheduled ...")

    def schedule_software_update(self, sleep_time_before_reboot):
        """Wrapper function to safely schedule the execute update function with the required
           arguments.

        Args:
            sleep_time_before_reboot (int): Time in seconds to sleep before initiating
                                            a device reboot after installation.

        Returns:
            bool: True if the execute_update was successfully schedule else False.
        """
        with utility.AutoLock(self.state_guard):
            if self.update_state == software_update_config.SoftwareUpdateState.UPDATE_AVAILABLE:
                self.get_logger().info("Update is available, scheduling...")
                sleep_time_before_reboot = \
                    software_update_config.MIN_TIME_BEFORE_REBOOT_IN_SECONDS \
                    if sleep_time_before_reboot < software_update_config.MIN_TIME_BEFORE_REBOOT_IN_SECONDS \
                    else sleep_time_before_reboot
                # Update kickoff: schedule update.
                self.scheduler.schedule_action(self.execute_update, reboot_after=sleep_time_before_reboot)
                # Change state to requested.
                self.update_state = software_update_config.SoftwareUpdateState.UPDATE_PENDING
                return True
            else:
                self.get_logger().info("Ignoring update request, state: "
                                       f"{self.get_state_description(self.update_state)}")
                return False

    def schedule_usb_update_scan(self, path, name, node_name):
        """Wrapper function to schedule the usb_update_scan function with the required
           arguments.

        Args:
            path (str): File path where the packages are present on the USB.
            name (str): Name of the folder ("update").
            node_name (str): Filesystem where the USB was mounted.
        """
        self.scheduler.schedule_action(self.usb_update_scan,
                                       path=path,
                                       name=name,
                                       node_name=node_name)

    def get_update_state(self, force_update_check=False):
        """Return the update status after perfoming software update check or waiting for current
           ongoing check to complete.

        Args:
            force_update_check (bool, optional): Set to True to force schedule update check immediately.
                                                 Defaults to False.

        Returns:
            int: Software update state information.
        """
        self.get_logger().info("Get software update state...")
        with utility.AutoLock(self.state_guard):

            # Force update check if it hasn"t been completed yet.
            if self.update_state == software_update_config.SoftwareUpdateState.UPDATE_UNKNOWN:
                force_update_check = True

            # Kick off update check if needed.
            if not self.check_in_progress:
                if force_update_check:
                    self.check_complete.clear()
                    self.scheduler.schedule_action(self.do_update_check)
                else:
                    self.get_logger().info("Force software update check flag is not set")
            else:
                self.get_logger().info("Previous scheduled software update check in progress...")

        # Wait for the check to complete.
        while not self.check_complete.wait(2):
            self.get_logger().info("Waiting for software update check complete...")

        self.get_logger().info("Software update check complete.")
        with utility.AutoLock(self.state_guard):
            # State here can still be unknown if it had been unknown before the last update
            # and the last update failed. Report and do the forced check next time.
            update_state = self.update_state
            self.get_logger().info("Software update status: "
                                   f"{self.get_state_description(update_state)}")
            return update_state

    def update_deepracer_cache(self):
        """Helper method top update and open the cache object to fetch the latest information
           from the DeepRacer apt repository.

        Returns:
            bool: True if successfully updated the cache and opened it else False.
        """
        # Update and open the cache.
        try:
            for sources_list in software_update_config.DEEPRACER_SOURCE_LIST_PATH:
                if not os.path.exists(sources_list):
                    self.get_logger().warn(f"Sources list {sources_list} does not exist.")
                    continue
                self.get_logger().info(f"Updating the cache for {sources_list}...")
                self.cache.update(fetch_progress=cache_update_progress.CacheUpdateProgress(self.get_logger()),
                                sources_list=sources_list)
                
            self.get_logger().info("Cache updated. Re-opening the cache...")
            self.cache.open(cache_open_progress.CacheOpenProgress(self.get_logger()))
        except Exception as ex:
            self.get_logger().error(f"Failed to update APT cache: {ex}")
            return False
        return True

    def update_pkg_candidate_list(self):
        """Helper method to identify the packages that have an update candidate available and
           populate the update_list.
        """
        self.update_list = list()
        # Find relevant packages.
        for package_name in software_update_config.DEEPRACER_PACKAGES:
            if package_name in self.cache:
                package = self.cache[package_name]
                self.get_logger().info(f"Verifying package {package.name}...")

                # Skip if already provided by another package that's installed
                already_provided = False
                for other_package in self.cache:
                    if other_package.is_installed and self.check_package_provides(other_package.name, package_name):
                        already_provided = True
                        break

                if already_provided:
                    self.get_logger().info(f"Package {package_name} is provided by installed {other_package.name}")
                    continue

                if not package.candidate.version.startswith(software_update_config.VERSION_MASK):
                    self.get_logger().info(f"* {package.name} package is not built for the Ubuntu and ROS packages; "
                                           f"candidate { package.candidate.version} is will not be used")
                    continue

                self.get_logger().info(f"* {package.name} package passes the version check; "
                                       f"verifying candidate {package.candidate.version}")

                # New package?
                if not package.is_installed:
                    self.get_logger().info(f"* {package.name} package not installed; "
                                           f"candidate {package.candidate.version} is added to update list")
                    self.update_list.append(package)

                # Newer version available?
                elif package.candidate.version > package.installed:
                    self.get_logger().info(f"* {package.name} package update available: "
                                           f"{package.candidate.version} > {package.installed.version}; "
                                           "Added to update list")
                    self.update_list.append(package)

    def verify_software_update(self):
        """Validation method to verify if the installed version of the packages are the same as the
           candidate versions that were identified for installation.

        Returns:
            bool: True if candidates were successfully installed else False.
        """
        for package in self.update_list:
            self.get_logger().info(f"Verifying updated package {package.name}...")

            if not package.installed.version.startswith(software_update_config.VERSION_MASK):
                self.get_logger().error(f"* {package.name} package is not built for the Ubuntu and ROS packages; "
                                        f"incorrect package installed: {package.installed.version}")
                return False

            self.get_logger().info(f"* {package.name} package passes the version check; "
                                   f"verifying candidate {package.candidate.version}")

            if not package.is_installed:
                self.get_logger().error(f"* {package.name} package fails the installation check: "
                                        f"{package.installed.version}")
                return False
            self.get_logger().info(f"* {package.name} package passes the validation")
        return True

    def do_update_check(self):
        """Main function to perform the cache update, update the candidate list and
           update_state flag.
        """
        self.check_in_progress = True
        self.get_logger().info("Checking software update...")
        # Make sure we have network connection.
        if not self.is_network_connected:
            self.get_logger().info("Scheduling software update check to wait "
                                   "for network connection...")
            self.reschedule_software_update_check = True
            return

        # Update and Re-open the cache to read the updated package list
        if not self.update_deepracer_cache():
            self.check_complete.set()
            self.check_in_progress = False
            return

        # Reset the package update list.
        self.update_pkg_candidate_list()

        with utility.AutoLock(self.state_guard):

            # No packages found to update?
            if len(self.update_list) == 0:
                self.update_state = software_update_config.SoftwareUpdateState.UP_TO_DATE

            else:
                self.update_state = software_update_config.SoftwareUpdateState.UPDATE_AVAILABLE
                self.pct_dict_db.put({software_update_config.PROG_STATE_KEY:
                                      software_update_config.PROGRESS_STATES[1],
                                      software_update_config.PROG_PCT_KEY: 0.0})
            self.get_logger().info(self.get_state_description(self.update_state))
            self.check_in_progress = False
            self.check_complete.set()

    def execute_update(self, keyworded_args):
        """Main function to execute the software update process triggered from console. It commits
           the udpated packages found, verify the package installation, publish update percentage
           post installation, update power LED status during the process and reboot the device
           after installation process is completed.

        Args:
            keyworded_args (dict): Keyworded arguments passed to the function while scheduling.
        """
        self.get_logger().info("Starting software update...")
        self.publish_pct_timer = self.create_timer(2.0, self.publish_update_pct)
        with utility.AutoLock(self.state_guard):
            # Ignore if already up to date.
            if self.update_state == software_update_config.SoftwareUpdateState.UP_TO_DATE:
                self.get_logger().info(f"Software is up to date, ignoring: {self.update_state}")
                return

            # Ignore if in progress.
            if self.update_state == software_update_config.SoftwareUpdateState.UPDATE_IN_PROGRESS:
                self.get_logger().info("Software update is already in progress, ignoring.")
                return

            # Mark as in progress.
            self.update_state = software_update_config.SoftwareUpdateState.UPDATE_IN_PROGRESS

        self.led_blink_request.led_index = constants.LEDIndex.POWER_LED
        self.led_blink_request.color1 = constants.LEDColor.BLUE
        self.led_blink_request.color2 = constants.LEDColor.NO_COLOR
        self.led_blink_request.delay = 0.2
        self.led_blink_service.call(self.led_blink_request)

        try:
            for package in self.update_list:
                self.get_logger().info(f"** Installing Software update for {package.name}")
                package.mark_install()

            commit_response = self.cache.commit(fetch_progress.FetchProgress(self.pct_dict_db,
                                                                             self.get_logger()),
                                                install_progress.InstallProgress(self.pct_dict_db,
                                                                                 self.get_logger()))

            self.get_logger().info(f"** Apt cache committed with latest packages: {commit_response}")
            retry_verification = 0
            installation_successful = False
            while retry_verification < software_update_config.MAX_UPDATE_VERIFICATION_RETRY_COUNT:
                if self.verify_software_update():
                    self.get_logger().info("Software update verified")
                    installation_successful = True
                    # Write to software update status as atleast one
                    # update has completed successfully.
                    with open(constants.SOFTWARE_UPDATE_STATUS_PATH, "w") \
                         as software_update_status_file:
                        software_update_status = {"update_completed": True}
                        json.dump(software_update_status, software_update_status_file)
                        self.get_logger().info("Written to software update status file.")
                    break
                else:
                    self.get_logger().error("Software update could not be verified. "
                                            f"Retrying {retry_verification+1}/{5}..")
                    retry_verification += 1
                    time.sleep(5)
            if not installation_successful:
                raise Exception("Failed to install packages")
            # Update is only 100% after the commit call exits
            # Set the state to complete
            self.publish_pct_timer.cancel()
            self.pct_dict_db.put({software_update_config.PROG_STATE_KEY:
                                  software_update_config.PROGRESS_STATES[5],
                                  software_update_config.PROG_PCT_KEY: 100.0})
            self.publish_update_pct()

            with utility.AutoLock(self.state_guard):
                self.update_state = software_update_config.SoftwareUpdateState.UP_TO_DATE
                self.get_logger().info("Software update complete.")

        except Exception as ex:
            self.led_solid_request.led_index = constants.LEDIndex.POWER_LED
            self.led_solid_request.color = constants.LEDColor.RED
            self.led_solid_request.hold = 2.0

            self.led_solid_service.call(self.led_solid_request)
            with utility.AutoLock(self.state_guard):
                self.update_state = software_update_config.SoftwareUpdateState.UPDATE_AVAILABLE
                self.get_logger().info(f"Software update failed: {ex}")
            self.pct_dict_db.put({software_update_config.PROG_STATE_KEY:
                                  software_update_config.PROGRESS_STATES[0],
                                  software_update_config.PROG_PCT_KEY: 0.0})
            self.publish_update_pct()

        #
        # Not rebooting the software update is dangerous and leave it in unstable state
        # The parameter passed to the software update is to reboot after some sleep time.
        # This is required so that the webserver can return 100% compeletion to the client
        # Before it reboots itself.
        #
        reboot_after = keyworded_args.get("reboot_after", 0)
        self.get_logger().info(f"Reboot after: {reboot_after} seconds")
        time.sleep(reboot_after)

        self.led_solid_request.led_index = constants.LEDIndex.POWER_LED
        self.led_solid_request.color = constants.LEDColor.NO_COLOR
        self.led_solid_request.hold = 0.0
        self.led_solid_service.call(self.led_solid_request)

        self.get_logger().info("Rebooting...")
        os.system("reboot")

    def usb_update_scan(self, keyworded_args):
        """Main function to scan for packages in the USB, verify the packages, decrypt
           and install packages, update power LED status during the process.

        Args:
            keyworded_args (dict): Keyworded arguments passed to the function while scheduling.
        """

        self.led_blink_request.led_index = constants.LEDIndex.POWER_LED
        self.led_blink_request.color1 = constants.LEDColor.BLUE
        self.led_blink_request.color2 = constants.LEDColor.NO_COLOR
        self.led_blink_request.delay = 0.2
        self.led_blink_service.call(self.led_blink_request)

        base_path = keyworded_args.get("path", "")
        name = keyworded_args.get("name", "")
        node_name = keyworded_args.get("node_name", None)

        encrypted_list = list()

        # Find potential packages.
        self.get_logger().info("Scanning for update packages...")
        search_path = os.path.join(base_path, name, "*.deb.gpg")
        for package_name in glob.glob(search_path):
            self.get_logger().info(f"  verifying {package_name}...")
            if not software_update_utils.verify_package(package_name):
                self.get_logger().info("  - failed to validate the package, ignoring.")
                continue

            encrypted_list.append(package_name)
            self.get_logger().info("  + valid update package.")

        if len(encrypted_list) == 0:
            self.get_logger().info(f"No valid packages found in: {search_path}")

        else:
            decrypted_list = list()

            self.get_logger().info("Decrypting:")
            for encrypted_name in encrypted_list:

                # Remove .gpg part.
                decrypted_name = os.path.splitext(encrypted_name)[0]

                # Remove the path.
                decrypted_name = os.path.basename(decrypted_name)

                # Add temporary path.
                decrypted_name = os.path.join(constants.TEMP_DIRECTORY, decrypted_name)

                self.get_logger().info(f"  {decrypted_name}")
                if not software_update_utils.decrypt_package(encrypted_name, decrypted_name):
                    self.get_logger().info("  * failed to decrypt the package.")
                    continue

                decrypted_list.append(decrypted_name)
                self.get_logger().info("  * successfully decrypted.")

            if len(decrypted_list) == 0:
                self.get_logger().info("No successfully decrypted packages.")

            else:
                self.get_logger().info("Installing packages:")
                for decrypted_name in decrypted_list:

                    # Install the package.
                    self.get_logger().info(f"  {decrypted_name}")
                    if not software_update_utils.install_debian(decrypted_name):
                        self.get_logger().info("  * failed to install.")
                    else:
                        self.get_logger().info("  * successfully installed.")

                    # Remove the temporary package file.
                    os.remove(decrypted_name)

        # Unmount the media.
        if node_name is not None:
            mount_point_mgr_request = USBMountPointManagerSrv.Request()
            mount_point_mgr_request.node_name = node_name
            mount_point_mgr_request.action = 0
            self.usb_mount_point_manager_client.call_async(mount_point_mgr_request)

        self.led_solid_request.led_index = constants.LEDIndex.POWER_LED
        self.led_solid_request.color = constants.LEDColor.BLUE
        self.led_solid_request.hold = 0.0
        self.led_solid_service.call(self.led_solid_request)

    def publish_update_pct(self):
        """Wrapper method that publishes update percentage and progress state.
        """
        pct_dict = self.pct_dict_db.get_nowait()
        pct_obj = SoftwareUpdatePctMsg()
        pct_obj.update_pct = pct_dict[software_update_config.PROG_PCT_KEY]
        pct_obj.status = pct_dict[software_update_config.PROG_STATE_KEY]
        self.software_update_pct_publisher.publish(pct_obj)

    def check_package_provides(self, package_name, provided_package_name):
        """Checks if a package provides another package (acts as a substitute).
        
        Args:
            package_name (str): Name of the package to check
            provided_package_name (str): Name of the package that might be provided
            
        Returns:
            bool: True if package_name provides provided_package_name, False otherwise
        """
        if package_name not in self.cache:
            self.get_logger().error(f"Package {package_name} not found in cache")
            return False
            
        package = self.cache[package_name]
        
        # Check installed version first if available
        if package.is_installed and hasattr(package.installed, 'provides'):
            for provided in package.installed.provides:
                if provided == provided_package_name:
                    self.get_logger().debug(f"Installed {package_name} provides {provided_package_name}")
                    return True
                    
        # Also check candidate version
        if hasattr(package.candidate, 'provides'):
            for provided in package.candidate.provides:
                if provided == provided_package_name:
                    self.get_logger().debug(f"Candidate {package_name} provides {provided_package_name}")
                    return True
                    
        return False


def main(args=None):
    try:
        rclpy.init(args=args)
        with SoftwareUpdateNode() as software_update_node:
            executor = MultiThreadedExecutor()
            rclpy.spin(software_update_node, executor)
            software_update_node.destroy_node()

    except KeyboardInterrupt:
        pass

    finally:
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
