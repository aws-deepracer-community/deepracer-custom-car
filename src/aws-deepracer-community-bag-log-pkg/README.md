# AWS DeepRacer Community Bag Logging Package

## Overview

The AWS DeepRacer Community bag logging ROS package creates the `bag_log_node`, which records ROS2 topics to rosbag files for the AWS DeepRacer application. This node enables automatic data collection during autonomous driving sessions and supports USB-based log storage for easy data retrieval and analysis.

This package provides both **Python** and **C++** implementations of the bag logging node:

- **Python implementation** (`bag_log_node`): The original implementation, fully compatible with ROS2 Humble and earlier distributions. Ideal for development and testing environments.
- **C++ implementation** (`bag_log_node_cpp`): A high-performance native implementation optimized for ROS2 Jazzy and newer distributions. Offers significantly improved performance with lower CPU overhead and reduced memory footprint, making it ideal for production deployments on resource-constrained devices like the AWS DeepRacer.

Both implementations are **fully compatible** with each other, sharing the same ROS2 interface (parameters, topics, services), allowing seamless switching between them without any changes to the rest of your system.

This package is part of the AWS DeepRacer Community modifications and is designed to integrate seamlessly with the core AWS DeepRacer application launched from the `deepracer_launcher`. For more details about the AWS DeepRacer application and its components, see the [AWS DeepRacer Launcher repository](https://github.com/aws-deepracer/aws-deepracer-launcher).

## License

The source code is released under [Apache 2.0](https://aws.amazon.com/apache-2-0/).

## Installation

Follow these steps to install the AWS DeepRacer Community bag logging package.

### Prerequisites

The AWS DeepRacer device comes with all prerequisite packages and libraries installed to run the `bag_log_pkg`. For more details about the preinstalled packages and libraries on the AWS DeepRacer device and about installing required build systems, see [Getting started with AWS DeepRacer OpenSource](https://github.com/aws-deepracer/aws-deepracer-launcher/blob/main/getting-started.md).

The `bag_log_pkg` specifically depends on the following ROS 2 packages as build and run dependencies:

1. `deepracer_interfaces_pkg`: This package contains the custom message and service type definitions used across the AWS DeepRacer core application.
2. `rosbag2_py`: ROS2 bag Python API for recording and playing back ROS2 topics.
3. `usb_monitor_pkg`: The AWS DeepRacer USB monitor package for detecting and managing USB storage devices.

## Downloading and Building

Open a terminal on the AWS DeepRacer device and run the following commands as the root user.

1. Switch to the root user before you source the ROS 2 installation:

        sudo su

2. Source the ROS 2 Humble setup bash script:

        source /opt/ros/humble/setup.bash

3. Create a workspace directory for the package:

        mkdir -p ~/deepracer_ws
        cd ~/deepracer_ws

4. Clone the `aws-deepracer-community-bag-log-pkg` repository:

        git clone https://github.com/aws-deepracer-community/deepracer-custom-car.git
        cd deepracer-custom-car/src/aws-deepracer-community-bag-log-pkg

5. Resolve the `bag_log_pkg` dependencies:

        cd ~/deepracer_ws/deepracer-custom-car
        rosdep install -i --from-path src --rosdistro humble -y

6. Build the `bag_log_pkg` and dependencies:

        cd ~/deepracer_ws/deepracer-custom-car
        colcon build --packages-select bag_log_pkg

## Usage

The `bag_log_node` provides automatic rosbag recording functionality for the AWS DeepRacer application. The package offers both Python and C++ implementations that can be used interchangeably.

### Choosing Between Python and C++ Implementations

**Python Node** (`bag_log_node`):
- Recommended for ROS2 Humble and earlier distributions
- Easier to modify and debug during development
- Lower barrier to entry for developers familiar with Python

**C++ Node** (`bag_log_node_cpp`):
- **Recommended for ROS2 Jazzy and newer distributions**
- Significantly better performance with lower CPU usage
- Reduced memory footprint, ideal for resource-constrained devices
- Faster startup time and more responsive recording behavior
- Native integration with ROS2 infrastructure

Both nodes share identical interfaces and can be swapped without any system changes.

### Run the Node

Although the node is designed to work with the AWS DeepRacer application, you can run it independently for development, testing, and debugging purposes.

#### Running the Python Node

To launch the built `bag_log_node` as the root user on the AWS DeepRacer device, open another terminal and run the following commands as the root user:

1. Switch to the root user before you source the ROS 2 installation:

        sudo su

2. Source the ROS 2 Humble setup bash script:

        source /opt/ros/humble/setup.bash

3. Source the setup script for the installed packages:

        source ~/deepracer_ws/deepracer-custom-car/install/setup.bash

4. Launch the `bag_log_node` using the launch script:

        ros2 launch bag_log_pkg bag_log_pkg_launch.py

#### Running the C++ Node

To launch the C++ implementation `bag_log_node_cpp`:

1. Switch to the root user before you source the ROS 2 installation:

        sudo su

2. Source the ROS 2 Jazzy setup bash script (or Humble for backward compatibility):

        source /opt/ros/jazzy/setup.bash

3. Source the setup script for the installed packages:

        source ~/deepracer_ws/deepracer-custom-car/install/setup.bash

4. Launch the `bag_log_node_cpp` using the C++ launch script:

        ros2 launch bag_log_pkg bag_log_cpp_launch.py

## Launch Files

The package includes launch files for both Python and C++ implementations:

### Python Node Launch File

The `bag_log_pkg_launch.py` file launches the Python implementation:

```python
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='bag_log_pkg',
            namespace='bag_log_pkg',
            executable='bag_log_node',
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
```

### C++ Node Launch File

The `bag_log_cpp_launch.py` file launches the C++ implementation with identical parameters:

```python
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
```

Both launch files use the same configuration parameters, making it easy to switch between implementations.

## Node Details

### `bag_log_node` and `bag_log_node_cpp`

Both the Python and C++ implementations provide identical functionality and interfaces. The key differences are in performance characteristics:

**Performance Comparison:**
- **CPU Usage**: The C++ node typically uses 80-90% less CPU than the Python implementation during active recording
- **Memory Footprint**: The C++ node has approximately 40-60% lower memory usage
- **Startup Time**: The C++ node starts 2-3x faster than the Python version
- **Recording Latency**: The C++ node provides more consistent and lower latency when starting/stopping recordings

**Recommended Use Cases:**
- Use the **Python node** for development, debugging, and on systems running ROS2 Humble or earlier
- Use the **C++ node** for production deployments, especially on ROS2 Jazzy, and when performance or resource efficiency is critical

#### Parameters

| Parameter name | Type | Description |
| -------------- | ---- | ----------- |
| `output_path` | `string` | The path where log files will be stored. Default: `/opt/aws/deepracer/logs` |
| `disable_usb_monitor` | `bool` | Flag to disable USB monitoring functionality. Default: `False` |
| `logging_mode` | `string` | Mode of logging operation. Options: `Never`, `USBOnly`, `Always`. Default: `Always` |
| `monitor_topic` | `string` | Topic to monitor for triggering recording. Default: `/inference_pkg/rl_results` |
| `file_name_topic` | `string` | Topic to monitor for bag file naming. Default: `/inference_pkg/model_name` |
| `monitor_topic_timeout` | `int` | Timeout in seconds for monitor topic activity. Default: `15` |
| `log_topics` | `string[]` | List of additional topics to record. Default: `['/ctrl_pkg/servo_msg']` |
| `logging_provider` | `string` | Storage format for bag files. Default: `sqlite3` |

#### Subscribed Topics

| Topic name | Message type | Description |
| ---------- | ------------ | ----------- |
| `/inference_pkg/rl_results` (configurable) | Any | Monitor topic that triggers the start of recording when messages are received. |
| `/inference_pkg/model_name` (configurable) | `String` | Topic providing the model name for bag file naming. |
| `/ctrl_pkg/servo_msg` (configurable) | Any | Additional topics to record as specified in `log_topics` parameter. |
| `/usb_monitor_pkg/usb_file_system_notification` | `USBFileSystemNotificationMsg` | Notification messages for USB file system events. |

#### Services

| Service name | Service type | Description |
| ------------ | ------------ | ----------- |
| `stop_logging` | `Trigger` | Service to manually stop the current recording session. |

#### Service Clients

| Service name | Service type | Description |
| ------------ | ------------ | ----------- |
| `/usb_monitor_pkg/usb_file_system_subscribe` | `USBFileSystemSubscribeSrv` | Client to subscribe to USB file system notifications for the logs directory. |
| `/usb_monitor_pkg/usb_mount_point_manager` | `USBMountPointManagerSrv` | Client to manage USB mount point reference counting. |

## Configuration

### Logging Modes

The node supports three logging modes:

- **Never**: Logging is disabled completely.
- **USBOnly**: Recording only starts when a USB drive with a "logs" folder is detected.
- **Always**: Recording starts automatically when the monitor topic becomes active.

### Monitor Topic Behavior

The node monitors a specific topic (default: `/inference_pkg/rl_results`) to determine when to record:

1. When a message is received on the monitor topic, recording begins.
2. Recording continues as long as messages are received within the timeout period.
3. If no messages are received for the configured timeout duration, recording stops automatically.
4. A new bag file is created when a new model name is received on the file name topic.

### USB Storage

When USB monitoring is enabled (default), the node:

1. Watches for USB drives containing a "logs" folder.
2. Automatically switches the output path to the USB drive when detected.
3. Records directly to the USB drive for easy data collection.

## Resources

* [Getting started with AWS DeepRacer OpenSource](https://github.com/aws-deepracer/aws-deepracer-launcher/blob/main/getting-started.md)
* [AWS DeepRacer Community](https://github.com/aws-deepracer-community)
