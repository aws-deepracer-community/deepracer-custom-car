from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, RegisterEventHandler, Shutdown
from launch.event_handlers import OnProcessExit
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    fps_arg = DeclareLaunchArgument("fps", default_value="30")
    image_dir_arg = DeclareLaunchArgument("image_dir", default_value="test/data/demo")
    model_dir_arg = DeclareLaunchArgument("model_dir", default_value="test/model/Sample_single_cam")

    comparison_node = Node(
        package="test_pkg",
        namespace="camera_pkg",
        executable="inference_comparison_node",
        output="log",
        parameters=[{
            "resize_images": True,
            "display_topic_enable": False,
            "fps": LaunchConfiguration("fps"),
            "image_dir": LaunchConfiguration("image_dir"),
            "model_dir": LaunchConfiguration("model_dir"),
            "output_dir": LaunchConfiguration("image_dir"),
        }],
    )

    sensor_fusion_node = Node(
        package="sensor_fusion_pkg",
        namespace="sensor_fusion_pkg",
        executable="sensor_fusion_node",
        output="log",
        parameters=[{"image_transport": "compressed"}],
    )

    inference_tflite_node = Node(
        package="inference_pkg",
        namespace="inference_pkg_tflite",
        executable="inference_node",
        output="log",
        parameters=[{"inference_engine": "TFLITE"}],
    )

    inference_ov_node = Node(
        package="inference_pkg",
        namespace="inference_pkg_ov",
        executable="inference_node",
        output="log",
        parameters=[{"inference_engine": "OV"}],
    )

    # Shut down the entire stack when inference_comparison_node exits
    shutdown_on_exit = RegisterEventHandler(
        OnProcessExit(
            target_action=comparison_node,
            on_exit=[Shutdown(reason="inference_comparison_node exited")],
        )
    )

    return LaunchDescription([
        fps_arg,
        image_dir_arg,
        model_dir_arg,
        comparison_node,
        sensor_fusion_node,
        inference_tflite_node,
        inference_ov_node,
        shutdown_on_exit,
    ])
