#!/usr/bin/env bash
set -e
export DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. >/dev/null 2>&1 && pwd)"

# Parse command line arguments
CACHE="false"
while getopts "c" opt; do
    case ${opt} in
    c)
        CACHE="true"
        ;;
    \?)
        echo "Usage: cmd [-c]"
        exit 1
        ;;
    esac
done

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

# Change to build directory
cd src

if [ "$CACHE" != "true" ]; then

    # Remove previous builds (gives clean build)
    rm -rf ../install ../build ../log ../pkg-build/aws-deepracer-core

    cd external

    # Undo checkouts / patches
    for pkg_dir in $(find . -mindepth 1 -maxdepth 1 -type d); do
        cd $pkg_dir
        if [ -d .git ]; then
            git reset --hard
        fi
        cd ..
    done

    cp .rosinstall-core .rosinstall

    if [ $ROS_DISTRO == "foxy" ]; then
        rosws merge --merge-replace - <.rosinstall-foxy
    fi

    # if [ $ROS_DISTRO == "humble" ]; then
    #    rosws merge --merge-replace - < .rosinstall-humble
    # fi

    if [ $ROS_DISTRO == "jazzy" ]; then
        export PYTHONWARNINGS=ignore::DeprecationWarning
        vcs import --input .rosinstall .
        # vcs import --input .rosinstall-jazzy .
    else
        rosws update
    fi
    cd ..
    
    #
    # END - Pull request specific changes
    #
    #######

    if [[ "$(dpkg --print-architecture)" == "arm64" ]]; then

        echo "Applying patches for Raspberry Pi / arm64"

        #######
        #
        # START - PI specific patches
        #

        git apply $DIR/build_scripts/patches/aws-deepracer-i2c-pkg.rpi.patch
        git apply $DIR/build_scripts/patches/aws-deepracer-servo-pkg.rpi.patch
        git apply $DIR/build_scripts/patches/aws-deepracer-status-led-pkg.rpi.patch

        #
        # END - Patches
        #
        #######
    fi

fi

# Resolve the dependencies
rosdep update --rosdistro=$ROS_DISTRO -q
rosdep install -i --from-path . --ignore-src --rosdistro $ROS_DISTRO -y

cd $DIR

# Build the core
export PYTHONWARNINGS=ignore:::setuptools.command.install
if [ "$ROS_DISTRO" == "humble" ] || [ "$ROS_DISTRO" == "jazzy" ]; then
    colcon build --packages-up-to deepracer_launcher logging_pkg
else
    colcon build --packages-up-to deepracer_launcher rplidar_ros logging_pkg
fi

set +e
echo "Done!"
