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
deepracer_systems_scripts_node.py

This package runs in background to run dependency scripts.

The node defines:
    timer: A timer created to periodically schedule to run dependency script commands
           if not run previously.
"""

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from subprocess import Popen, PIPE, STDOUT
import threading
from deepracer_systems_pkg import constants


class DeepracerSystemsScriptsNode(Node):
    """Node responsible for running dependency scripts.
    """

    def __init__(self):
        """Create a DeepracerSystemsScriptsNode.
        """
        super().__init__("deepracer_systems_script_node")
        self.get_logger().info("deepracer_systems_script_node started.")
        self.timer = self.create_timer(constants.CHK_DEP_TIMER_PERIOD, self.run_dependencies)
        self.lock = threading.RLock()

        self.uvc_logs_suppressed = False

    def __enter__(self):
        """Called when the node object is created using the 'with' statement.
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Called when the object is destroyed.
        """
        pass

    def run_dependencies(self):
        """Timer callback which runs the dependency scripts if not run previously.
        """
        self.get_logger().info("Initiate running dependency scripts check.")
        with self.lock:
            if not self.uvc_logs_suppressed:
                self.uvc_logs_suppressed = self.suppress_uvc_logs()

    def suppress_uvc_logs(self):
        """Function which runs the dependency commands to suppress verbose UVC camera driver logs.

        Returns:
            bool: True if uvc logs are suppressed successfully else False.
        """
        try:
            is_rule_present = self.is_keyword_in_file(constants.RSYSLOG_RULE, constants.RSYSLOG_CONFIG_FILE)
            if not is_rule_present:
                self.prepend_keyword_to_file(constants.RSYSLOG_RULE, constants.RSYSLOG_CONFIG_FILE)
                return self.execute_cmd(constants.RSYSLOG_RESTART_CMD)
            else:
                self.get_logger().info("UVC suppression rule already present in rsyslog config file.")
                return True
        except Exception as ex:
            self.get_logger().error(f"Failed to suppress_uvc_logs. Exception: {ex}")
            return False

    def is_keyword_in_file(self, keyword, file):
        """Function which reads from a file and verifies if the input keyword
        is already present or not.

        Args:
            keyword (str): keyword to be matched in the file.
            file (str): Path to the file on device.

        Returns:
            bool: True if keyword is found in file else False.
        """
        try:
            with open(file, 'r') as f:
                if keyword in f.read():
                    self.get_logger().info(f"Found {keyword} in {file}")
                    return True
                else:
                    return False
        except FileNotFoundError:
            self.get_logger().error(f"File {file} not found on device.")
            return False

    def prepend_keyword_to_file(self, keyword, file):
        """Function which prepends given keyword at the beginning of the file.

        Args:
            keyword (str): keyword to be added to the file.
            file (str): Path to the file on device.
        """
        with open(file, 'a+') as f:
            self.get_logger().info(f"Writing {keyword} in {file}")
            f.seek(0, 0)
            content = f.read()
            f.truncate(0)
            f.write(keyword.rstrip('\r\n') + '\n' + content)

    def execute_cmd(self, cmd):
        """Execute the commands on shell terminal.

        Args:
            cmd (str): Command to be executed.

        Returns:
            bool: True if command executed successfully.
        """
        proc = Popen([cmd], stdout=PIPE, stdin=PIPE, stderr=STDOUT, shell=True)
        stdout = proc.communicate()
        self.get_logger().info(f"{cmd} : Execute output: {stdout[0]}")
        return not proc.returncode


def main(args=None):

    try:
        rclpy.init(args=args)
        deepracer_systems_script_node = DeepracerSystemsScriptsNode()
        executor = MultiThreadedExecutor()
        rclpy.spin(deepracer_systems_script_node, executor)
        # Destroy the node explicitly
        # (optional - otherwise it will be done automatically
        # when the garbage collector destroys the node object)
        deepracer_systems_script_node.destroy_node()

    except KeyboardInterrupt:
        pass

    finally:
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
