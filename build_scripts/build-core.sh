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

    rosdep update --rosdistro=$ROS_DISTRO -q

    # Remove previous builds (gives clean build)
    rm -rf ../install ../build ../log

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

    if [ $ROS_DISTRO == "humble" ]; then
        rosws merge --merge-replace - < .rosinstall-humble
    fi

    if [ $ROS_DISTRO == "jazzy" ]; then
        export PYTHONWARNINGS=ignore::DeprecationWarning
        vcs import --input .rosinstall .
        vcs import --input .rosinstall-jazzy .
    else
        rosws update
    fi
    cd ..
    

    # Resolve the dependencies
    rosdep install -i --from-path . --ignore-src --rosdistro $ROS_DISTRO -y

    #
    # END - Pull request specific changes
    #
    #######

    #######
    #
    # START - Common patches
    #
    #######

    # Apply common improvement patches
    cd aws-deepracer-ctrl-pkg
    git apply $DIR/build_scripts/patches/aws-deepracer-ctrl-pkg.patch
    cd ..

    cd aws-deepracer-camera-pkg
    git apply $DIR/build_scripts/patches/aws-deepracer-camera-pkg.patch
    cd ..

    cd aws-deepracer-device-info-pkg/
    git apply $DIR/build_scripts/patches/aws-deepracer-device-info-pkg.patch
    cd ..

    cd aws-deepracer-inference-pkg/
    git apply $DIR/build_scripts/patches/aws-deepracer-inference-pkg.patch
    cd ..

    cd aws-deepracer-navigation-pkg/
    git apply $DIR/build_scripts/patches/aws-deepracer-navigation-pkg.patch
    cd ..

    cd aws-deepracer-usb-monitor-pkg/
    git apply $DIR/build_scripts/patches/aws-deepracer-usb-monitor-pkg.patch
    cd ..

    cd aws-deepracer-status-led-pkg/
    git apply $DIR/build_scripts/patches/aws-deepracer-status-led-pkg.patch
    cd ..

    cd aws-deepracer-servo-pkg/
    git apply $DIR/build_scripts/patches/aws-deepracer-servo-pkg.patch
    cd ..

    cd aws-deepracer-sensor-fusion-pkg/
    git apply $DIR/build_scripts/patches/aws-deepracer-sensor-fusion-pkg.patch
    cd ..

    cd aws-deepracer-systems-pkg/
    git apply $DIR/build_scripts/patches/aws-deepracer-systems-pkg.patch
    cd ..

    cd aws-deepracer-webserver-pkg/
    git apply $DIR/build_scripts/patches/aws-deepracer-webserver-pkg.patch
    cd ..
    #######
    #
    # END - Common patches
    #
    #######

    if [ "$ROS_DISTRO" == "humble" ] || [ "$ROS_DISTRO" == "jazzy" ]; then

        echo "Applying patches for Raspberry Pi / ROS 2 Humble & Jazzy"

        #######
        #
        # START - PI specific patches
        #

        cd aws-deepracer-i2c-pkg/
        git apply $DIR/build_scripts/patches/aws-deepracer-i2c-pkg.rpi.patch
        cd ..

        cd aws-deepracer-servo-pkg/
        git apply $DIR/build_scripts/patches/aws-deepracer-servo-pkg.rpi.patch
        cd ..

        cd aws-deepracer-systems-pkg/
        git apply $DIR/build_scripts/patches/aws-deepracer-systems-pkg.rpi.patch
        cd ..

        cd aws-deepracer-status-led-pkg/
        git apply $DIR/build_scripts/patches/aws-deepracer-status-led-pkg.rpi.patch
        cd ..

        cd aws-deepracer-model-optimizer-pkg/
        git apply $DIR/build_scripts/patches/aws-deepracer-model-optimizer-pkg.rpi.patch
        cd ..

        #
        # END - Patches
        #
        #######
    fi

    # Update deepracer_launcher.py (fix an issue in the file)
    cp $DIR/build_scripts/files/common/deepracer_launcher.py ./aws-deepracer-launcher/deepracer_launcher/launch/deepracer_launcher.py

fi

cd ..

# Build the core
export PYTHONWARNINGS=ignore:::setuptools.command.install
if [ "$ROS_DISTRO" == "humble" ] || [ "$ROS_DISTRO" == "jazzy" ]; then
    colcon build --packages-up-to deepracer_launcher logging_pkg camera_ros
else
    colcon build --packages-up-to deepracer_launcher rplidar_ros logging_pkg
fi

set +e
echo "Done!"
