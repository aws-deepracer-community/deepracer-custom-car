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

from deepracer_interfaces_pkg.srv import GetDeviceStatusSrv
from deepracer_interfaces_pkg.msg import DeviceStatusMsg
from device_info_pkg import constants


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
        self.free_disk = 0.0  # Now a float percentage instead of string

        # Initialize metrics on startup
        self.update_metrics()

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
        self.update_timer = self.create_timer(5.0, self.update_timer_callback)

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
                f"Memory usage: {self.memory_usage:.1f}% | Free disk: {self.free_disk:.1f}%")

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

    def update_cpu_load(self):
        """Function to update CPU utilization percentage using psutil.
        """
        try:
            # Get overall CPU utilization as percentage
            self.cpu_percent = psutil.cpu_percent(interval=0.1)

            self.get_logger().debug(f"CPU utilization updated: {self.cpu_percent}%")
        except Exception as ex:
            self.get_logger().error(f"Failed to get CPU utilization: {ex}")

    def update_cpu_temp(self):
        """Function to update CPU temperature using psutil.
        """
        try:
            # Try to get CPU temperature via psutil
            temps = psutil.sensors_temperatures()
            # Different systems report temperature under different keys
            # First try 'coretemp' which is common on Intel systems
            if 'coretemp' in temps:
                # Take the first core temperature as representative
                self.cpu_temp = temps['coretemp'][0].current
            # Then try 'cpu_thermal' which is common on ARM/Raspberry Pi
            elif 'cpu_thermal' in temps:
                self.cpu_temp = temps['cpu_thermal'][0].current
            # Try any other available temperature sensor
            elif temps:
                # Get the first available sensor's first reading
                first_sensor = list(temps.keys())[0]
                self.cpu_temp = temps[first_sensor][0].current
            else:
                # If no temperature sensors available through psutil, try reading directly
                try:
                    with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                        self.cpu_temp = float(f.read().strip()) / 1000.0
                except:
                    self.cpu_temp = 0.0
                    self.get_logger().debug("CPU temperature not available")
            self.get_logger().debug(f"CPU temperature updated: {self.cpu_temp}°C")
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

            self.status_publisher.publish(msg)
            self.get_logger().debug("Published device status update")
        except Exception as ex:
            self.get_logger().error(f"Error publishing device status: {ex}")


def main(args=None):
    node = None
    try:
        rclpy.init(args=args)
        node = DeviceStatusNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as ex:
        if node:
            node.get_logger().error(f"Device Status Node error: {ex}")
    finally:
        if node:
            # Single shutdown log line
            node.get_logger().info("Device Status Node shutting down")
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
