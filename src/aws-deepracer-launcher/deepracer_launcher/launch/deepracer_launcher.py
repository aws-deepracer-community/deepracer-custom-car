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

from calendar import c
import math

from numpy import e
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def str2bool(v):
    return v.lower() in ("yes", "true", "t", "1")


def launch_setup(context, *args, **kwargs):

    ld = []

    camera_mode = LaunchConfiguration('camera_mode').perform(context)
    camera_index = int(LaunchConfiguration('camera_index').perform(context))
    fps = int(LaunchConfiguration('camera_fps').perform(context))
    resize_images = str2bool(LaunchConfiguration('camera_resize').perform(context))
    resolution = resize_images and [160, 120] or [640, 480]

    if camera_mode == 'legacy':
        camera_node = Node(
            package='camera_pkg',
            namespace='camera_pkg',
            executable='camera_node',
            name='camera_node',
            parameters=[
                {'resize_images': resize_images,
                 'fps': fps}
            ]
        )
    else:
        # Camera configuration
        camera_params = {'width': resolution[0],
                         'height': resolution[1],
                         'FrameDurationLimits': [math.floor(1e6 / fps), math.ceil(1e6 / fps)],
                         'timestamp_source': 'node'}

        # Camera detection
        try:
            from libcamera import CameraManager
            camera_manager = CameraManager.singleton()

            camera_model = None
            
            # If camera_index is specified, use it to select the camera
            if camera_index >= 0 and camera_index < len(camera_manager.cameras):
                camera = camera_manager.cameras[camera_index]
                for prop_id, value in camera.properties.items():
                    if 'Model' in str(prop_id):
                        camera_model = value

                camera_params['camera'] = camera_index
                print(f"Camera {camera_index}: {camera_model} - {camera.id}")

                # Select the sensor mode based on the camera model
                # RPi Cameras need specific sensor modes to avoid cropping
                if camera_model == 'imx708':
                    camera_params['sensor_mode'] = '2304:1296'
                    camera_params['format'] = 'BGR888'
                elif camera_model == 'imx219':
                    camera_params['sensor_mode'] = '1640:1232'
                    camera_params['format'] = 'BGR888'

        except ImportError as e:
            print("libcamera is not available, using imx219 camera settings.")
            camera_params['sensor_mode'] = '1640:1232'
            camera_params['format'] = 'BGR888'

        camera_node = Node(
            package='camera_ros',
            namespace='camera_pkg',
            executable='camera_node',
            parameters=[camera_params],
            remappings=[
                # Topic remappings
                ('/camera_pkg/camera/camera_info', '/camera_pkg/camera_info'),
                ('/camera_pkg/camera/image_raw', '/camera_pkg/display_mjpeg'),
                ('/camera_pkg/camera/image_raw/compressed', '/camera_pkg/display_mjpeg/compressed'),
                # Service remappings
                ('/camera_pkg/camera/describe_parameters', '/camera_pkg/describe_parameters'),
                ('/camera_pkg/camera/get_parameter_types', '/camera_pkg/get_parameter_types'),
                ('/camera_pkg/camera/get_parameters', '/camera_pkg/get_parameters'),
                ('/camera_pkg/camera/list_parameters', '/camera_pkg/list_parameters'),
                ('/camera_pkg/camera/set_parameters', '/camera_pkg/set_parameters'),
                ('/camera_pkg/camera/set_parameters_atomically', '/camera_pkg/set_parameters_atomically')
            ]
        )

    ctrl_node = Node(
        package='ctrl_pkg',
        namespace='ctrl_pkg',
        executable='ctrl_node',
        name='ctrl_node',
        parameters=[{'camera_mode': camera_mode}]
    )
    deepracer_navigation_node = Node(
        package='deepracer_navigation_pkg',
        namespace='deepracer_navigation_pkg',
        executable='deepracer_navigation_node_cpp',
        name='deepracer_navigation_node'
    )
    software_update_node = Node(
        package='deepracer_systems_pkg',
        namespace='deepracer_systems_pkg',
        executable='software_update_node',
        name='software_update_node'
    )
    model_loader_node = Node(
        package='deepracer_systems_pkg',
        namespace='deepracer_systems_pkg',
        executable='model_loader_node',
        name='model_loader_node'
    )
    otg_control_node = Node(
        package='deepracer_systems_pkg',
        namespace='deepracer_systems_pkg',
        executable='otg_control_node',
        name='otg_control_node'
    )
    network_monitor_node = Node(
        package='deepracer_systems_pkg',
        namespace='deepracer_systems_pkg',
        executable='network_monitor_node',
        name='network_monitor_node'
    )
    deepracer_systems_scripts_node = Node(
        package='deepracer_systems_pkg',
        namespace='deepracer_systems_pkg',
        executable='deepracer_systems_scripts_node',
        name='deepracer_systems_scripts_node'
    )
    device_info_node = Node(
        package='device_info_pkg',
        namespace='device_info_pkg',
        executable='device_info_node',
        name='device_info_node'
    )
    device_status_node = Node(
        package='device_info_pkg',
        namespace='device_info_pkg',
        executable='device_status_node',
        name='device_status_node'
    )

    battery_node_exec = 'battery_node'
    if str2bool(LaunchConfiguration('battery_dummy').perform(context)):
        battery_node_exec = 'battery_dummy_node'

    battery_node = Node(
        package='i2c_pkg',
        namespace='i2c_pkg',
        executable=battery_node_exec,
        name='battery_node'
    )

    inference_node = Node(
        package='inference_pkg',
        namespace='inference_pkg',
        executable='inference_node',
        name='inference_node',
        respawn=True,
        respawn_delay=5,
        parameters=[{
                'device': LaunchConfiguration("inference_device").perform(context),
                'inference_engine': LaunchConfiguration("inference_engine").perform(context)
        }]
    )
    model_optimizer_node = Node(
        package='model_optimizer_pkg',
        namespace='model_optimizer_pkg',
        executable='model_optimizer_node',
        name='model_optimizer_node',
        parameters=[{
                'inference_engine': LaunchConfiguration("inference_engine").perform(context)
        }]
    )

    rplidar = str2bool(LaunchConfiguration('rplidar').perform(context))
    if rplidar:
        rplidar_node = Node(
            package='rplidar_ros',
            namespace='rplidar_ros',
            executable='rplidar_node',
            name='rplidar_node',
            parameters=[{
                    'serial_port': '/dev/ttyUSB0',
                    'serial_baudrate': 115200,
                    'frame_id': 'laser',
                    'inverted': False,
                    'angle_compensate': True,
            }]
        )

    sensor_fusion_node = Node(
        package='sensor_fusion_pkg',
        namespace='sensor_fusion_pkg',
        executable='sensor_fusion_node',
        name='sensor_fusion_node',
        parameters=[{
                'camera_mode': camera_mode,
                'image_transport': 'compressed',
                'enable_overlay': rplidar
        }]
    )
    servo_node = Node(
        package='servo_pkg',
        namespace='servo_pkg',
        executable='servo_node',
        name='servo_node'
    )
    status_led_node = Node(
        package='status_led_pkg',
        namespace='status_led_pkg',
        executable='status_led_node',
        name='status_led_node'
    )
    usb_monitor_node = Node(
        package='usb_monitor_pkg',
        namespace='usb_monitor_pkg',
        executable='usb_monitor_node',
        name='usb_monitor_node'
    )
    webserver_publisher_node = Node(
        package='webserver_pkg',
        namespace='webserver_pkg',
        executable='webserver_publisher_node',
        name='webserver_publisher_node',
        arguments=['--ros-args', '--log-level', 'info']
    )
    web_video_server_node = Node(
        package='web_video_server',
        namespace='web_video_server',
        executable='web_video_server',
        name='web_video_server',
        parameters=[{
                'default_transport': 'compressed'
        }]
    )
    bag_log_node = Node(
        package='logging_pkg',
        namespace='logging_pkg',
        executable='bag_log_node',
        name='bag_log_node',
        parameters=[{
                'logging_mode': LaunchConfiguration(
                    'logging_mode').perform(context),
                'logging_provider': LaunchConfiguration(
                    'logging_provider').perform(context),
                'monitor_topic_timeout': 15,
                'output_path': '/opt/aws/deepracer/logs',
                'monitor_topic': '/deepracer_navigation_pkg/auto_drive',
                'file_name_topic': '/inference_pkg/model_artifact',
                'log_topics': ['/inference_pkg/rl_results', '/device_info_pkg/device_status']
        }]
    )

    ld.append(camera_node)
    ld.append(ctrl_node)
    ld.append(deepracer_navigation_node)
    ld.append(software_update_node)
    ld.append(model_loader_node)
    ld.append(otg_control_node)
    ld.append(network_monitor_node)
    ld.append(deepracer_systems_scripts_node)
    ld.append(device_info_node)
    ld.append(device_status_node)
    ld.append(battery_node)
    ld.append(inference_node)
    ld.append(model_optimizer_node)
    ld.append(sensor_fusion_node)
    ld.append(servo_node)
    ld.append(status_led_node)
    ld.append(usb_monitor_node)
    ld.append(webserver_publisher_node)
    ld.append(web_video_server_node)
    ld.append(bag_log_node)

    if rplidar:
        ld.append(rplidar_node)

    return ld


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                name="camera_fps",
                default_value="30",
                description="FPS of Camera"),
            DeclareLaunchArgument(
                name="camera_resize",
                default_value="True",
                description="Resize camera input"),
            DeclareLaunchArgument(
                name="inference_engine",
                default_value="TFLITE",
                description="Inference engine to use (TFLITE or OV)"),
            DeclareLaunchArgument(
                name="inference_device",
                default_value="CPU",
                description="Inference device to use, applicable to OV only (CPU, GPU or MYRIAD)."),
            DeclareLaunchArgument(
                name="logging_mode",
                default_value="usbonly",
                description="Enable the logging of results to ROS Bag on USB stick"),
            DeclareLaunchArgument(
                name="logging_provider",
                default_value="sqlite3",
                description="Database provider to use for logging"),
            DeclareLaunchArgument(
                name="battery_dummy",
                default_value="False",
                description="Use static dummy for battery measurements"),
            DeclareLaunchArgument(
                name="camera_mode",
                default_value="legacy",
                description="Legacy or modern camera integration"),
            DeclareLaunchArgument(
                name="camera_index",
                default_value="0",
                description="Index of the camera to use, applicable to modern camera_mode only"),                
            DeclareLaunchArgument(
                name="rplidar",
                default_value="True",
                description="Enable RPLIDAR node"),
            OpaqueFunction(function=launch_setup)
        ])
