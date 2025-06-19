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
device_status_node.py

This module creates the device_status_node which is responsible for providing real-time
system metrics including CPU load, CPU temperature, memory utilization, and free disk space.

The node defines:
    get_device_status_service: A service that is called to get the real-time system metrics.
"""

import psutil
import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor

from deepracer_interfaces_pkg.srv import GetDeviceStatusSrv
from deepracer_interfaces_pkg.msg import DeviceStatusMsg, LatencyMeasureMsg
from device_info_pkg import constants
from device_info_pkg.ring_buffer import RingBuffer

#########################################################################################
# DeviceStatusNode


class DeviceStatusNode(Node):
    """Node responsible for retrieving real-time system metrics.
    """

    def __init__(self):
        """Create a DeviceStatusNode.
        """
        super().__init__("device_status_node")
        self.get_logger().info("Device Status Node starting - monitoring system metrics")

        # Variables to store the system metrics
        self.cpu_percent = 0.0
        self.cpu_temp = 0.0
        self.cpu_freq = 0.0     # Current CPU frequency in MHz
        self.cpu_freq_max = 0.0  # Maximum CPU frequency in MHz
        self.memory_usage = 0.0
        self.free_disk = 0.0
        self.fps_mean = 0.0

        # Data structure to store latency messages
        self.latency_stats = {
            "mean": 0.0,
            "std": 0.0,
            "min": 0.0,
            "max": 0.0,
            "median": 0.0,
            "p95": 0.0
        }
        self.latency_history = RingBuffer(maxsize=constants.MAX_LATENCY_HISTORY)

        # Subscribe to the latency topic
        self.latency_subscriber = self.create_subscription(
            LatencyMeasureMsg,
            constants.SERVO_LATENCY_TOPIC_NAME,
            self.latency_callback,
            10  # QoS depth,
        )
        self.get_logger().info(f"Subscribed to {constants.SERVO_LATENCY_TOPIC_NAME} topic")

        # Service to get the system metrics
        self.get_device_status_service = self.create_service(
            GetDeviceStatusSrv,
            constants.GET_DEVICE_STATUS_SERVICE_NAME,
            self.get_device_status
        )

        # Publisher for device status updates
        self.status_publisher = self.create_publisher(
            DeviceStatusMsg,
            constants.DEVICE_STATUS_TOPIC_NAME,
            1  # QoS depth
        )

        # Timer to periodically update the metrics
        self.timer_count = 0
        self.update_timer = self.create_timer(constants.DEVICE_STATUS_TIMING, self.update_timer_callback)


        # Pre-allocate for better performance
        self.last_latency_msg =  self.get_clock().now()
        self.latency_msg_counter = 0

        # Cache temperature sensor path on startup
        self.temp_sensor_path = self._find_temp_sensor_path()

        # Initialize metrics on startup
        self.update_metrics()

    def latency_callback(self, latency_msg: LatencyMeasureMsg):
        """Callback for the latency subscriber - optimized for performance.

        Args:
            msg (LatencyMeasure): The latency message containing send and receive timestamps
        """
        try:
            # Calculate latency more efficiently
            latency_ms = latency_msg.latency_ms
            receive_time = self.get_clock().now()

            # Check if we should clear the history due to a time gap
            if (receive_time - self.last_latency_msg).nanoseconds > 500_000_000:  # If more than 500ms since last measurement
                time_gap_ms = (receive_time - self.last_latency_msg).nanoseconds / 1.0e6
                self.get_logger().info(f"Latency gap detected ({time_gap_ms:.1f}ms). Clearing latency history.")
                self.latency_history.clear()

            # Store the latency value and timestamp in the history deque
            self.latency_history.append(latency_ms, receive_time)
            self.last_latency_msg = receive_time

        except Exception as ex:
            self.get_logger().error(f"Error processing latency message: {ex}")

    def update_timer_callback(self):
        """Timer callback to update the system metrics periodically.
        """
        self.update_metrics()
        self.timer_count += 1

        # Publish the updated status
        self.publish_status()

        if self.timer_count % 5 == 0:
            self.get_logger().info(
                f"Status update (count: {self.timer_count}) | " +
                f"CPU percent: {self.cpu_percent:.2f}% | " +
                f"CPU temp: {self.cpu_temp:.1f}°C | " +
                f"CPU freq: {self.cpu_freq:.1f}MHz / {self.cpu_freq_max:.1f}MHz max | " +
                f"Memory usage: {self.memory_usage:.1f}% | Free disk: {self.free_disk:.1f}% | " +
                f"Latency: {self.latency_stats['mean']:.1f}")

    def get_device_status(self, req, res):
        """Callback for the get_device_status service. Returns the system metrics."""
        self.get_logger().info("get_device_status service called")
        try:
            # Fill response with current metrics
            res.cpu_percent = self.cpu_percent
            res.cpu_temp = self.cpu_temp
            res.cpu_freq = self.cpu_freq
            res.cpu_freq_max = self.cpu_freq_max
            res.memory_usage = self.memory_usage
            res.free_disk = self.free_disk
            res.latency_mean = self.latency_stats["mean"]
            res.latency_p95 = self.latency_stats["p95"]
            res.fps_mean = self.fps_mean
            res.error = 0
        except Exception as ex:
            res.error = 1
            self.get_logger().error(f"Error getting device status: {ex}")
        return res

    def update_metrics(self):
        """Update all system metrics.
        """
        self.update_cpu_load()
        self.update_cpu_temp()
        self.update_cpu_freq()
        self.update_memory_usage()
        self.update_free_disk()
        self.update_latency_statistics()

    def update_cpu_load(self):
        """Function to update CPU utilization percentage using psutil."""
        try:
            # Use interval=1 for more accurate reading with less frequent calls
            self.cpu_percent = psutil.cpu_percent(interval=0.2)
            self.get_logger().debug(f"CPU utilization: {self.cpu_percent:.1f}%")
        except Exception as ex:
            self.get_logger().error(f"Failed to get CPU utilization: {ex}")

    def _find_temp_sensor_path(self):
        """Find the best temperature sensor path once at startup."""
        try:
            temps = psutil.sensors_temperatures()
            if 'coretemp' in temps:
                return ('psutil', 'coretemp', 0)
            elif 'cpu_thermal' in temps:
                return ('psutil', 'cpu_thermal', 0)
            elif temps:
                first_sensor = list(temps.keys())[0]
                return ('psutil', first_sensor, 0)
            else:
                # Check if thermal zone file exists
                import os
                if os.path.exists('/sys/class/thermal/thermal_zone0/temp'):
                    return ('file', '/sys/class/thermal/thermal_zone0/temp', None)
        except Exception:
            pass
        return None

    def update_cpu_temp(self):
        """Function to update CPU temperature using cached sensor path."""
        try:
            if not self.temp_sensor_path:
                self.cpu_temp = 0.0
                return

            method, path, index = self.temp_sensor_path

            if method == 'psutil':
                temps = psutil.sensors_temperatures()
                if path in temps and len(temps[path]) > index:
                    self.cpu_temp = temps[path][index].current
                else:
                    self.cpu_temp = 0.0
            elif method == 'file':
                with open(path, 'r') as f:
                    self.cpu_temp = float(f.read().strip()) / 1000.0

            self.get_logger().debug(f"CPU temperature: {self.cpu_temp:.1f}°C")
        except Exception as ex:
            self.get_logger().error(f"Failed to get CPU temperature: {ex}")
            self.cpu_temp = 0.0

    def update_cpu_freq(self):
        """Function to update CPU frequency information using psutil.
        """
        try:
            # Get CPU frequency information
            freq = psutil.cpu_freq()
            if freq:
                self.cpu_freq = freq.current
                self.cpu_freq_max = freq.max if freq.max else self.cpu_freq
                self.get_logger().debug(f"CPU frequency updated: {self.cpu_freq:.1f}MHz / {self.cpu_freq_max:.1f}MHz")
            else:
                # Try reading from /proc/cpuinfo as fallback
                try:
                    with open('/proc/cpuinfo', 'r') as f:
                        for line in f:
                            if line.startswith('cpu MHz'):
                                self.cpu_freq = float(line.split(':')[1].strip())
                                break
                    self.get_logger().debug(f"CPU frequency updated (fallback): {self.cpu_freq:.1f}MHz")
                except:
                    self.get_logger().debug("CPU frequency information not available")
        except Exception as ex:
            self.get_logger().error(f"Failed to get CPU frequency: {ex}")

    def update_memory_usage(self):
        """Function to update memory usage percentage using psutil.
        """
        try:
            # Get virtual memory statistics
            memory = psutil.virtual_memory()
            # Calculate memory usage as percentage
            self.memory_usage = memory.percent
            self.get_logger().debug(f"Memory usage updated: {self.memory_usage}%")
        except Exception as ex:
            self.get_logger().error(f"Failed to get memory usage: {ex}")

    def update_free_disk(self):
        """Function to update free disk space as percentage using psutil.
        """
        try:
            # Get disk usage for the root filesystem
            disk = psutil.disk_usage('/')

            # Calculate free disk space as percentage (disk.percent is usage percentage)
            free_percent = 100.0 - disk.percent
            self.free_disk = free_percent

            self.get_logger().debug(f"Free disk space updated: {self.free_disk:.1f}%")
        except Exception as ex:
            self.get_logger().error(f"Failed to get free disk space: {ex}")
            self.free_disk = 0.0

    def update_latency_statistics(self):
        """Get statistics for the latency values - update less frequently."""
        if not self.latency_history:
            return

        # Get basic statistics in O(1) time
        self.latency_stats["mean"] = self.latency_history.get_mean()
        self.latency_stats["p95"] = self.latency_history.get_percentile(0.95)

        # Calculate FPS in O(1) time
        self.fps_mean = self.latency_history.get_fps()

    def publish_status(self):
        """Publish the current device status metrics.
        """
        try:
            msg = DeviceStatusMsg()
            msg.cpu_percent = self.cpu_percent
            msg.cpu_temp = self.cpu_temp
            msg.cpu_freq = self.cpu_freq
            msg.cpu_freq_max = self.cpu_freq_max
            msg.memory_usage = self.memory_usage
            msg.free_disk = self.free_disk
            msg.latency_mean = self.latency_stats["mean"]
            msg.latency_p95 = self.latency_stats["p95"]
            msg.fps_mean = self.fps_mean

            self.status_publisher.publish(msg)
            self.get_logger().debug("Published device status update")
        except Exception as ex:
            self.get_logger().error(f"Error publishing device status: {ex}")


def main(args=None):

    node = None
    try:
        rclpy.init(args=args)
        node = DeviceStatusNode()
        executor = MultiThreadedExecutor()
        rclpy.spin(node, executor)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        if node:
            node.get_logger().error(f"Error in DeviceStatusNode: {e}")
    finally:
        if node:
            node.get_logger().info("Device Status Node shutting down")
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
