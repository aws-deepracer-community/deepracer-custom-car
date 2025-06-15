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

import os


GET_OTG_LINK_STATE_SERVICE_NAME = "get_otg_link_state"

#########################################################################################
# OTG settings.

ENABLE_OTG_PERIODIC_CHECK = True
OTG_CHECK_PERIOD_IN_SECONDS = 5

def get_otg_link_state_path():
    """
    Get the path to the OTG link state file.
    """
    if os.path.exists(os.path.join(os.sep, "sys", "kernel", "debug", "dwc3.0.auto", "link_state")):
        OTG_STATE_FILE = os.path.join(os.sep, "sys", "kernel", "debug", "dwc3.0.auto", "link_state")
        OTG_UP_STATE = "U0"
        OTH_USB1 = True
    else:
        OTG_STATE_FILE = os.path.join(os.sep, "sys", "class", "net", "usb0", "operstate")
        OTG_UP_STATE = "up"
        OTH_USB1 = False

    return OTG_STATE_FILE, OTG_UP_STATE, OTH_USB1

OTG_STATE_FILE, OTG_UP_STATE, OTH_USB1 = get_otg_link_state_path()