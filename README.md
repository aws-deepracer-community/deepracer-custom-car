# DeepRacer Interfaces Package

## Overview

The DeepRacer Interfaces ROS package is a foundational package that creates the custom service and message types that are used in the core AWS DeepRacer application. These services and messages defined are shared across the packages that are part of the AWS DeepRacer application. More details about the application and the components can be found [here](https://github.com/aws-racer/aws-deepracer-launcher).

## License

The source code is released under Apache 2.0 (https://aws.amazon.com/apache-2-0/).

## Installation

### Prerequisites

The DeepRacer device comes with all the pre-requisite packages, build systems and libraries installed to build and run the deepracer_inferfaces_pkg. More details about pre installed set of packages and libraries on the DeepRacer, and installing required build systems can be found in the [Getting Started](https://github.com/aws-racer/aws-deepracer-launcher/blob/main/getting-started.md) section of the AWS DeepRacer Opensource page.

The deepracer_inferfaces_pkg specifically depends on the following ROS2 packages as build and execute dependencies:

1. *rosidl_default_generators* - The custom built interfaces rely on rosidl_default_generators for generating language-specific code.
1. *rosidl_default_runtime* - The custom built interfaces rely on rosidl_default_runtime for using the language-specific code.
1. *sensor_msgs* - This package defines messages for commonly used sensors, including cameras and scanning laser rangefinders.
1. *std_msgs* - Standard ROS Messages including common message types representing primitive data types and other basic message constructs, such as multiarrays.

## Downloading and Building

Open up a terminal on the DeepRacer device and run the following commands as root user.

1. Source the ROS2 Foxy setup bash script:

        source /opt/ros/foxy/setup.bash 

1. Create a workspace directory for the package:

        mkdir -p ~/deepracer_ws
        cd ~/deepracer_ws

1. Clone the deepracer_interfaces_pkg on the DeepRacer device:

        git clone https://github.com/aws-racer/aws-deepracer-interfaces-pkg.git

1. Resolve the deepracer_inferfaces_pkg dependencies:

        cd ~/deepracer_ws && rosdep install -i --from-path . --rosdistro foxy -y

1. Build the deepracer_interfaces_pkg:

        cd ~/deepracer_ws && colcon build --packages-select deepracer_interfaces_pkg

