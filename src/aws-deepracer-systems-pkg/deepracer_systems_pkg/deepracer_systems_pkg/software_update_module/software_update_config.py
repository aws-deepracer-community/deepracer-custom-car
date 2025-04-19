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

# Service and topic names.
BEGIN_SOFTWARE_UPDATE_SERVICE_NAME = "begin_update"
SOFTWARE_UPDATE_CHECK_SERVICE_NAME = "software_update_check"
SOFTWARE_UPDATE_STATE_SERVICE_NAME = "software_update_state"

SOFTWARE_UPDATE_PCT_TOPIC_NAME = "software_update_pct"

DEEPRACER_SYSTEMS_PACKAGE_NS = "/deepracer_systems_pkg"
NETWORK_CONNECTION_STATUS_TOPIC_NAME = \
    f"{DEEPRACER_SYSTEMS_PACKAGE_NS}/network_connection_status"

#########################################################################################
# Software Update manager configuration.

ENABLE_PERIODIC_SOFTWARE_UPDATE = False
SOFTWARE_UPDATE_PERIOD_IN_SECONDS = (60.0 * 15)
MIN_TIME_BEFORE_REBOOT_IN_SECONDS = 10
SOFTWARE_UPDATE_RETRY_SLEEP_IN_SECONDS = (30.0 * 15)

MAX_UPDATE_VERIFICATION_RETRY_COUNT = 5

# Apt repository information.
DEEPRACER_SOURCE_LIST_PATH = ["/etc/apt/sources.list.d/aws_deepracer.list", 
                              "/etc/apt/sources.list.d/aws_deepracer-community.list"]

DEEPRACER_PACKAGES = ["aws-deepracer-sample-models",
                      "aws-deepracer-util",
                      "aws-deepracer-device-console",
                      "aws-deepracer-core",
                      "aws-deepracer-community-device-console"]
VERSION_MASK = "2."


# Update state information.
class SoftwareUpdateState():
    UPDATE_UNKNOWN = -1
    UP_TO_DATE = 0
    UPDATE_AVAILABLE = 1
    UPDATE_PENDING = 2
    UPDATE_IN_PROGRESS = 3


SOFTWARE_UPDATE_STATE_MSG = {
    SoftwareUpdateState.UPDATE_UNKNOWN: "Software update check hasn\"t been performed yet.",
    SoftwareUpdateState.UP_TO_DATE: "Software is up to date.",
    SoftwareUpdateState.UPDATE_AVAILABLE: "Software update is available.",
    SoftwareUpdateState.UPDATE_PENDING: "Software update in pending.",
    SoftwareUpdateState.UPDATE_IN_PROGRESS: "Software update in progress."
}

# Per the spec package download accounts for 50% of the update
PACKAGE_DOWNLOAD_PCT = 50.0
# Per the spec package install accounts for 50% of the update
PACKAGE_INSTALL_PCT = 50.0
# Do not allow the install update to go beyond this number, let the update
# be 100% after cache.commit() call, which is when the update is complete.
INSTALL_UPDATE_MAX_PCT = 99.0

# List of available progress states
PROGRESS_STATES = ["unknown",
                   "checking",
                   "beginning",
                   "downloading",
                   "installing",
                   "complete"]

# Dictionary key for the state of the update
PROG_STATE_KEY = "progress_state"
# Dictionary key for % progress of the update
PROG_PCT_KEY = "progress_pct"

SCHEDULE_USB_UPDATE_SCAN_CB = "schedule_usb_update_scan"
UPDATE_SOURCE_DIRECTORY = "update"
