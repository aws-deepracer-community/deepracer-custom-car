#################################################################################
#   Copyright AWS DeepRacer Community. All Rights Reserved.                     #
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
car_config_api.py

API for reading and writing vehicle configuration settings. Settings are
persisted to /opt/aws/deepracer/config.json and are applied on the next
service restart via start_ros.sh.
"""

import json
import os

from flask import (Blueprint,
                   jsonify,
                   request)

from webserver_pkg import webserver_publisher_node

CAR_CONFIG_API_BLUEPRINT = Blueprint("car_config_api", __name__)

CONFIG_FILE_PATH = "/opt/aws/deepracer/config.json"

# Valid options for each setting
VALID_LOGGING_MODES = ["Never", "USBOnly", "Always"]
VALID_INFERENCE_ENGINES = ["TFLITE", "OV"]
VALID_INFERENCE_DEVICES = {
    "TFLITE": ["CPU"],
    "OV": ["CPU", "GPU", "MYRIAD"]
}
VALID_CAMERA_MODES = ["legacy", "modern"]
VALID_LOGGING_PROVIDERS = ["sqlite3", "mcap"]
VALID_STEERING_MODES = ["servo", "diffdrive"]

DEFAULT_CONFIG = {
    "logging": {
        "mode": "always",
        "provider": "sqlite3"
    },
    "camera": {
        "mode": "auto"
    },
    "inference": {
        "engine": "auto",
        "device": "auto"
    },
    "steering": {
        "mode": "servo"
    }
}


def _get_ros_distro():
    """Return the current ROS_DISTRO environment variable value."""
    return os.environ.get("ROS_DISTRO", "")


def _is_myriad_present():
    """Return True if an Intel Movidius Myriad X device is detected via lsusb."""
    import subprocess
    try:
        result = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=5)
        return "Intel Movidius MyriadX" in result.stdout
    except Exception:
        return False


def _get_capabilities():
    """Build the capabilities matrix based on the current system.

    Returns:
        dict: Available options for each configurable setting.
    """
    import platform
    is_foxy = _get_ros_distro() == "foxy"
    is_x86 = platform.machine() == "x86_64"

    ov_devices = []
    if is_x86:
        ov_devices.append("CPU")
    if is_foxy:
        ov_devices.append("GPU")
    if _is_myriad_present():
        ov_devices.append("MYRIAD")

    inference_devices = dict(VALID_INFERENCE_DEVICES)
    inference_devices["OV"] = ov_devices

    # Only advertise OV if at least one device is available
    inference_engines = [e for e in VALID_INFERENCE_ENGINES if e != "OV" or ov_devices]

    return {
        "camera_modes": ["legacy"] if is_foxy else ["legacy", "modern"],
        "logging_modes": ["Never", "USBOnly", "Always"],
        "logging_providers": ["sqlite3"] if is_foxy else ["sqlite3", "mcap"],
        "inference_engines": inference_engines,
        "inference_devices": inference_devices,
        "steering_modes": VALID_STEERING_MODES
    }


def _deep_merge(base, override):
    """Recursively merge override into base, only accepting known keys.

    Args:
        base (dict): Base dictionary with known structure.
        override (dict): Values to merge in.

    Returns:
        dict: Merged dictionary.
    """
    result = {k: (v.copy() if isinstance(v, dict) else v) for k, v in base.items()}
    for key, value in override.items():
        if key not in result:
            continue  # ignore unknown top-level keys
        if isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _read_config():
    """Read the config.json file, falling back to defaults for missing keys.

    Returns:
        dict: Current configuration.
    """
    import copy
    config = copy.deepcopy(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, "r") as f:
                stored = json.load(f)
            config = _deep_merge(config, stored)
        except (json.JSONDecodeError, IOError) as ex:
            webserver_publisher_node.get_webserver_node().get_logger().warning(
                f"Failed to read car config, using defaults: {ex}"
            )
    return config


def _write_config(config):
    """Persist the config dict to config.json.

    Args:
        config (dict): Configuration to write.
    """
    os.makedirs(os.path.dirname(CONFIG_FILE_PATH), exist_ok=True)
    with open(CONFIG_FILE_PATH, "w") as f:
        json.dump(config, f, indent=2)


def _validate_config(data, capabilities):
    """Validate the incoming config values against the capabilities matrix.

    Args:
        data (dict): Incoming nested config values to validate.
        capabilities (dict): Current system capabilities.

    Returns:
        tuple: (is_valid: bool, error_message: str | None)
    """
    logging_data = data.get("logging", {})
    camera_data = data.get("camera", {})
    inference_data = data.get("inference", {})
    steering_data = data.get("steering", {})

    if "mode" in logging_data:
        mode = logging_data["mode"]
        valid_lower = [m.lower() for m in VALID_LOGGING_MODES]
        if mode.lower() not in valid_lower:
            return False, f"Invalid logging.mode '{mode}'. Valid values: {VALID_LOGGING_MODES}"

    if "provider" in logging_data:
        provider = logging_data["provider"]
        if provider not in capabilities["logging_providers"]:
            return False, (
                f"logging.provider '{provider}' is not supported on this system. "
                f"Available: {capabilities['logging_providers']}"
            )

    if "mode" in camera_data:
        mode = camera_data["mode"]
        # 'auto' means auto-detect, which is always valid
        if mode != "auto" and mode not in capabilities["camera_modes"]:
            return False, (
                f"camera.mode '{mode}' is not supported on this system. "
                f"Available: {capabilities['camera_modes']} or 'auto'"
            )

    if "engine" in inference_data:
        engine = inference_data["engine"]
        # 'auto' means auto-detect
        if engine != "auto" and engine not in capabilities["inference_engines"]:
            return False, f"Invalid inference.engine '{engine}'. Valid values: {VALID_INFERENCE_ENGINES} or 'auto'"

    if "device" in inference_data:
        device = inference_data["device"]
        engine = inference_data.get("engine", "auto")
        if device != "auto" and engine != "auto":
            allowed_devices = VALID_INFERENCE_DEVICES.get(engine, [])
            if device not in allowed_devices:
                return False, (
                    f"inference.device '{device}' is not valid for engine '{engine}'. "
                    f"Allowed: {allowed_devices} or 'auto'"
                )
        elif device != "auto" and engine == "auto":
            all_devices = [d for devices in VALID_INFERENCE_DEVICES.values() for d in devices]
            if device not in all_devices:
                return False, f"Invalid inference.device '{device}'"

    if "mode" in steering_data:
        mode = steering_data["mode"]
        if mode not in VALID_STEERING_MODES:
            return False, (
                f"Invalid steering.mode '{mode}'. "
                f"Valid values: {VALID_STEERING_MODES}"
            )

    return True, None


@CAR_CONFIG_API_BLUEPRINT.route("/api/car_config", methods=["GET"])
def get_car_config():
    """API to get the current vehicle configuration and available options.

    Returns:
        dict: JSON with success status, current config, and capabilities matrix.
    """
    try:
        config = _read_config()
        capabilities = _get_capabilities()
        return jsonify({
            "success": True,
            "config": config,
            "capabilities": capabilities
        })
    except Exception as ex:
        webserver_publisher_node.get_webserver_node().get_logger().error(
            f"Failed to get car config: {ex}"
        )
        return jsonify({"success": False, "reason": str(ex)})


@CAR_CONFIG_API_BLUEPRINT.route("/api/car_config", methods=["POST"])
def set_car_config():
    """API to update vehicle configuration settings.

    The new settings are persisted to config.json and will take effect
    on the next service restart.

    Returns:
        dict: JSON with success status and the updated config.
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"success": False, "reason": "No JSON data provided"})

        capabilities = _get_capabilities()
        is_valid, error = _validate_config(data, capabilities)
        if not is_valid:
            return jsonify({"success": False, "reason": error})

        current = _read_config()
        current = _deep_merge(current, data)

        _write_config(current)

        webserver_publisher_node.get_webserver_node().get_logger().info(
            "Car configuration updated. Restart required for changes to take effect."
        )
        return jsonify({"success": True, "config": current})

    except Exception as ex:
        webserver_publisher_node.get_webserver_node().get_logger().error(
            f"Failed to set car config: {ex}"
        )
        return jsonify({"success": False, "reason": str(ex)})
