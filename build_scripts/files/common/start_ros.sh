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
fi

# Require jq for config.json parsing
if ! command -v jq &>/dev/null; then
    echo "ERROR: jq is not installed. Install it with: sudo apt-get install -y jq" >&2
    exit 1
fi

# Read configuration overrides from config.json
CONFIG_FILE='/opt/aws/deepracer/config.json'
if [ -f "${CONFIG_FILE}" ]; then
    CFG_LOGGING_MODE=$(jq -r '.logging.mode // empty' "${CONFIG_FILE}" 2>/dev/null)
    CFG_LOGGING_PROVIDER=$(jq -r '.logging.provider // empty' "${CONFIG_FILE}" 2>/dev/null)
    CFG_CAMERA_MODE=$(jq -r '.camera.mode // empty' "${CONFIG_FILE}" 2>/dev/null)
    CFG_CAMERA_ORIENTATION=$(jq -r '.camera.orientation // 0' "${CONFIG_FILE}" 2>/dev/null)
    CFG_GRAY_OVERLAY=$(jq -r '.camera.enable_gray_overlay // false' "${CONFIG_FILE}" 2>/dev/null)
    CFG_INFERENCE_ENGINE=$(jq -r '.inference.engine // empty' "${CONFIG_FILE}" 2>/dev/null)
    CFG_INFERENCE_DEVICE=$(jq -r '.inference.device // empty' "${CONFIG_FILE}" 2>/dev/null)
    CFG_STEERING_MODE=$(jq -r '.steering.mode // empty' "${CONFIG_FILE}" 2>/dev/null)
else
    CFG_LOGGING_MODE=''
    CFG_LOGGING_PROVIDER=''
    CFG_CAMERA_MODE=''
    CFG_CAMERA_ORIENTATION='0'
    CFG_GRAY_OVERLAY='false'
    CFG_INFERENCE_ENGINE=''
    CFG_INFERENCE_DEVICE=''
    CFG_STEERING_MODE=''
fi

# Determine inference engine and device
# Config overrides auto-detection; auto-detection priority: MYRIAD > OV/CPU (x86_64) > TFLITE
if [ -n "${CFG_INFERENCE_ENGINE}" ] && [ "${CFG_INFERENCE_ENGINE}" != "auto" ]; then
    INFERENCE_ENGINE="inference_engine:=${CFG_INFERENCE_ENGINE}"
    if [ -n "${CFG_INFERENCE_DEVICE}" ] && [ "${CFG_INFERENCE_DEVICE}" != "auto" ]; then
        INFERENCE_DEVICE="inference_device:=${CFG_INFERENCE_DEVICE}"
    else
        INFERENCE_DEVICE=''
    fi
else
    MYRIAD=$(lsusb | grep "Intel Movidius MyriadX")
    if [ -n "${MYRIAD}" ]; then
        INFERENCE_ENGINE='inference_engine:=OV'
        INFERENCE_DEVICE='inference_device:=MYRIAD'
    elif [ "$(uname -m)" == "x86_64" ]; then
        INFERENCE_ENGINE='inference_engine:=OV'
        INFERENCE_DEVICE='inference_device:=CPU'
    else
        INFERENCE_ENGINE='inference_engine:=TFLITE'
        INFERENCE_DEVICE=''
    fi
fi

# No support for battery sensor on Raspberry Pi
if [ -f /sys/firmware/devicetree/base/model ] && grep -q "Raspberry Pi" /sys/firmware/devicetree/base/model; then
    BATTERY_DUMMY='battery_dummy:=True'
else
    BATTERY_DUMMY=''
fi

# Determine camera mode
# Config overrides auto-detection; auto-detection: foxy -> legacy, others -> modern
if [ -n "${CFG_CAMERA_MODE}" ] && [ "${CFG_CAMERA_MODE}" != "auto" ]; then
    CAMERA_MODE="camera_mode:=${CFG_CAMERA_MODE}"
elif [ "$ROS_DISTRO" == "foxy" ]; then
    CAMERA_MODE=''
else
    CAMERA_MODE='camera_mode:=modern'
fi

# Determine camera orientation for modern/libcamera mode only.
# In auto mode we keep orientation hidden in UI, so only explicit modern mode enables this.
case "${CFG_CAMERA_ORIENTATION}" in
    180) CAMERA_ORIENTATION="camera_orientation:=180" ;;
    *) CAMERA_ORIENTATION="camera_orientation:=0" ;;
esac
if [ "${CFG_CAMERA_MODE}" != "modern" ]; then
    CAMERA_ORIENTATION=''
fi

# Determine logging configuration
LOGGING_MODE="logging_mode:=${CFG_LOGGING_MODE:-usbonly}"
LOGGING_PROVIDER="logging_provider:=${CFG_LOGGING_PROVIDER:-sqlite3}"

# Determine steering mode (no auto-detection; defaults to servo)
# Validate value; fall back to servo for unknown/corrupt config entries
case "${CFG_STEERING_MODE}" in
    servo|diffdrive) STEERING_MODE="steering_mode:=${CFG_STEERING_MODE}" ;;
    *) STEERING_MODE="steering_mode:=servo" ;;
esac

# Determine gray overlay setting
case "${CFG_GRAY_OVERLAY}" in
    true|True) GRAY_OVERLAY="enable_gray_overlay:=True" ;;
    *) GRAY_OVERLAY="enable_gray_overlay:=False" ;;
esac

# Check if the LiDAR is connected via UART
CP210X=$(lsusb | grep "CP210x UART Bridge")
if [ -n "${CP210X}" ]; then
    echo "RPLIDAR / UART Bridge found!"
    RPLIDAR="rplidar:=True"
else
    RPLIDAR="rplidar:=False"
    echo "RPLIDAR / UART Bridge not found!"
fi

CMD="ros2 launch deepracer_launcher deepracer_launcher.py"
for ARG in "${INFERENCE_ENGINE}" "${INFERENCE_DEVICE}" "${BATTERY_DUMMY}" "${LOGGING_MODE}" "${LOGGING_PROVIDER}" "${CAMERA_MODE}" "${CAMERA_ORIENTATION}" "${STEERING_MODE}" "${RPLIDAR}" "${GRAY_OVERLAY}"; do
    [ -n "${ARG}" ] && CMD="${CMD} ${ARG}"
done
echo "==> ${CMD}"
exec ${CMD}
