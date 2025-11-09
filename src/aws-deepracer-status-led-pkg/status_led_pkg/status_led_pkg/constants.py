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

import os

from requests import get
from enum import Enum, auto

LED_SOLID_SERVICE_NAME = "led_solid"
LED_BLINK_SERVICE_NAME = "led_blink"

# Default LED index.
DEFAULT_LED_INDEX = 0

class SystemType(Enum):
    DR = auto()
    RPI4 = auto()
    RPI5 = auto()

def get_system_type():
    """Get if the system is a Raspberry Pi or not.
    """
    if os.path.exists("/sys/class/dmi/id/chassis_serial"):
        return SystemType.DR
    elif os.path.exists("/proc/device-tree/model"):
        with open("/proc/device-tree/model") as f:
            model = f.read()
        if any(x in model for x in ["Raspberry Pi 4", "Raspberry Pi Compute Module 4"]):
            return SystemType.RPI4
        elif any(x in model for x in ["Raspberry Pi 5", "Raspberry Pi Compute Module 5"]):
            return SystemType.RPI5

SYSTEM_TYPE = get_system_type()

def is_ubuntu_24_04():
    """Check if the system is running Ubuntu 24.04.
    """
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("VERSION_ID="):
                    version = line.split("=")[1].strip().strip('"')
                    return version == "24.04"
    except:
        pass
    return False

IS_UBUNTU_24_04 = is_ubuntu_24_04()

def get_gpio_root_path():
    """Get the GPIO root path based on the system type.
    """
    if SYSTEM_TYPE == SystemType.DR:
        return "/sys/class/gpio"
    elif SYSTEM_TYPE == SystemType.RPI4:
        return "/dev/gpiochip0"
    elif SYSTEM_TYPE == SystemType.RPI5:
        return "/dev/gpiochip4"

# Base path of the GPIO ports.
GPIO_ROOT_PATH = get_gpio_root_path()


def get_led_ports():
    """Status light LED GPIO port matrix.
       Cols: led indices; rows: r, g, b channel ports.
    """

    if SYSTEM_TYPE == SystemType.DR:
        # On Ubuntu 24.04, GPIO base changed from 434 to 512, requiring +78 offset
        offset = 78 if IS_UBUNTU_24_04 else 0
        return (
            (448 + offset, 447 + offset, 437 + offset),
            (446 + offset, 445 + offset, 443 + offset),
            (450 + offset, 457 + offset, 458 + offset)
        )
    elif SYSTEM_TYPE == SystemType.RPI4 or SYSTEM_TYPE == SystemType.RPI5:
        return (
            (9+0, 9+1, 9+2),
            (9+3, 9+4, 9+5),
            (9+6, 9+7, 9+8))


LED_PORTS = get_led_ports()


class SupportedLEDEffects():
    """Supported led effects.
    """
    SOLID_COLOR = 0
    TWO_COLOR_SIREN = 1


class LEDColors():
    """LED color values that are passed as part of led_blink and led_solid service calls.
    """
    RED = "red"
    GREEN = "green"
    BLUE = "blue"
    BLACK = "black"
    WHITE = "white"
    NO_COLOR = "no_color"
    ON = "on"


# R,G,B Channel mapping for each of the LED color values.
LED_COLOR_VALUES = {
    LEDColors.RED: (1, 0, 0),
    LEDColors.GREEN: (0, 1, 0),
    LEDColors.BLUE: (0, 0, 1),
    LEDColors.BLACK: (0, 0, 0),
    LEDColors.WHITE: (1, 1, 1),
    LEDColors.NO_COLOR: (0, 0, 0),
    LEDColors.ON: (1, 1, 1)
}
