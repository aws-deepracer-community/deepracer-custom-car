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
led_control.py

This module creates the LEDControl class which manages the R, G, B channel ports
for specific LED and provides a combined functionality to access their GPIO ports.
"""

from status_led_pkg import (constants,
                            gpio_module, gpiod_module)

#########################################################################################
# LED control class.


class LEDControl:
    """LED control class responsible for managing the R,G,B channels of the status led light
       for the specific index.
    """

    def __init__(self, index, logger):
        """Create the LEDControl object.

        Args:
            index (int): Index identifying the Status LED light.
            logger (rclpy.rclpy.impl.rcutils_logger.RcutilsLogger):
                Logger object of the status_led_node.
        """

        if constants.SYSTEM_TYPE == constants.SystemType.DR:
            # Create the specific GPIO objects for r, g, b channels.
            self.r = gpio_module.GPIO(constants.GPIO_ROOT_PATH,
                                      constants.LED_PORTS[index][0],
                                      logger)
            self.g = gpio_module.GPIO(constants.GPIO_ROOT_PATH,
                                      constants.LED_PORTS[index][1],
                                      logger)
            self.b = gpio_module.GPIO(constants.GPIO_ROOT_PATH,
                                      constants.LED_PORTS[index][2],
                                      logger)
        else:
            # Create the specific GPIO objects for r, g, b channels.
            self.r = gpiod_module.GPIOD(constants.GPIO_ROOT_PATH, 
                                        constants.LED_PORTS[index][0],
                                        logger)
            self.g = gpiod_module.GPIOD(constants.GPIO_ROOT_PATH, 
                                        constants.LED_PORTS[index][1],
                                        logger)
            self.b = gpiod_module.GPIOD(constants.GPIO_ROOT_PATH, 
                                        constants.LED_PORTS[index][2],
                                        logger)

    def __enter__(self):
        """Called when the LEDControl object is created using the 'with' statement.

        Returns:
           LEDControl : self object returned.
        """
        # Enable all the channels.
        self.enable()
        return self

    def __exit__(self):
        """Called when the object is destroyed.
        """
        # Disable all the channels.
        self.disable()

    def enable(self):
        """Wrapper function to enable the r, g, b channel ports.
        """
        self.r.enable()
        self.g.enable()
        self.b.enable()

    def disable(self):
        """Wrapper function to disable the r, g, b channel ports.
        """
        self.r.disable()
        self.g.disable()
        self.b.disable()

    def on(self):
        """Wrapper function to set value as 1 for the r, g, b channel ports.
        """
        self.r.on()
        self.g.on()
        self.b.on()

    def off(self):
        """Wrapper function to set value as 0 for the r, g, b channel ports.
        """
        self.r.off()
        self.g.off()
        self.b.off()

    def rgb(self, color):
        """Wrapper function to set specific values for the r, g, b channel ports.

        Args:
            color (list): List of values to be set for the ports.
        """
        self.r.set(color[0])
        self.g.set(color[1])
        self.b.set(color[2])
