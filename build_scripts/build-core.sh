#!/usr/bin/env bash
set -e
export DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. >/dev/null 2>&1 && pwd)"

# Parse command line arguments
CACHE="false"
export HW_PLATFORM="${HW_PLATFORM:-DR}"  # Default to DR if not set

while getopts "cp:s" opt; do
    case ${opt} in
    c)
        CACHE="true"
        ;;
    p)
        HW_PLATFORM="${OPTARG}"
        ;;
    s)
        SINGLE_PACKAGE="true"
        ;;
    \?)
        echo "Usage: cmd [-c] [-p platform] [-s]"
        echo "  -c: Use cache"
        echo "  -p: Hardware platform (DR, RPI)"
        echo "  -s: Single package build and only two cores for compilation"
        exit 1
        ;;
    esac
done

# Validate HW_PLATFORM
if [[ ! "$HW_PLATFORM" =~ ^(DR|RPI)$ ]]; then
    echo "Invalid hardware platform: $HW_PLATFORM"
    echo "Valid options: DR, RPI"
    exit 1
fi

echo "Building for hardware platform: $HW_PLATFORM"

# Detect ROS version
if [ -f /opt/ros/foxy/setup.bash ]; then
    ROS_DISTRO="foxy"
elif [ -f /opt/ros/humble/setup.bash ]; then
    ROS_DISTRO="humble"
elif [ -f /opt/ros/jazzy/setup.bash ]; then
    ROS_DISTRO="jazzy"
else
    echo "Unsupported ROS version"
    exit 1
fi
echo "Detected ROS version: $ROS_DISTRO"
source /opt/ros/$ROS_DISTRO/setup.bash

# Set the OpenVINO environment
if [ -f /opt/intel/openvino_2021/bin/setupvars.sh ]; then
    source /opt/intel/openvino_2021/bin/setupvars.sh
elif [ -f /opt/intel/openvino_2022/setupvars.sh ]; then
    source /opt/intel/openvino_2022/setupvars.sh
else
    echo "No OpenVINO in the environment."
fi

# Check single package build
if [ "$SINGLE_PACKAGE" == "true" ]; then
    echo "Limiting build to sequential execution and two cores"
    COLCON_BUILD_ARGS="--executor sequential"
    CMAKE_ARGS="-DCMAKE_BUILD_TYPE=Release"
    export MAKEFLAGS="-j2"
else
    COLCON_BUILD_ARGS="--parallel-workers 4"
    CMAKE_ARGS="-DCMAKE_BUILD_TYPE=Release"
fi

# Change to build directory
cd src

# Remove warnings
export PYTHONWARNINGS="ignore::DeprecationWarning,ignore:::setuptools.command.install"

# Clean up and pull the latest code if not using cache
if [ "$CACHE" != "true" ]; then

    # Remove previous builds (gives clean build)
    rm -rf ../install ../build ../log ../pkg-build/aws-deepracer-core

    cd external

    cp .rosinstall-core .rosinstall

    if [ $ROS_DISTRO == "foxy" ]; then
        rosws merge --merge-replace - <.rosinstall-foxy
    fi

    if [ $ROS_DISTRO == "humble" ]; then
        rosws merge --merge-replace - < .rosinstall-humble
    fi

    if [ $ROS_DISTRO == "jazzy" ]; then
        vcs import --input .rosinstall .
        vcs import --input .rosinstall-jazzy .
    else
        rosws update
    fi
    cd ..
    
    #
    # END - Pull request specific changes
    #
    #######

fi

# Resolve the dependencies
rosdep update --rosdistro=$ROS_DISTRO -q
rosdep install -i --from-path . --ignore-src --rosdistro $ROS_DISTRO -y

cd $DIR

# Build the core
if [ "$ROS_DISTRO" == "humble" ] || [ "$ROS_DISTRO" == "jazzy" ]; then
    colcon build --packages-up-to deepracer_launcher bag_log_pkg camera_ros $COLCON_BUILD_ARGS --cmake-args $CMAKE_ARGS
else
    colcon build --packages-up-to deepracer_launcher rplidar_ros bag_log_pkg $COLCON_BUILD_ARGS --cmake-args $CMAKE_ARGS
fi

set +e
echo "Done!"
