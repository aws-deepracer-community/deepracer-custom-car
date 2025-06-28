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
device_info.py

This is the module that holds the APIs required to get the hardware/software version,
sensor status and battery level information.
"""

from flask import Blueprint
from flask import jsonify

from deepracer_interfaces_pkg.srv import (GetDeviceInfoSrv,
                                          BatteryLevelSrv,
                                          SensorStatusCheckSrv)
from deepracer_interfaces_pkg.msg import DeviceStatusMsg
from webserver_pkg import webserver_publisher_node
from webserver_pkg.utility import call_service_sync

DEVICE_INFO_API_BLUEPRINT = Blueprint("device_info_api", __name__)


@DEVICE_INFO_API_BLUEPRINT.route("/api/get_device_info", methods=["GET"])
def get_device_info():
    """API to call the service to get the current hardware version of the
       DeepRacer vehicle and the software version of aws-deepracer-core package.

    Returns:
        dict: Execution status if the API call was successful, hardware and
              software version details and error reason if call fails.
    """
    try:
        webserver_node = webserver_publisher_node.get_webserver_node()
        webserver_node.get_logger().info("Providing hardware and software revision "
                                         "details as response")

        get_revision_info_req = GetDeviceInfoSrv.Request()
        get_revision_info_res = call_service_sync(webserver_node.get_revision_info_cli,
                                                  get_revision_info_req)
        if get_revision_info_res and get_revision_info_res.error == 0:
            data = {
                "hardware_version": get_revision_info_res.hardware_version,
                "software_version": get_revision_info_res.software_version,
                "cpu_model": get_revision_info_res.cpu_model,
                "os_version": get_revision_info_res.os_version,
                "disk_amount": get_revision_info_res.disk_amount,
                "ram_amount": get_revision_info_res.ram_amount,
                "ros_distro": get_revision_info_res.ros_distro,
                "success": True
            }
            webserver_node.get_logger().info(f"Hardware version: {data['hardware_version']}, "
                                             f"Software version: {data['software_version']}, "
                                             f"CPU model: {data['cpu_model']}, "
                                             f"OS version: {data['os_version']}, "
                                             f"Disk amount: {data['disk_amount']}, "
                                             f"RAM amount: {data['ram_amount']}, "
                                             f"ROS distro: {data['ros_distro']}")
        else:
            webserver_node.get_logger().error("Get device info service call failed")
            data = {
                "reason": "Error",
                "success": False
            }
        return jsonify(data)

    except Exception as ex:
        if (webserver_node is not None):
            webserver_node.get_logger().error(f"Unable to reach revision info server: {ex}")
        return jsonify(success=False, reason="Error")


@DEVICE_INFO_API_BLUEPRINT.route("/api/get_battery_level", methods=["GET"])
def get_battery_level():
    """API to call the service to get the current vehicle battery level
       information.

    Returns:
        dict: Execution status if the API call was successful, vehicle
              battery level details and error reason if call fails.
    """
    try:
        webserver_node = webserver_publisher_node.get_webserver_node()

        battery_level_req = BatteryLevelSrv.Request()
        battery_level_res = call_service_sync(webserver_node.battery_level_cli,
                                              battery_level_req)
        if battery_level_res:
            data = {
                "battery_level": battery_level_res.level,
                "success": True
            }
            webserver_node.get_logger().debug(f"Battery Level: {data['battery_level']}")
            return jsonify(data)
        else:
            return jsonify(success=False, reason="Error")
    except Exception as ex:
        if webserver_node is not None:
            webserver_node.get_logger().error(f"Unable to reach battery level server: {ex}")
        return jsonify(success=False, reason="Error")


@DEVICE_INFO_API_BLUEPRINT.route("/api/get_sensor_status", methods=["GET"])
def get_sensor_status():
    """API to call the service to get the sensor data status for camera and
       LiDAR sensors connected to the vehicle.

    Returns:
        dict: Execution status if the API call was successful, sensor status
              information and error reason if call fails.
    """
    try:
        data = {
            "camera_status": "checking",
            "stereo_status": "checking",
            "lidar_status": "checking",
            "success": True
        }
        webserver_node = webserver_publisher_node.get_webserver_node()
        sensor_status_req = SensorStatusCheckSrv.Request()
        sensor_status_res = call_service_sync(webserver_node.sensor_status_cli, sensor_status_req)
        if sensor_status_res and sensor_status_res.error == 0:
            data["camera_status"] = \
                "not_connected" if sensor_status_res.single_camera_status == 1 else "connected"
            data["stereo_status"] = \
                "not_connected" if sensor_status_res.stereo_camera_status == 1 else "connected"
            data["lidar_status"] = \
                "not_connected" if sensor_status_res.lidar_status == 1 else "connected"
        else:
            webserver_node.get_logger().error("Get sensor status service call failed")
            data["camera_status"] = "error"
            data["stereo_status"] = "error"
            data["lidar_status"] = "error"
    except Exception as ex:
        if (webserver_node is not None):
            webserver_node.get_logger().error("Unable to reach sensor status server: {ex}")
        data["camera_status"] = "error"
        data["stereo_status"] = "error"
        data["lidar_status"] = "error"
    finally:
        if webserver_node is not None:
            webserver_node.get_logger().info(f"Camera status: {data['camera_status']}, "
                                             f"Stereo status: {data['stereo_status']}, "
                                             f"Lidar status: {data['lidar_status']}")
        return jsonify(data)


def get_registered_apis():
    """Helper function that collects all registered API routes from the Flask application.

    Returns:
        list: List of registered API endpoints
    """
    from webserver_pkg.webserver import app
    api_routes = []
    for rule in app.url_map.iter_rules():
        # Only include API routes, excluding static files
        if "api" in rule.rule and "static" not in rule.rule:
            api_routes.append(rule.rule)
    return sorted(api_routes)


@DEVICE_INFO_API_BLUEPRINT.route("/api/supported_apis", methods=["GET"])
def get_supported_apis():
    """API to get a list of all supported API endpoints.

    Returns:
        dict: JSON object containing success status and list of supported APIs.
    """
    return jsonify({
        "success": True,
        "apis_supported": get_registered_apis()
    })


@DEVICE_INFO_API_BLUEPRINT.route("/api/get_device_status", methods=["GET"])
def get_device_status():
    """API to get the current system metrics including CPU load, temperature, memory usage, etc.

    This endpoint retrieves the latest metrics from the device_status_node via subscription
    to the DeviceStatusMsg topic.

    Returns:
        dict: JSON object containing device metrics and success status:
              - cpu_percent: CPU utilization percentage
              - cpu_temp: CPU temperature in Celsius
              - cpu_freq: Current CPU frequency in MHz
              - cpu_freq_max: Maximum CPU frequency in MHz
              - memory_usage: Memory utilization percentage
              - free_disk: Free disk space percentage
              - latency_mean: Mean latency in millisecondsz
              - latency_p95: 95th percentile latency in milliseconds
              - fps_mean: Mean frames per second
    """
    try:
        webserver_node = webserver_publisher_node.get_webserver_node()

        # Get the latest device status from the subscription data
        latest_device_status: DeviceStatusMsg = webserver_node.latest_device_status

        if latest_device_status is not None:
            data = {
                "cpu_percent": latest_device_status.cpu_percent,
                "cpu_temp": latest_device_status.cpu_temp,
                "cpu_freq": latest_device_status.cpu_freq,
                "cpu_freq_max": latest_device_status.cpu_freq_max,
                "memory_usage": latest_device_status.memory_usage,
                "free_disk": latest_device_status.free_disk,
                "latency_mean": latest_device_status.latency_mean,
                "latency_p95": latest_device_status.latency_p95,
                "fps_mean": latest_device_status.fps_mean,
                "success": True
            }
            webserver_node.get_logger().debug(
                f"Device status metrics: CPU: {data['cpu_percent']:.1f}%, "
                f"Temp: {data['cpu_temp']:.1f}°C, Mem: {data['memory_usage']:.1f}%, "
                f"Disk: {data['free_disk']:.1f}% free"
            )
        else:
            webserver_node.get_logger().error("No device status data available yet")
            data = {
                "reason": "No device status data available yet",
                "success": False
            }
        return jsonify(data)

    except Exception as ex:
        if webserver_node is not None:
            webserver_node.get_logger().error(f"Error retrieving device status: {ex}")
        return jsonify(success=False, reason=f"Error retrieving device status: {str(ex)}")
