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
import socket
import subprocess
import fcntl
import struct

from deepracer_systems_pkg import file_system_utils
from deepracer_systems_pkg.software_update_module import software_update_config
from deepracer_systems_pkg.network_monitor_module import network_config


#########################################################################################
# Determine the name of the currently connected WiFi.

def get_current_SSID():
    """Helper function to find the WiFi SSID name.

    Returns:
        str: Wifi SSID name("" on Exception).
    """
    try:
        p = subprocess.Popen(["iwgetid", "-r"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        return out.strip().decode("utf-8")

    except Exception:
        return ""


#########################################################################################
# Hostname functions.

def get_chassis_serial():
    """Read the serial value from the /sys/class/dmi/id/chassis_serial file
       which will be used to set as hostname.

    Returns:
        str: Chassis serial value. (Example: amss-mmaz)
    """
    serial = file_system_utils.read_line(network_config.CHASSIS_SERIAL).strip()
    if serial == "":
        serial = "deepracer"

    serial = serial.lower()
    serial = serial.replace(" ", "-")

    return serial


def get_hostname():
    """Wrapper function to return the result of socket.gethostname() function. This returns
       a string containing the hostname of the machine where the Python interpreter
       is currently executing.

    Returns:
        str: Hostname of the machine.
    """
    return socket.gethostname()


def set_hostname(new_hostname):
    """Set the new host name.

    Args:
        new_hostname (str): New host name.

    Returns:
        str: Updated new host name if successful.
    """
    try:
        socket.sethostname(new_hostname)
    except Exception:
        pass

    return get_hostname()


#########################################################################################

def get_interface_IP(interface_name):
    """Retrieve IP address of the specified network interface.

    Args:
        interface_name (str): Name of the interace.

    Returns:
        str: Standard dotted-quad string representation of the IP address.
    """
    IFNAMSIZ = 16      # Maximum size of the interface name including zero character.
    SIOCGIFADDR = 0x8915  # IOCTL control code
    IFREQSIZ = 40      # sizeof(struct ifreq)

    # Pack interface name into ASCIIZ form while making sure
    # the interface name length is within the alowed range.
    interface_name_z = struct.pack("%ds" % IFREQSIZ, bytes(interface_name[:IFNAMSIZ-1], "utf-8"))

    # Open UDP socket.
    udpSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Execute IOCTL.
    result = fcntl.ioctl(udpSock.fileno(), SIOCGIFADDR, interface_name_z)

    # Extract binary IP and convert to string.
    # The code below is an emulation of:
    #   (struct sockaddr_in *) &ifr.ifr_addr)->sin_addr
    bin_IP = result[20:24]
    return socket.inet_ntoa(bin_IP)


#########################################################################################

def get_net_connections():
    """Determine available network interfaces and their IP addresses.

    Returns:
        dict: Map of the network interfaces and their IP addresses.
    """
    result = dict()

    for interface in os.listdir(os.path.join(os.sep, "sys", "class", "net")):
        try:
            ip = get_interface_IP(interface)

            # Ignore loopback addresses.
            quads = ip.split(".")
            if quads[0] == "127":
                continue

            result[interface] = ip

        except Exception as e:
            pass
    return result
