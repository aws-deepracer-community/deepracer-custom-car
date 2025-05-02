from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='deepracer_navigation_pkg',
            namespace='deepracer_navigation_pkg',
            executable='deepracer_navigation_node_cpp',  # Updated to use the C++ executable
            name='deepracer_navigation_node',
            output='screen'
        )
    ])