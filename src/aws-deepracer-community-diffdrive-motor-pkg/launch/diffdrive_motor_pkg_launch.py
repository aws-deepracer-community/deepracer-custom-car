#!/usr/bin/env python3

"""
Launch file for AWS DeepRacer Community Differential Drive Motor Package.

This launch file maintains the same interface as the original servo package
to ensure compatibility with existing DeepRacer applications.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

from launch_ros.actions import Node


def generate_launch_description():
    """Generate launch description for differential drive motor package."""
    # Launch arguments — must match parameters declared in DifferentialDriveNode
    max_left_differential_arg = DeclareLaunchArgument(
        'max_left_differential',
        default_value='0.5',
        description='Maximum speed reduction on the left wheel during a left turn (0.0-1.0)'
    )

    max_right_differential_arg = DeclareLaunchArgument(
        'max_right_differential',
        default_value='0.5',
        description='Maximum speed reduction on the right wheel during a right turn (0.0-1.0)'
    )

    center_offset_arg = DeclareLaunchArgument(
        'center_offset',
        default_value='0.0',
        description='Steering zero-point offset (-1.0 to 1.0) to compensate for misalignment'
    )

    motor_polarity_arg = DeclareLaunchArgument(
        'motor_polarity',
        default_value='1',
        description='Reverses both motors when set to -1 (use to fix inverted direction)'
    )

    # Differential drive motor node
    diffdrive_motor_node = Node(
        package='diffdrive_motor_pkg',
        executable='diffdrive_motor_node',
        name='diffdrive_motor_node',
        parameters=[{
            'max_left_differential': LaunchConfiguration('max_left_differential'),
            'max_right_differential': LaunchConfiguration('max_right_differential'),
            'center_offset': LaunchConfiguration('center_offset'),
            'motor_polarity': LaunchConfiguration('motor_polarity'),
        }],
        output='screen'
    )

    return LaunchDescription([
        max_left_differential_arg,
        max_right_differential_arg,
        center_offset_arg,
        motor_polarity_arg,
        diffdrive_motor_node
    ])
