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
device_info_node.py

This module creates the device_info_node which is responsible to provide the hardware
version of the DeepRacer device and software version of aws-deepracer-core package.
It provides services and functions to find out the current hardware and software version
and log the secure boot information.

The node defines:
    get_device_info_service: A service that is called to get the DeepRacer hardware and
                             software version information.
"""

import apt
import subprocess
import rclpy
from rclpy.node import Node

from deepracer_interfaces_pkg.srv import GetDeviceInfoSrv
from device_info_pkg import (constants,
                             gpio_module)


#########################################################################################
# DeviceInfoNode


class DeviceInfoNode(Node):
    """Node responsible for retrieving DeepRacer hardware and software version information.
    """

    def __init__(self):
        """Create a DeviceInfoNode.
        """
        super().__init__("device_info_node")

        # Apt cache.
        self.apt_cache = apt.Cache()

        # Variables to store the version and secure boot details.
        self.hardware_version = None
        self.software_version = None
        self.sb = None
        self.os_version = None
        self.cpu_model = None
        self.ros_distribution = None
        self.ram_amount = None
        self.disk_amount = None

        # Initialize the variables.
        self.load_hardware_version()
        self.load_software_version()
        self.load_sb()
        self.load_os_version()
        self.load_cpu_model()
        self.load_ros_distribution()
        self.load_ram_amount()
        self.load_disk_amount()

        # Service to get the DeepRacer hardware and software version details.
        self.get_device_info_service = self.create_service(GetDeviceInfoSrv,
                                                           constants.GET_DEVICE_INFO_SERVICE_NAME,
                                                           self.get_device_info)

        # Heartbeat timer.
        self.timer_count = 0
        self.timer = self.create_timer(5.0, self.timer_callback)

    def timer_callback(self):
        """Heartbeat function to keep the node alive.
        """
        self.get_logger().debug(f"Timer heartbeat {self.timer_count}")
        self.timer_count += 1

    def get_device_info(self, req, res):
        """Callback for the get_device_info service. Returns the hardware and software
           version details.

        Args:
            req (GetDeviceInfoSrv.Request): No request data passed.
            res (GetDeviceInfoSrv.Response): Response object with hardware_version(str)
                                             software_version(str) and error(int) flag.

        Returns:
            GetDeviceInfoSrv.Response: Response object with hardware_version(str)
                                       software_version(str) and error(int) flag.
        """
        self.get_logger().info("get_device_info")
        try:
            # Logging the secure boot info
            self.get_secure_boot_info()
            hw_version = self.get_hardware_version()
            sw_version = self.get_software_version()
            os_version = self.get_os_version()
            ros_distribution = self.get_ros_distribution()
            cpu_model = self.get_cpu_model()
            ram_amount = self.get_ram_amount()
            disk_amount = self.get_disk_amount()
            res.hardware_version = hw_version if hw_version else "--"
            res.software_version = sw_version if sw_version else "--"
            res.os_version = os_version if os_version else "--"
            res.cpu_model = cpu_model if cpu_model else "--"
            res.ros_distro = ros_distribution if ros_distribution else "--"
            res.ram_amount = ram_amount if ram_amount else "--"
            res.disk_amount = disk_amount if disk_amount else "--"
            res.error = 0
        except Exception:
            res.error = 1
            self.get_logger().error("Error while getting revision info")
        return res

    def load_sb(self):
        """Function to load the secure boot varible based on the result of the od command executed.
        """
        cmd = constants.SECURE_BOOT_CMD
        try:
            proc = subprocess.Popen(cmd.split(),
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT,
                                    universal_newlines=True)
            stdout = str(proc.communicate()[0]).split()
            if len(stdout) >= 3:
                if stdout[2].strip() == "1":
                    self.sb = "on"
                else:
                    self.sb = "off"
                self.get_logger().info(f"Loading secure boot information: {self.sb}")
            else:
                self.get_logger().error("od command did not return right values")
        except Exception as ex:
            self.get_logger().error(f"Failed to execute secure boot info cmd: {cmd} err:{ex}")

    def load_hardware_version(self):
        """Function to load the hardware version variable based on the board ids on the
           DeepRacer device.
        """
        base_path = constants.GPIO_BASE_PATH
        board_id0 = None
        board_id1 = None
        try:
            if constants.SYSTEM_TYPE == constants.SystemType.DR:
                board1 = gpio_module.GPIO(base_path, 383, self.get_logger(), direction="in")
                if board1.enable():
                    board_id1 = board1.get()
                    self.get_logger().info(f"board_id1: {board_id1}")

                board0 = gpio_module.GPIO(base_path, 387, self.get_logger(), direction="in")
                if (board_id1 is not None) and board0.enable():
                    board_id0 = board0.get()
                    self.get_logger().info(f"board_id0: {board_id0}")

                if (board_id1 is not None) and (board_id0 is not None):
                    hardware_version = ""
                    if board_id1 == "0":
                        if board_id0 == "0":
                            hardware_version = "DeepRacer R1.0"
                        else:
                            hardware_version = "DeepRacer R1.1"
                    else:
                        if board_id0 == "0":
                            hardware_version = "DeepRacer R2.0"
                        else:
                            hardware_version = "DeepRacer R2.1"

                    self.hardware_version = hardware_version
                    self.get_logger().info(f"Loading Hardware version: {self.hardware_version}")
            else:
                # Check if a device tree is available (Raspberry Pi)
                model_path = "/sys/firmware/devicetree/base/model"
                try:
                    with open(model_path, "r") as model_file:
                        self.hardware_version = model_file.read().strip()
                        self.get_logger().info(f"Loading Hardware version from device tree: {self.hardware_version}")
                        return
                except FileNotFoundError:
                    self.get_logger().error(f"Device tree base model file not found at {model_path}")
                except Exception as ex:
                    self.get_logger().error(f"Error reading device tree base model file: {ex}")
                self.get_logger().error("Could not load the hardware version")
        except Exception as ex:
            self.get_logger().error(f"Error while loading hardware version: {ex}")

    def load_software_version(self):
        """Function to load the software version variable based on the apt installed package
           version for aws-deepracer-core pacakge.
        """
        try:
            if constants.AWS_DEEPRACER_CORE_PKG in self.apt_cache:
                deepracer_pkg = self.apt_cache[constants.AWS_DEEPRACER_CORE_PKG]
                current_installed_version = deepracer_pkg.installed
                self.software_version = current_installed_version.version
                self.get_logger().info(f"Loading Software version: {self.software_version}")
            else:
                self.software_version = None
                self.get_logger().error("Software not installed")
        except Exception as ex:
            self.get_logger().error(f"Error while loading software version: {ex}")

    def get_hardware_version(self):
        """Getter method to return the hardware version variable if loaded, else load it
           and return.

        Returns:
            str: Hardware version details.
        """
        self.get_logger().info("Getting the hardware version")
        if not self.hardware_version:
            self.load_hardware_version()
        self.get_logger().info(f"Hardware version: {self.hardware_version}")
        return self.hardware_version

    def get_software_version(self):
        """Getter method to return the software version variable if loaded, else load it
           and return.

        Returns:
            str: Software version details.
        """
        self.get_logger().info("Getting the software version")
        if not self.software_version:
            self.load_software_version()
        self.get_logger().info(f"Software version: {self.software_version}")
        return self.software_version

    def get_secure_boot_info(self):
        """Getter method to return the secure boot variable if loaded, else load it
           and return.

        Returns:
            str: Secure boot details.
        """
        self.get_logger().info("Getting the secure boot information")
        if not self.sb:
            self.load_sb()
        self.get_logger().info(f"Secure boot: {self.sb}")

    def load_os_version(self):
        """Function to load the OS version pretty name.
        """
        cmd = constants.OS_VERSION_CMD
        try:
            proc = subprocess.Popen(cmd,
                                    shell=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT,
                                    universal_newlines=True)
            stdout = str(proc.communicate()[0]).strip()
            self.os_version = stdout
            self.get_logger().info(f"Loading OS information: {self.os_version}")
        except Exception as ex:
            self.get_logger().error(f"Failed to execute os version cmd: {cmd} err:{ex}")

    def get_os_version(self):
        """Getter method to return the OS version if loaded, else load it
           and return.

        Returns:
            str: OS details.
        """
        self.get_logger().info("Getting the OS information")
        if not self.os_version:
            self.load_os_version()
        self.get_logger().info(f"OS: {self.os_version}")
        return self.os_version

    def load_cpu_model(self):
        """Function to load the CPU Model name.
        """
        cmd = constants.CPU_MODEL_CMD
        try:
            proc = subprocess.Popen(cmd,
                                    shell=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT,
                                    universal_newlines=True)
            stdout = str(proc.communicate()[0]).strip()
            self.cpu_model = stdout
            self.get_logger().info(f"Loading CPU model information: {stdout}")
        except Exception as ex:
            self.get_logger().error(f"Failed to execute CPU model version cmd: {cmd} err:{ex}")

    def get_cpu_model(self):
        """Getter method to return the CPU model if loaded, else load it
           and return.

        Returns:
            str: CPU Model details.
        """
        self.get_logger().info("Getting the CPU model information")
        if not self.cpu_model:
            self.load_cpu_model()
        self.get_logger().info(f"CPU: {self.cpu_model}")
        return self.cpu_model

    def load_ros_distribution(self):
        """Function to load the ROS distribution name.
        """
        cmd = constants.ROS_DISTRO_CMD
        try:
            proc = subprocess.Popen(cmd,
                                    shell=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT,
                                    universal_newlines=True)
            stdout = str(proc.communicate()[0]).strip()
            self.ros_distribution = "ROS2 " + stdout.capitalize()
            self.get_logger().info(f"Loading ROS distribution information: {self.ros_distribution}")
        except Exception as ex:
            self.get_logger().error(f"Failed to execute ROS distribution cmd: {cmd} err:{ex}")

    def get_ros_distribution(self):
        """Getter method to return the ROS distribution if loaded, else load it
           and return.

        Returns:
            str: ROS distribution details.
        """
        self.get_logger().info("Getting the ROS distribution information")
        if not self.ros_distribution:
            self.load_ros_distribution()
        self.get_logger().info(f"ROS Distribution: {self.ros_distribution}")
        return self.ros_distribution

    def load_ram_amount(self):
        """Function to load the total RAM amount in the system.
        """
        cmd = constants.RAM_AMOUNT_CMD
        try:
            proc = subprocess.Popen(cmd,
                                    shell=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT,
                                    universal_newlines=True)
            stdout = str(proc.communicate()[0]).strip()
            ram_float = float(stdout) / (1024)
            self.ram_amount = str(int(round(ram_float, 0))) + "GB"
            self.get_logger().info(f"Loading RAM amount information: {self.ram_amount}")
        except Exception as ex:
            self.get_logger().error(f"Failed to execute RAM amount cmd: {cmd} err:{ex}")
            self.ram_amount = None

    def get_ram_amount(self):
        """Getter method to return the total RAM amount if loaded, else load it
           and return.

        Returns:
            str: RAM amount in GB.
        """
        self.get_logger().info("Getting the RAM amount information")
        if not hasattr(self, 'ram_amount') or self.ram_amount is None:
            self.load_ram_amount()
        self.get_logger().info(f"RAM: {self.ram_amount}")
        return self.ram_amount

    def load_disk_amount(self):
        """Function to load the total disk space amount.
        """
        cmd = constants.DISK_AMOUNT_CMD
        try:
            proc = subprocess.Popen(cmd,
                                    shell=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT,
                                    universal_newlines=True)
            stdout = str(proc.communicate()[0]).strip()
            self.disk_amount = stdout
            self.get_logger().info(f"Loading disk amount information: {self.disk_amount}")
        except Exception as ex:
            self.get_logger().error(f"Failed to execute disk amount cmd: {cmd} err:{ex}")
            self.disk_amount = None

    def get_disk_amount(self):
        """Getter method to return the total disk space if loaded, else load it
           and return.

        Returns:
            str: Disk space amount.
        """
        self.get_logger().info("Getting the disk amount information")
        if not hasattr(self, 'disk_amount') or self.disk_amount is None:
            self.load_disk_amount()
        self.get_logger().info(f"Disk: {self.disk_amount}")
        return self.disk_amount


def main(args=None):

    try:
        rclpy.init(args=args)
        device_info_node = DeviceInfoNode()
        rclpy.spin(device_info_node)
        # Destroy the node explicitly
        # (optional - otherwise it will be done automatically
        # when the garbage collector destroys the node object)
        device_info_node.destroy_node()

    except KeyboardInterrupt:
        pass

    finally:
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
