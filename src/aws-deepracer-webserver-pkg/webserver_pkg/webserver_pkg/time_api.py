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
time_api.py

This is the module that controls the car time and timezone.
"""

import time
from flask import (Blueprint,
                   jsonify,
                   request)

from webserver_pkg import utility
from webserver_pkg import webserver_publisher_node

TIME_API_BLUEPRINT = Blueprint("time_api", __name__)


@TIME_API_BLUEPRINT.route("/api/get_time", methods=["GET"])
def get_time_info():
    """API called to execute commands to check if SSH is enabled.
       This will populate the ssh enabled radio button in the UI.

    Returns:
        dict: Execution status if the API call was successful, flag to indicate
              if ssh is enabled and with error reason if call fails.
    """
    try:
        webserver_node = webserver_publisher_node.get_webserver_node()
        webserver_node.get_logger().info("Providing time and timezone information as response")

        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        current_timezone = time.tzname[time.daylight] if time.daylight else time.tzname[0]

        return jsonify(success=True,
                       time=current_time,
                       timezone=current_timezone)

    except Exception as ex:
        webserver_node.get_logger().error(f"Failed check of time and timezone: {ex}")
        return jsonify(success=False, reason="Error")


@TIME_API_BLUEPRINT.route("/api/set_timezone", methods=["POST"])
def set_timezone():
    """API called to set the timezone of the car.

    Returns:
        dict: Execution status if the API call was successful, with error reason if call fails.
    """
    try:
        webserver_node = webserver_publisher_node.get_webserver_node()

        data = request.get_json()
        timezone = data.get("timezone", "")

        if not timezone:
            return jsonify(success=False, reason="Timezone not provided")

        webserver_node.get_logger().info(f"Setting timezone to {timezone}")

        # Validate timezone by checking if it exists in the system's timezone list
        try:
            result = utility.execute("timedatectl list-timezones", shlex_split=True)
            valid_timezones = result.stdout.strip().split('\n') if result.stdout else []

            if timezone not in valid_timezones:
                return jsonify(success=False, reason=f"Invalid timezone: {timezone}")
        except Exception as validation_ex:
            webserver_node.get_logger().warning(f"Failed to validate timezone list: {validation_ex}")
            # Continue with the operation if validation fails - let timedatectl handle the error

        result = utility.execute(f"timedatectl set-timezone {timezone}", shlex_split=True)
        if result.returncode == 0:
            return jsonify(success=True, reason="Timezone updated successfully")
        else:
            webserver_node.get_logger().error(f"Failed to set timezone: {result.stderr}")
            return jsonify(success=False, reason=f"Failed to set timezone: {result.stderr}")

    except Exception as ex:
        webserver_node.get_logger().error(f"Failed to set timezone: {ex}")
        return jsonify(success=False, reason="Error")
