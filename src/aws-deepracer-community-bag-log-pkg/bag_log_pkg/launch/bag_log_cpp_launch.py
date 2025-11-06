#################################################################################
#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.          #
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

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='bag_log_pkg',
            namespace='bag_log_pkg',
            executable='bag_log_node_cpp',
            name='bag_log_node',
            parameters=[{
                    'monitor_topic': '/inference_pkg/rl_results',
                    'file_name_topic': '/inference_pkg/model_name',
                    'log_topics': ['/ctrl_pkg/servo_msg'],
                    'output_path': '/opt/aws/deepracer/logs',
                    'logging_mode': 'Always',
                    'monitor_topic_timeout': 15,
                    'disable_usb_monitor': False,
                    'logging_provider': 'sqlite3'
            }]
        )
    ])
