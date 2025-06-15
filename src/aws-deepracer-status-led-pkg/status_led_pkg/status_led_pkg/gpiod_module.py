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
gpiod_module.py

This module creates the GPIO class which is responsible to provide enable/disable, set/get
and on/off functionality for required GPIO ports.
"""

import sys

# Check if gpiod is available
GPIOD_AVAILABLE = False
GPIOD_VERSION = 0  # 0=not available, 1=v1.x, 2=v2.x

try:
    import gpiod
    GPIOD_AVAILABLE = True
    
    # Detect gpiod version
    if hasattr(gpiod, 'line'):  # v2.x has gpiod.line module
        GPIOD_VERSION = 2
        from gpiod.line import Direction, Value
    else:  # v1.x
        GPIOD_VERSION = 1
except ImportError:
    GPIOD_AVAILABLE = False

#########################################################################################
# GPIO access class using the modern gpiod interface for Raspberry Pi 4 and 5


class GPIOD:
    """Class responsible to read and write to a GPIO port using the gpiod library.
    """

    def __init__(self, gpio_base_path, gpio, logger, direction="out"):
        """Create a GPIO object.

        Args:
            gpio_base_path (str): The GPIO Chip to connect to (e.g. /dev/gpiochip0).
            gpio (int): GPIO pin number.
            logger (rclpy.rclpy.impl.rcutils_logger.RcutilsLogger):
                Logger object of the device_info_node.
            direction (str, optional): GPIO input/output direction. Defaults to "out".
        """
        self.gpio = gpio
        self.logger = logger
        self.chip = None
        self.line = None
        self.chip_base_path = gpio_base_path
        self.direction = direction

        if not GPIOD_AVAILABLE:
            self.logger.error("GPIOD module requires the gpiod library to be installed")

    def enable(self):
        """Enable the GPIO port by requesting a line from the GPIO chip.

        Returns:
            bool: True if successful else False.
        """
        if not GPIOD_AVAILABLE:
            self.logger.error("GPIOD module not available")
            return False

        try:
            if GPIOD_VERSION == 2:
                # gpiod v2.x API
                self.chip = gpiod.Chip(self.chip_base_path)
                self.line = self.chip.request_lines({
                    self.gpio: gpiod.LineSettings(
                        direction=Direction.OUTPUT if self.direction == "out" else Direction.INPUT,
                        output_value=Value.INACTIVE  # Start with low output
                    )
                }, consumer="deepracer-custom-car")
            else:
                # gpiod v1.x API
                self.chip = gpiod.Chip(self.chip_base_path)
                if self.direction == "out":
                    self.line = self.chip.get_line(self.gpio)
                    self.line.request(consumer="deepracer-custom-car", 
                                     type=gpiod.LINE_REQ_DIR_OUT, 
                                     default_val=0)
                else:
                    self.line = self.chip.get_line(self.gpio)
                    self.line.request(consumer="deepracer-custom-car",
                                     type=gpiod.LINE_REQ_DIR_IN)
            return True
        except Exception as ex:
            self.logger.error(f"Error enabling GPIO port {self.gpio}: {ex}")
            return False

    def disable(self):
        """Disable the GPIO port by releasing the line.

        Returns:
            bool: True if successful else False.
        """
        if not GPIOD_AVAILABLE:
            return False

        try:
            if self.line:
                if GPIOD_VERSION == 1:
                    self.line.release()
                # In v2.x, release automatically happens when line is deleted
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
        if not GPIOD_AVAILABLE:
            return

        try:
            if self.line:
                if GPIOD_VERSION == 2:
                    gpio_value = Value.ACTIVE if value else Value.INACTIVE
                    self.line.set_value(self.gpio, gpio_value)
                else:
                    # v1.x API
                    self.line.set_value(1 if value else 0)
        except Exception as ex:
            self.logger.error(f"Error setting the value for GPIO port {self.gpio}: {ex}")

    def get(self):
        """Helper method to read the value from the GPIO port.

        Returns:
            str: "0" or "1" depending on the GPIO state
        """
        if not GPIOD_AVAILABLE:
            return None

        try:
            if self.line:
                if GPIOD_VERSION == 2:
                    value = self.line.get_value(self.gpio)
                    return "1" if value == Value.ACTIVE else "0"
                else:
                    # v1.x API
                    value = self.line.get_value()
                    return "1" if value == 1 else "0"
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
