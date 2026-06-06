################################################################################
#   Copyright AWS DeepRacer Community. All Rights Reserved.                   #
#                                                                              #
#   Licensed under the Apache License, Version 2.0 (the 'License').            #
#   You may not use this file except in compliance with the License.           #
#   You may obtain a copy of the License at                                    #
#                                                                              #
#       http://www.apache.org/licenses/LICENSE-2.0                             #
#                                                                              #
#   Unless required by applicable law or agreed to in writing, software        #
#   distributed under the License is distributed on an 'AS IS' BASIS,          #
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.   #
#   See the License for the specific language governing permissions and        #
#   limitations under the License.                                             #
################################################################################

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            name='bus_id',
            default_value='7',
            description='I2C bus number (7 for original DeepRacer, 1 for Raspberry Pi)'),
        DeclareLaunchArgument(
            name='address',
            default_value='104',   # 0x68 in decimal
            description='BMI160 I2C slave address (default: 0x68 = 104)'),
        DeclareLaunchArgument(
            name='publish_rate',
            default_value='30',
            description='IMU publish rate in Hz'),  # matches camera frame rate
        DeclareLaunchArgument(
            name='accel_range_g',
            default_value='8',
            # 8G covers ~4G lateral at racing speeds
            description='Accelerometer full-scale range in G (2, 4, 8, or 16)'),
        DeclareLaunchArgument(
            name='gyro_range_dps',
            default_value='1000',
            # 1000dps = 17.5 rad/s, covers tight turns at racing speed
            description='Gyroscope full-scale range in dps (125, 250, 500, 1000, or 2000)'),
        DeclareLaunchArgument(
            name='accel_z_gravity_target',
            default_value='1',
            description='Expected published accel_z direction when flat: +1 for upside-down '
                        'mounting (DeepRacer default), -1 for normal mounting'),
        DeclareLaunchArgument(
            name='stop_on_pickup',
            default_value='False',
            description='Stop the vehicle when the IMU detects it has been picked up'),
        DeclareLaunchArgument(
            name='stop_on_crash',
            default_value='False',
            description='Stop the vehicle when the IMU detects a high-G crash event'),
        DeclareLaunchArgument(
            name='crash_accel_threshold_g',
            default_value='3.0',
            description='Acceleration magnitude (in G) that triggers the crash stop'),
        DeclareLaunchArgument(
            name='pickup_threshold_g',
            default_value='0.5',
            description='How much the Z-axis acceleration must deviate from the expected '
                        'gravity value (in G) to be considered a pickup event'),
        DeclareLaunchArgument(
            name='filter_alpha',
            default_value='0.5',
            description='EMA smoothing factor (0, 1]: 1.0 = no filtering, lower = more smoothing'),
        Node(
            package='imu_pkg',
            namespace='imu_pkg',
            executable='imu_node',
            name='imu_node',
            parameters=[{
                'bus_id':                 LaunchConfiguration('bus_id'),
                'address':                LaunchConfiguration('address'),
                'publish_rate':           LaunchConfiguration('publish_rate'),
                'accel_range_g':          LaunchConfiguration('accel_range_g'),
                'gyro_range_dps':         LaunchConfiguration('gyro_range_dps'),
                'accel_z_gravity_target': LaunchConfiguration('accel_z_gravity_target'),
                'stop_on_pickup':         LaunchConfiguration('stop_on_pickup'),
                'stop_on_crash':          LaunchConfiguration('stop_on_crash'),
                'crash_accel_threshold_g': LaunchConfiguration('crash_accel_threshold_g'),
                'pickup_threshold_g':     LaunchConfiguration('pickup_threshold_g'),
                'filter_alpha':           LaunchConfiguration('filter_alpha'),
            }]
        ),
    ])
