#!/usr/bin/env bash

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

source /opt/aws/deepracer/lib/setup.bash

if [ -f /opt/intel/openvino_2022/setupvars.sh ]; then
    source /opt/intel/openvino_2022/setupvars.sh
elif [ -f /opt/intel/openvino_2021/bin/setupvars.sh ]; then
    source /opt/intel/openvino_2021/bin/setupvars.sh
else
    echo "No OpenVINO found!"
    exit 1
fi

MYRIAD=$(lsusb | grep "Intel Movidius MyriadX")
if [ -n "${MYRIAD}" ]; then
    INFERENCE_ENGINE='inference_engine:=OV'
    INFERENCE_DEVICE='inference_device:=MYRIAD'
else
    INFERENCE_ENGINE='inference_engine:=TFLITE'
fi

if [ -f /sys/firmware/devicetree/base/model ] && grep -q "Raspberry Pi" /sys/firmware/devicetree/base/model; then
    BATTERY_DUMMY='battery_dummy:=True'
else
    BATTERY_DUMMY=''
fi

if [ -f /opt/aws/deepracer/logging.conf ]; then
    LOGGING_MODE="logging_mode:=$(cat /opt/aws/deepracer/logging.conf | grep mode | cut -d'=' -f2 | tr -d '[:space:]')"
    LOGGING_PROVIDER="logging_provider:=$(cat /opt/aws/deepracer/logging.conf | grep provider | cut -d'=' -f2 | tr -d '[:space:]')"
else
    LOGGING_MODE='logging_mode:=usbonly'
    LOGGING_PROVIDER='logging_provider:=sqlite3'
fi

ros2 launch deepracer_launcher deepracer_launcher.py ${INFERENCE_ENGINE} ${INFERENCE_DEVICE} ${BATTERY_DUMMY} ${LOGGING_MODE} ${LOGGING_PROVIDER}
