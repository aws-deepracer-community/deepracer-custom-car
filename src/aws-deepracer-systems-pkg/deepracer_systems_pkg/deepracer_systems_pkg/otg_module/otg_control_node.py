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

"""
otg_control_node.py

This module creates the otg_control_node which is responsible to check for otg connection
and enable/disable whenever there is a connection change. It provides services and
functions to execute scripts to initialize, enable, disable otg and find out about
current the otg connection status.

The node defines:
    otg_check_timer: A timer created to periodically check if there is a host connection
                     and schedule to enable or disable otg.
    get_otg_link_state_service: A service that is called to return the flag if host is
                                connected.
"""

import os
import threading
import subprocess
import rclpy
from rclpy.node import Node

from deepracer_systems_pkg import (file_system_utils,
                                   scheduler,
                                   utility)
from deepracer_systems_pkg.otg_module import otg_config
from deepracer_interfaces_pkg.srv import OTGLinkStateSrv


#########################################################################################
# OTG control class.

class OTGControlNode(Node):
    """Node responsible for execute scripts to initialize, enable and disable otg connections.
    """

    def __init__(self):
        """Create a OTGControlNode.
        """
        super().__init__("otg_control_node")
        self.get_logger().info("otg_control_node started")
        # Setup and Start OTG monitor.
        self.init_otg()

        # Threading lock object to safely check connection details and enable/disable otg.
        self.otg_guard = threading.Lock()

        # Flag to identify if the host is connected.
        self.otg_connected = True

        # Scheduler to queue the function calls and run them in a separate thread.
        self.scheduler = scheduler.Scheduler(self.get_logger())
        self.stop = threading.Event()

        # Timer to periodically check for host connection and enable/disable otg.
        if otg_config.ENABLE_OTG_PERIODIC_CHECK:
            self.otg_check_timer = \
                self.create_timer(otg_config.OTG_CHECK_PERIOD_IN_SECONDS,
                                  self.check_otg_connection)

        # Service to return host connection flag.
        self.get_otg_link_state_service = \
            self.create_service(OTGLinkStateSrv,
                                otg_config.GET_OTG_LINK_STATE_SERVICE_NAME,
                                self.get_otg_link_state)

        # Heartbeat timer.
        self.timer_count = 0
        self.timer = self.create_timer(5.0, self.timer_callback)

        self.get_logger().info("OTG Control node successfully created")

    def timer_callback(self):
        """Heartbeat function to keep the node alive.
        """
        self.get_logger().debug(f"Timer heartbeat {self.timer_count}")
        self.timer_count += 1

    def get_otg_link_state(self, req, res):
        """Callback for the get_otg_link_state service. Returns the host connection details.

        Args:
            req (OTGLinkStateSrv.Request): No request data passed.
            res (OTGLinkStateSrv.Response): Response object with link_state(bool) flag
                                            with the host connection details.

        Returns:
            OTGLinkStateSrv.Response: Response object with link_state(bool) flag
                                      with the host connection details.
        """
        if otg_config.ENABLE_OTG_PERIODIC_CHECK:
            res.link_state = self.is_otg_connected()
        else:
            res.link_state = False
        return res

    def __enter__(self):
        """Called when the node object is created using the 'with' statement.

        Returns:
           OTGControlNode : self object returned.
        """
        if otg_config.ENABLE_OTG_PERIODIC_CHECK:
            self.get_logger().info("Enable OTG by default")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Called when the object is destroyed.
        """
        self.destroy_timer(self.timer)
        self.scheduler.schedule_exit()

        if otg_config.ENABLE_OTG_PERIODIC_CHECK:
            self.disable_otg()
            self.destroy_timer(self.otg_check_timer)

    def check_otg_connection(self):
        """Wrapper function to schedule the otg_connection_change function whenver
           there is a chagne in the host connecton status.
        """
        with utility.AutoLock(self.otg_guard):
            host_connected = otg_config.OTG_UP_STATE in file_system_utils.read_line(otg_config.OTG_STATE_FILE)
            if host_connected != self.otg_connected:
                self.otg_connected = host_connected
                self.scheduler.schedule_action(self.otg_connection_change, connected=host_connected)

    def otg_connection_change(self, keyworded_args):
        """Function to enable/disable otg based on host connection status.

        Args:
            keyworded_args (dict): Keyworded arguments passed to the function while scheduling.
        """
        connected = keyworded_args.get("connected")
        if connected:
            self.get_logger().info("OTG cable connected.")
            self.enable_otg()
            return

        # Disable Ethernet Over OTG and sync changes, if any.
        self.get_logger().info("OTG cable disconnected.")
        self.disable_otg()

    def is_otg_connected(self):
        """Getter function to return the otg_connected flag data.

        Returns:
            bool: Host connection status.
        """
        return self.otg_connected

    def init_otg(self):
        """Initialization function to execute the otg_eth script.
        """
        # Initiate Ethenret Connectivity
        self.execute("/opt/aws/deepracer/util/otg_eth.sh start")
        self.get_logger().info("Setup Ethernet over OTG.")

    def enable_otg(self):
        """Helper method to enable the otg by executing required commands.

        Returns:
            bool: True if successfully executed the commands.
        """
        # Setup connectivity from  Windows
        usb0 = False
        usb1 = False

        # Setup connectivity from Windows
        if self.execute("ip link set usb0 up"):
            if self.execute("ip addr add 10.0.0.1/30 dev usb0"):
                if self.execute("systemctl restart dnsmasq") and \
                   self.execute("systemctl restart isc-dhcp-server"):
                    usb0 = True
                    self.get_logger().info("Ethernet Over OTG enabled for Windows!")
        if not usb0:
            self.get_logger().error("Ethernet Over OTG enable failed for Windows.")

        # Setup connectivity from Mac
        if otg_config.OTH_USB1:
            if self.execute("ip link set usb1 up"):
                if self.execute("ip addr add 10.0.1.1/30 dev usb1"):
                    if self.execute("systemctl restart dnsmasq") and \
                            self.execute("systemctl restart isc-dhcp-server"):
                        usb1 = True
                        self.get_logger().info("Ethernet Over OTG enabled for MAC!")
            if not usb1:
                self.get_logger().error("Ethernet Over OTG enable failed for MAC.")

        return True

    def disable_otg(self):
        """Helper method to disable the otg by executing required commands.
        """
        if not self.execute("ip link set usb0 down"):
            self.get_logger().error("Ethernet Over OTG disable failed for Windows!")
        if otg_config.OTH_USB1:
            if not self.execute("ip link set usb1 down"):
                self.get_logger().error("Ethernet Over OTG disable failed for MAC!")
        self.get_logger().info("Ethernet Over OTG disabled!!!")

    def execute(self, cmd):
        """Helper method to run the commands and return the execution status.

        Args:
            cmd (str): Command to be executed.

        Returns:
            bool: True if command is executed successfully else False.
        """
        try:
            proc = subprocess.Popen([cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            proc.communicate()
            return True
        except Exception as ex:
            self.get_logger().error("Failed to self.execute cmd: {} err:{}".format(cmd, ex))
            return False


def main(args=None):
    try:
        rclpy.init(args=args)
        with OTGControlNode() as otg_control_node:
            rclpy.spin(otg_control_node)
            otg_control_node.destroy_node()

    except KeyboardInterrupt:
        pass

    finally:
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
