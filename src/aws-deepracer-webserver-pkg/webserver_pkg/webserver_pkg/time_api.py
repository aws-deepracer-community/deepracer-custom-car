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
import datetime
from flask import (Blueprint,
                   jsonify,
                   request)

from webserver_pkg import utility
from webserver_pkg import webserver_publisher_node
import subprocess

_timezone_changed = False


TIME_API_BLUEPRINT = Blueprint("time_api", __name__)


@TIME_API_BLUEPRINT.route("/api/get_time", methods=["GET"])
def get_time_info():
    """API called to get current time and timezone information.

    Returns:
        dict: Execution status if the API call was successful, current time,
              timezone name, abbreviation, and UTC offset, with error reason if call fails.
    """
    global _timezone_changed

    try:
        webserver_node = webserver_publisher_node.get_webserver_node()
        webserver_node.get_logger().info("Providing time and timezone information as response")

        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        # Get timezone name (e.g., Europe/Berlin)
        timezone_name = _get_timezone_name(webserver_node)

        # Get timezone abbreviation (e.g., CEST) and UTC offset
        timezone_abbr, utc_offset = _get_timezone_details(webserver_node)

        return jsonify(success=True,
                       time=current_time,
                       timezone=timezone_name,
                       timezone_abbr=timezone_abbr,
                       utc_offset=utc_offset,
                       timezone_changed=_timezone_changed)

    except Exception as ex:
        webserver_node.get_logger().error(f"Failed to get time and timezone information: {ex}")
        return jsonify(success=False, reason="Failed to retrieve time information")


def _get_timezone_name(webserver_node):
    """Get the system timezone name."""
    try:
        result = subprocess.run(
            ["timedatectl", "show", "-p", "Timezone", "--value"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as ex:
        webserver_node.get_logger().warning(f"Failed to get timezone from timedatectl: {ex}")
        return time.tzname[time.daylight] if time.daylight else time.tzname[0]
    except Exception as ex:
        webserver_node.get_logger().warning(f"Unexpected error getting timezone name: {ex}")
        return "UTC"


def _get_timezone_details(webserver_node):
    """Get timezone abbreviation and UTC offset."""
    try:
        now = datetime.datetime.now()
        # Get the current timezone info using the system's local timezone
        local_tz = datetime.datetime.now().astimezone().tzinfo
        timezone_abbr = local_tz.tzname(now)
        utc_offset = local_tz.utcoffset(now)
        # Format UTC offset as +HHMM
        if utc_offset is not None:
            total_minutes = int(utc_offset.total_seconds() // 60)
            sign = "+" if total_minutes >= 0 else "-"
            hours, minutes = divmod(abs(total_minutes), 60)
            utc_offset = f"{sign}{hours:02d}{minutes:02d}"
        else:
            utc_offset = "+0000"

        return timezone_abbr, utc_offset

    except Exception as ex:
        webserver_node.get_logger().warning(f"Failed to get timezone details: {ex}")
        fallback_abbr = time.tzname[time.daylight] if time.daylight else time.tzname[0]
        return fallback_abbr, "+00:00"


@TIME_API_BLUEPRINT.route("/api/set_timezone", methods=["POST"])
def set_timezone():
    """API called to set the timezone of the car.

    Returns:
        dict: Execution status if the API call was successful, with error reason if call fails.
    """
    global _timezone_changed

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
            stdout = result[1] if isinstance(result, tuple) and len(result) > 0 else ""
            valid_timezones = stdout.strip().split('\n') if stdout else []

            if timezone not in valid_timezones:
                return jsonify(success=False, reason=f"Invalid timezone: {timezone}")

        except Exception as validation_ex:
            webserver_node.get_logger().warning(f"Failed to validate timezone list: {validation_ex}")
            # Continue with the operation if validation fails - let timedatectl handle the error

        result = utility.execute(f"timedatectl set-timezone {timezone}", shlex_split=True)
        if result[0] == 0:
            _timezone_changed = True
            return jsonify(success=True, reason="Timezone updated successfully")
        else:
            webserver_node.get_logger().error(f"Failed to set timezone: {result.stderr}")
            return jsonify(success=False, reason=f"Failed to set timezone: {result.stderr}")

    except Exception as ex:
        webserver_node.get_logger().error(f"Failed to set timezone: {ex}")
        return jsonify(success=False, reason="Error")
