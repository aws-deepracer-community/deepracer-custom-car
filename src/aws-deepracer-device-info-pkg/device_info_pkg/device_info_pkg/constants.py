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

from enum import Enum, auto
import os


GET_DEVICE_INFO_SERVICE_NAME = "get_device_info"

GET_DEVICE_STATUS_SERVICE_NAME = "get_device_status"

# Topic names
DEVICE_STATUS_TOPIC_NAME = "device_status"
SERVO_LATENCY_TOPIC_NAME = "/servo_pkg/latency"

# Core package whose version is considered as DeepRacer software version.
AWS_DEEPRACER_CORE_PKG = "aws-deepracer-core"

# Base path of the GPIO ports.
GPIO_BASE_PATH = "/sys/class/gpio"

SECURE_BOOT_CMD = "od -An -t u2 /sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c"

OS_VERSION_CMD = "bash -c 'source /etc/os-release && echo $PRETTY_NAME'"

CPU_MODEL_CMD = "lscpu | grep '^Model name' | awk -F: '{print $2}' | sed 's/^ *//' | sed 's/(R)//g' | sed 's/(TM)//g' | sed 's/Cortex/Arm Cortex/g'"

ROS_DISTRO_CMD = "bash -c 'echo $ROS_DISTRO'"

DISK_AMOUNT_CMD = "df / -h | awk '{print $2 \"B\"}' | tail -1"

RAM_AMOUNT_CMD = "free -m | grep 'Mem' | awk '{print $2}'"

# Latency measurement
MAX_LATENCY_HISTORY = 50
LATENCY_SAMPLE_RATE = 5
DEVICE_STATUS_TIMING = 2.5  # seconds

# System type
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
    """Check if the system is running Ubuntu 24.04 (noble).
    """
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("VERSION_CODENAME="):
                    codename = line.split("=")[1].strip().strip('"')
                    return codename == "noble"
                elif line.startswith("VERSION_ID="):
                    version = line.split("=")[1].strip().strip('"')
                    if version == "24.04":
                        return True
    except:
        pass
    return False


IS_UBUNTU_24_04 = is_ubuntu_24_04()


def get_board_id_gpio_pins():
    """Get the GPIO pin numbers for board ID detection.
       On Ubuntu 24.04, GPIO base changed from 357 to 590, requiring +233 offset.
    
    Returns:
        tuple: (board_id1_pin, board_id0_pin)
    """
    if SYSTEM_TYPE == SystemType.DR and IS_UBUNTU_24_04:
        # Ubuntu 24.04: base 590, so 383+233=616 and 387+233=620
        return (616, 620)
    else:
        # Older systems: base 357
        return (383, 387)


BOARD_ID_PINS = get_board_id_gpio_pins()
