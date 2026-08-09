"""
camera_api.py

This module holds the APIs required to interact with camera settings in ROS 2 via parameters.
"""

import json
import os

from flask import Blueprint, jsonify, request

from rcl_interfaces.msg import Parameter, ParameterType, ParameterValue
from rcl_interfaces.srv import DescribeParameters, GetParameters, ListParameters, SetParameters
from webserver_pkg import webserver_publisher_node
from webserver_pkg.utility import call_service_sync


CAMERA_NODE_NAME = "/camera_pkg/camera"
PARAMETER_SERVICE_TIMEOUT = 5
CAMERA_SETTINGS_FILE_PATH = "/opt/aws/deepracer/camera.json"

CAMERA_PARAM_DENYLIST = {
    "camera",
    "camera_info_url",
    "format",
    "frame_id",
    "FrameDurationLimits",
    "height",
    "jpeg_quality",
    "orientation",
    "role",
    "sensor_mode",
    "use_node_time",
    "use_sim_time",
    "width",
}

CAMERA_API_BLUEPRINT = Blueprint("camera_api", __name__)

PARAMETER_TYPE_NAMES = {
    ParameterType.PARAMETER_BOOL: "boolean",
    ParameterType.PARAMETER_INTEGER: "integer",
    ParameterType.PARAMETER_DOUBLE: "double",
    ParameterType.PARAMETER_STRING: "string",
    ParameterType.PARAMETER_BYTE_ARRAY: "byte_array",
    ParameterType.PARAMETER_BOOL_ARRAY: "boolean_array",
    ParameterType.PARAMETER_INTEGER_ARRAY: "integer_array",
    ParameterType.PARAMETER_DOUBLE_ARRAY: "double_array",
    ParameterType.PARAMETER_STRING_ARRAY: "string_array",
}


def _logger():
    """Return the shared webserver logger when available."""
    node = webserver_publisher_node.get_webserver_node()
    if node is None:
        return None
    return node.get_logger()


def _parameter_service_name(service_name):
    """Return the fully-qualified service name for the camera node parameter API."""
    return f"{CAMERA_NODE_NAME}/{service_name}"


def _call_parameter_service(service_type, service_name, service_request):
    """Call a camera node parameter service using the shared webserver ROS node."""
    webserver_node = webserver_publisher_node.get_webserver_node()
    service_path = _parameter_service_name(service_name)
    client = webserver_node.create_client(service_type, service_path)
    try:
        if not client.wait_for_service(timeout_sec=1.0):
            webserver_node.get_logger().warn(f"Camera parameter service is unavailable: {service_path}")
            return None
        return call_service_sync(client, service_request, timeout=PARAMETER_SERVICE_TIMEOUT)
    finally:
        webserver_node.destroy_client(client)


def _parameter_value_to_python(parameter_value):
    """Convert an rcl_interfaces ParameterValue into a JSON-serializable value."""
    if parameter_value.type == ParameterType.PARAMETER_BOOL:
        return parameter_value.bool_value
    if parameter_value.type == ParameterType.PARAMETER_INTEGER:
        return parameter_value.integer_value
    if parameter_value.type == ParameterType.PARAMETER_DOUBLE:
        return parameter_value.double_value
    if parameter_value.type == ParameterType.PARAMETER_STRING:
        return parameter_value.string_value
    if parameter_value.type == ParameterType.PARAMETER_BYTE_ARRAY:
        return list(parameter_value.byte_array_value)
    if parameter_value.type == ParameterType.PARAMETER_BOOL_ARRAY:
        return list(parameter_value.bool_array_value)
    if parameter_value.type == ParameterType.PARAMETER_INTEGER_ARRAY:
        return list(parameter_value.integer_array_value)
    if parameter_value.type == ParameterType.PARAMETER_DOUBLE_ARRAY:
        return list(parameter_value.double_array_value)
    if parameter_value.type == ParameterType.PARAMETER_STRING_ARRAY:
        return list(parameter_value.string_array_value)
    return None


def _python_to_parameter_value(value):
    """Convert a JSON value into an rcl_interfaces ParameterValue."""
    parameter_value = ParameterValue()
    if isinstance(value, bool):
        parameter_value.type = ParameterType.PARAMETER_BOOL
        parameter_value.bool_value = value
    elif isinstance(value, int):
        parameter_value.type = ParameterType.PARAMETER_INTEGER
        parameter_value.integer_value = value
    elif isinstance(value, float):
        parameter_value.type = ParameterType.PARAMETER_DOUBLE
        parameter_value.double_value = value
    elif isinstance(value, str):
        parameter_value.type = ParameterType.PARAMETER_STRING
        parameter_value.string_value = value
    elif isinstance(value, list):
        _populate_array_parameter_value(parameter_value, value)
    else:
        raise ValueError(f"Unsupported parameter value type: {type(value).__name__}")
    return parameter_value


def _populate_array_parameter_value(parameter_value, value):
    """Populate an rcl_interfaces ParameterValue from a JSON array."""
    if not value:
        raise ValueError("Array parameter values must not be empty")
    if all(isinstance(item, bool) for item in value):
        parameter_value.type = ParameterType.PARAMETER_BOOL_ARRAY
        parameter_value.bool_array_value = value
    elif all(isinstance(item, int) and not isinstance(item, bool) for item in value):
        parameter_value.type = ParameterType.PARAMETER_INTEGER_ARRAY
        parameter_value.integer_array_value = value
    elif all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value):
        parameter_value.type = ParameterType.PARAMETER_DOUBLE_ARRAY
        parameter_value.double_array_value = [float(item) for item in value]
    elif all(isinstance(item, str) for item in value):
        parameter_value.type = ParameterType.PARAMETER_STRING_ARRAY
        parameter_value.string_array_value = value
    else:
        raise ValueError("Array parameter values must contain one supported type")


def _descriptor_metadata(descriptor):
    """Extract UI-friendly metadata from a ROS parameter descriptor."""
    metadata = {
        "read_only": descriptor.read_only,
        "description": descriptor.description,
    }
    if descriptor.integer_range:
        integer_range = descriptor.integer_range[0]
        metadata.update({
            "min": integer_range.from_value,
            "max": integer_range.to_value,
            "step": integer_range.step,
        })
    elif descriptor.floating_point_range:
        floating_point_range = descriptor.floating_point_range[0]
        metadata.update({
            "min": floating_point_range.from_value,
            "max": floating_point_range.to_value,
            "step": floating_point_range.step,
        })
    return metadata


def _camera_parameter_payload(name, parameter_value, descriptor):
    """Build a JSON payload for one camera parameter."""
    payload = {
        "name": name,
        "value": _parameter_value_to_python(parameter_value),
        "type": PARAMETER_TYPE_NAMES.get(parameter_value.type, "not_set"),
    }
    payload.update(_descriptor_metadata(descriptor))
    return payload


def _read_camera_settings():
    """Read pending camera settings from disk, if present."""
    if not os.path.exists(CAMERA_SETTINGS_FILE_PATH):
        return {}

    try:
        with open(CAMERA_SETTINGS_FILE_PATH, "r") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as ex:
        logger = _logger()
        if logger is not None:
            logger.warning(f"Failed to read camera settings from {CAMERA_SETTINGS_FILE_PATH}: {ex}")
        return {}


def _write_camera_settings(settings):
    """Persist pending camera settings to disk."""
    os.makedirs(os.path.dirname(CAMERA_SETTINGS_FILE_PATH), exist_ok=True)
    with open(CAMERA_SETTINGS_FILE_PATH, "w") as handle:
        json.dump(settings, handle, indent=2)


def _persist_camera_parameter(name, value):
    """Store a camera parameter value on disk for deferred application."""
    settings = _read_camera_settings()
    settings[name] = value
    _write_camera_settings(settings)


def _apply_pending_camera_parameters():
    """Apply any camera parameters that were queued while the camera node was unavailable."""
    pending_settings = _read_camera_settings()
    if not pending_settings:
        return []

    remaining_settings = {}
    applied_names = []
    for name in sorted(pending_settings):
        value = pending_settings[name]
        try:
            parameter_value = _python_to_parameter_value(value)
        except ValueError as ex:
            logger = _logger()
            if logger is not None:
                logger.warning(f"Skipping pending camera parameter {name}: {ex}")
            remaining_settings[name] = value
            continue

        set_request = SetParameters.Request()
        set_request.parameters = [Parameter(name=name, value=parameter_value)]
        set_response = _call_parameter_service(SetParameters, "set_parameters", set_request)
        if set_response is None:
            remaining_settings[name] = value
            continue

        result = set_response.results[0]
        if result.successful:
            applied_names.append(name)
        else:
            remaining_settings[name] = value

    _write_camera_settings(remaining_settings)
    return applied_names


def _is_exposed_camera_parameter(name, descriptor=None):
    """Return whether a camera parameter should be exposed through this API."""
    if name in CAMERA_PARAM_DENYLIST:
        return False
    if descriptor is not None and descriptor.read_only:
        return False
    return True


@CAMERA_API_BLUEPRINT.route("/api/camera/params", methods=["GET"])
def get_camera_params():
    """
    Returns a list of available camera parameters and their current values.
    Queries /camera_pkg/camera_node, which is provided by camera_ros.
    """
    _apply_pending_camera_parameters()

    list_request = ListParameters.Request()
    list_request.depth = ListParameters.Request.DEPTH_RECURSIVE
    list_response = _call_parameter_service(ListParameters, "list_parameters", list_request)
    if list_response is None:
        return jsonify({
            "status": "error",
            "message": f"Unable to query parameters from {CAMERA_NODE_NAME}"
        }), 503

    parameter_names = sorted(list_response.result.names)
    if not parameter_names:
        return jsonify({"status": "success", "params": []})

    get_request = GetParameters.Request(names=parameter_names)
    describe_request = DescribeParameters.Request(names=parameter_names)
    get_response = _call_parameter_service(GetParameters, "get_parameters", get_request)
    describe_response = _call_parameter_service(DescribeParameters, "describe_parameters", describe_request)
    if get_response is None or describe_response is None:
        return jsonify({
            "status": "error",
            "message": f"Unable to read parameter details from {CAMERA_NODE_NAME}"
        }), 503

    params = [
        _camera_parameter_payload(name, value, descriptor)
        for name, value, descriptor in zip(
            parameter_names,
            get_response.values,
            describe_response.descriptors,
        )
        if _is_exposed_camera_parameter(name, descriptor)
    ]
    return jsonify({"status": "success", "params": params})


@CAMERA_API_BLUEPRINT.route("/api/camera/param/<param_name>", methods=["POST"])
def set_camera_param(param_name):
    """
    Updates a specific camera parameter in ROS 2.
    """
    if param_name in CAMERA_PARAM_DENYLIST:
        return jsonify({
            "status": "error",
            "parameter": param_name,
            "message": "Parameter is not exposed for web configuration"
        }), 403

    request_body = request.get_json(silent=True)
    if not isinstance(request_body, dict):
        return jsonify({"status": "error", "message": "Request body must be JSON"}), 400

    new_value = request_body.get("value")
    if new_value is None:
        return jsonify({"status": "error", "message": "No value provided"}), 400

    try:
        parameter_value = _python_to_parameter_value(new_value)
    except ValueError as ex:
        return jsonify({"status": "error", "message": str(ex)}), 400

    set_request = SetParameters.Request()
    set_request.parameters = [Parameter(name=param_name, value=parameter_value)]
    set_response = _call_parameter_service(SetParameters, "set_parameters", set_request)
    if set_response is None:
        _persist_camera_parameter(param_name, new_value)
        return jsonify({
            "status": "success",
            "parameter": param_name,
            "new_value": new_value,
            "message": f"Parameter saved and will be applied when {CAMERA_NODE_NAME} is available"
        })

    result = set_response.results[0]
    if not result.successful:
        return jsonify({
            "status": "error",
            "parameter": param_name,
            "message": result.reason or "Parameter update was rejected"
        }), 400

    _persist_camera_parameter(param_name, new_value)
    _apply_pending_camera_parameters()
    return jsonify({
        "status": "success",
        "parameter": param_name,
        "new_value": new_value
    })
