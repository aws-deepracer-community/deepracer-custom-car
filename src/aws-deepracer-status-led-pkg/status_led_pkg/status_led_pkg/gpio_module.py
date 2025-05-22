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
gpio_module.py

This module creates the GPIO class which is responsible to provide enable/disable, set/get
and on/off functionality for required GPIO ports.
"""

import os

#########################################################################################
# GPIO access class.
# Add error handling on the client side


class GPIO:
    """Class responsible to read and write to a GPIO port.
    """
    def __init__(self, gpio_base_path, gpio, logger, direction="out"):
        """Create a GPIO object.

        Args:
            gpio_base_path (str): Base path to the GPIO port.
            gpio (int): GPIO port number.
            logger (rclpy.rclpy.impl.rcutils_logger.RcutilsLogger):
                Logger object of the status_led_node.
            direction (str, optional): GPIO input/output direction. Defaults to "out".
        """
        self.base_path = gpio_base_path
        self.gpio = gpio
        self.direction = direction
        self.logger = logger
        self.root_path = f"{gpio_base_path}/gpio{gpio}"
        self.value_path = f"{self.root_path}/value"

    def enable(self):
        """Enable the GPIO port by exporting the control of a GPIO to userspace and
           set the direction attribute.

        Returns:
            bool: True if successful else False.
        """
        try:
            if(not os.path.isdir(self.root_path)):
                with open(f"{self.base_path}/export", "w") as export:
                    export.write(str(self.gpio))
        except Exception as ex:
            self.logger.error(f"Error while writing to export for the GPIO port {self.gpio}: {ex}")
            return False

        try:
            with open(f"{self.root_path}/direction", "w") as direction:
                direction.write(self.direction)
        except Exception as ex:
            self.logger.error(f"Error while writing direction for the GPIO port {self.gpio}: {ex}")
            return False

        try:
            os.chmod(self.value_path, 766)
        except Exception as ex:
            self.logger.error("Error while changing access permissions of value file for the GPIO port"
                              f"{self.gpio}: {ex}")
            return False

        return True

    def disable(self):
        """Disable the GPIO port by unexporting the control of a GPIO to userspace.

        Returns:
            bool: True if successful else False.
        """
        try:
            with open(f"{self.base_path}/unexport", "w") as unexport:
                unexport.write(str(self.gpio))
        except Exception as ex:
            self.logger.error("Error while writing to unexport for the GPIO port "
                              f"{self.gpio}: {ex}")
            return False

        return True

    def set(self, Value):
        """Helper method to write the value attribute of the GPIO port.
        """
        try:
            with open(self.value_path, "w") as value:
                value.write(str(Value))
        except Exception as ex:
            self.logger.error("Error while setting the value for the GPIO port "
                              f"{self.gpio}: {ex}")

    def get(self):
        """Helper method to read the value attribute of the GPIO port.
        """
        try:
            with open(self.value_path, "r") as value:
                result = value.read()
                return str(result.strip())
        except Exception as ex:
            self.logger.error("Error while getting the value for the GPIO port "
                              f"{self.gpio}: {ex}")

    def on(self):
        """Wrapper function to write the value 1 to value attribute of GPIO port.
        """
        self.set(1)

    def off(self):
        """Wrapper function to write the value 0 to value attribute of GPIO port.
        """
        self.set(0)
