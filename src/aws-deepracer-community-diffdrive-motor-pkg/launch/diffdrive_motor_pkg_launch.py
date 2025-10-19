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
    # Launch arguments
    max_turn_differential_arg = DeclareLaunchArgument(
        'max_turn_differential',
        default_value='0.5',
        description='Maximum speed difference between wheels (0.0-1.0)'
    )

    pwm_device_arg = DeclareLaunchArgument(
        'pwm_device',
        default_value='i2c-1',
        description='PWM device identifier for chip discovery'
    )

    invert_left_motor_arg = DeclareLaunchArgument(
        'invert_left_motor',
        default_value='false',
        description='Invert left motor direction'
    )

    invert_right_motor_arg = DeclareLaunchArgument(
        'invert_right_motor',
        default_value='false',
        description='Invert right motor direction'
    )

    # Differential drive motor node
    diffdrive_motor_node = Node(
        package='diffdrive_motor_pkg',
        executable='diffdrive_motor_node',
        name='diffdrive_motor_node',
        parameters=[{
            'max_turn_differential': LaunchConfiguration('max_turn_differential'),
            'pwm_device': LaunchConfiguration('pwm_device'),
            'invert_left_motor': LaunchConfiguration('invert_left_motor'),
            'invert_right_motor': LaunchConfiguration('invert_right_motor'),
        }],
        output='screen'
    )

    return LaunchDescription([
        max_turn_differential_arg,
        pwm_device_arg,
        invert_left_motor_arg,
        invert_right_motor_arg,
        diffdrive_motor_node
    ])
