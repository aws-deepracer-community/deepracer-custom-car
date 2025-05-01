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

import gpiod
from gpiod.line import Direction, Value

#########################################################################################
# GPIO access class using the modern gpiod interface for Raspberry Pi 5


class GPIO:
    """Class responsible to read and write to a GPIO port using the gpiod library.
    """
    def __init__(self, gpio_base_path, gpio, logger, direction="out"):
        """Create a GPIO object.

        Args:
            gpio_base_path (str): Deprecated, kept for API compatibility.
            gpio (int): GPIO pin number.
            logger (rclpy.rclpy.impl.rcutils_logger.RcutilsLogger):
                Logger object of the device_info_node.
            direction (str, optional): GPIO input/output direction. Defaults to "out".
        """
        self.gpio = gpio
        self.direction = Direction.OUTPUT if direction == "out" else Direction.INPUT
        self.logger = logger
        self.chip = None
        self.line = None
        self.chip_base_path = gpio_base_path
        
    def enable(self):
        """Enable the GPIO port by requesting a line from the GPIO chip.

        Returns:
            bool: True if successful else False.
        """
        try:
            # Get the default GPIO chip (typically gpiochip0 on RPi)
            self.chip = gpiod.Chip(self.chip_base_path)
            
            # For gpiod 2.3.0, the proper API is:
            self.line = self.chip.request_lines({
                self.gpio: gpiod.LineSettings(
                    direction=self.direction,
                    output_value=Value.INACTIVE  # Start with low output
                )
            }, consumer="deepracer-custom-car")
            
            return True
        except Exception as ex:
            self.logger.error(f"Error enabling GPIO port {self.gpio}: {ex}")
            return False

    def disable(self):
        """Disable the GPIO port by releasing the line.

        Returns:
            bool: True if successful else False.
        """
        try:
            if self.line:
                # Release automatically happens when line is deleted
                self.line = None
            
            if self.chip:
                self.chip.close()
                self.chip = None
            return True
        except Exception as ex:
            self.logger.error(f"Error disabling GPIO port {self.gpio}: {ex}")
            return False

    def set(self, value):
        """Helper method to write the value to the GPIO port.
        
        Args:
            value (int): 0 for low, 1 for high
        """
        try:
            if self.line:
                gpio_value = Value.ACTIVE if value else Value.INACTIVE
                self.line.set_value(self.gpio, gpio_value)
        except Exception as ex:
            self.logger.error(f"Error setting the value for GPIO port {self.gpio}: {ex}")

    def get(self):
        """Helper method to read the value from the GPIO port.
        
        Returns:
            str: "0" or "1" depending on the GPIO state
        """
        try:
            if self.line:
                value = self.line.get_value(self.gpio)
                return "1" if value == Value.ACTIVE else "0"
            return None
        except Exception as ex:
            self.logger.error(f"Error getting the value for GPIO port {self.gpio}: {ex}")
            return None

    def on(self):
        """Wrapper function to set the GPIO port to high.
        """
        self.set(1)

    def off(self):
        """Wrapper function to set the GPIO port to low.
        """
        self.set(0)