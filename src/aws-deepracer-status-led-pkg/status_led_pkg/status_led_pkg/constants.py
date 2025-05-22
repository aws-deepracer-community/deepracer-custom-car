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

# Base path of the GPIO ports.
GPIO_ROOT_PATH = "/sys/class/gpio"

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
    elif os.path.exists("/proc/device-tree/model") and "Raspberry Pi 4" in open("/proc/device-tree/model").read():
        return SystemType.RPI4
    elif os.path.exists("/proc/device-tree/model") and "Raspberry Pi 5" in open("/proc/device-tree/model").read():
        return SystemType.RPI5

SYSTEM_TYPE = get_system_type()

def get_led_ports():
    """Status light LED GPIO port matrix.
       Cols: led indices; rows: r, g, b channel ports.
    """

    if SYSTEM_TYPE == SystemType.DR:
        return (
            (448, 447, 437),
            (446, 445, 443),
            (450, 457, 458)
        )
    elif SYSTEM_TYPE == SystemType.RPI4:
        return (
            (488+7, 488+8, 488+9),
            (488+10, 488+11, 488+12),
            (488+13, 488+14, 488+15))
    elif SYSTEM_TYPE == SystemType.RPI4:
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
