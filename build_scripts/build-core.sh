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
    source /opt/ros/foxy/setup.bash
elif [ -f /opt/ros/humble/setup.bash ]; then
    ROS_DISTRO="humble"
    source /opt/ros/humble/setup.bash
else
    echo "Unsupported ROS version"
    exit 1
fi
echo "Detected ROS version: $ROS_DISTRO"

# Set the OpenVINO environment
if [ -f /opt/intel/openvino_2021/bin/setupvars.sh ]; then
    source /opt/intel/openvino_2021/bin/setupvars.sh
elif [ -f /opt/intel/openvino_2022/setupvars.sh ]; then
    source /opt/intel/openvino_2022/setupvars.sh
else
    echo "Unsupported OpenVINO version"
    exit 1
fi

# Change to build directory
cd src

if [ "$CACHE" != "true" ]; then

    rosdep update --rosdistro=$ROS_DISTRO -q

    # Remove previous builds (gives clean build)
    rm -rf ../install ../build ../log

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

    rosws update

    #######
    #
    # START - Pull request specific changes
    #

    # Update packages for PR's
    # https://github.com/aws-deepracer/aws-deepracer-inference-pkg/pull/4
    cd aws-deepracer-inference-pkg
    git fetch origin pull/5/head:tflite
    git checkout tflite
    cd ..

    # https://github.com/aws-deepracer/aws-deepracer-camera-pkg/pull/5
    cd aws-deepracer-camera-pkg
    git fetch origin pull/5/head:compressed-image
    git checkout compressed-image
    cd ..

    # https://github.com/aws-deepracer/aws-deepracer-interfaces-pkg/pull/4
    cd aws-deepracer-interfaces-pkg
    git fetch origin pull/4/head:compressed-image
    git checkout compressed-image
    cd ..

    # https://github.com/aws-deepracer/aws-deepracer-sensor-fusion-pkg/pull/4
    cd aws-deepracer-sensor-fusion-pkg
    git fetch origin pull/4/head:compressed-image
    git checkout compressed-image
    cd ..

    # https://github.com/aws-deepracer/aws-deepracer-model-optimizer-pkg/pull/2
    cd aws-deepracer-model-optimizer-pkg
    git fetch origin pull/3/head:tflite
    git checkout tflite
    cd ..

    # https://github.com/aws-deepracer/aws-deepracer-i2c-pkg/pull/3
    cd aws-deepracer-i2c-pkg
    git fetch origin pull/3/head:dummy
    git checkout dummy
    cd ..

    # Patch with aws-deepracer-ctrl-pkg.patch
    cd aws-deepracer-ctrl-pkg
    git apply $DIR/build_scripts/patches/aws-deepracer-ctrl-pkg.patch
    cd ..

    # Resolve the dependencies
    rosdep install -i --from-path . --ignore-src --rosdistro $ROS_DISTRO -y

    #
    # END - Pull request specific changes
    #
    #######

    if [ "$ROS_DISTRO" == "humble" ]; then

        echo "Applying patches for ROS 2 Humble"

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

        cd aws-deepracer-webserver-pkg/
        git apply $DIR/build_scripts/patches/aws-deepracer-webserver-pkg.rpi.patch
        cd ..

        cd aws-deepracer-inference-pkg/
        git apply $DIR/build_scripts/patches/aws-deepracer-inference-pkg.rpi.patch
        cd ..

        cd aws-deepracer-model-optimizer-pkg/
        git apply $DIR/build_scripts/patches/aws-deepracer-model-optimizer-pkg.rpi.patch
        cd ..

        cd aws-deepracer-sensor-fusion-pkg/
        git apply $DIR/build_scripts/patches/aws-deepracer-sensor-fusion-pkg.rpi.patch
        cd ..

        cd aws-deepracer-usb-monitor-pkg/
        git apply $DIR/build_scripts/patches/aws-deepracer-usb-monitor-pkg.rpi.patch
        cd ..

        cd aws-deepracer-navigation-pkg/
        git apply $DIR/build_scripts/patches/aws-deepracer-navigation-pkg.rpi.patch
        cd ..

        cd aws-deepracer-device-info-pkg/
        git apply $DIR/build_scripts/patches/aws-deepracer-device-info-pkg.rpi.patch
        cd ..

        #
        # END - Patches
        #
        #######
    fi

    # Update deepracer_launcher.py (fix an issue in the file)
    cp $DIR/build_scripts/files/common/deepracer_launcher.py ./aws-deepracer-launcher/deepracer_launcher/launch/deepracer_launcher.py

    # Turn off SW update
    sed -i "s/ENABLE_PERIODIC_SOFTWARE_UPDATE = True/ENABLE_PERIODIC_SOFTWARE_UPDATE = False/" aws-deepracer-systems-pkg/deepracer_systems_pkg/deepracer_systems_pkg/software_update_module/software_update_config.py

fi

cd ..

# Build the core
export PYTHONWARNINGS=ignore:::setuptools.command.install
colcon build --packages-up-to deepracer_launcher

# Build the add-ons
colcon build --packages-up-to logging_pkg

set +e
echo "Done!"
