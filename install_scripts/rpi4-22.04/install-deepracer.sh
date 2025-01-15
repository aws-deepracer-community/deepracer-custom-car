#!/usr/bin/env bash

# This script installs the necessary dependencies and software for the DeepRacer project on a Raspberry Pi.
# It performs the following steps:
# 1. Ensures the script is run with root privileges.
# 2. Sets the working directory to the script's location.
# 3. Adds the ROS 2 GPG key and repository to the system's sources list.
# 4. Installs ROS Core, development tools, and other required packages.
# 5. Initializes and updates rosdep for ROS 2 Humble.
# 6. Updates Python build tools and utilities.
# 7. Downloads and installs OpenVINO 2022.3.1.
# 8. Installs TensorFlow and other Python dependencies.
# 9. Copies AWS DeepRacer package sources and GPG key to the system.
# 10. Installs AWS DeepRacer packages.
# 11. Disables the deepracer-core service until it is ready to be used.
set -e

DEBIAN_FRONTEND=noninteractive

# Check we have the privileges we need
if [ $(whoami) != root ]; then
    echo "Please run this script as root or using sudo"
    exit 1
fi

export DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/../.. >/dev/null 2>&1 && pwd)"

# Now add the ROS 2 GPG key with apt.
# Then add the repository to your sources list.
curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key | gpg --no-default-keyring --keyring /usr/share/keyrings/ros-archive-keyring.gpg --import 
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | tee /etc/apt/sources.list.d/ros2.list >/dev/null

# Install ROS Core and Development Tools
apt -y update && apt install -y --no-install-recommends \
    cython3 \
    libboost-dev \
    libboost-filesystem-dev \
    libboost-regex-dev \
    libboost-thread-dev \
    libhdf5-dev \
    libjsoncpp-dev \
    libopencv-dev \
    libpugixml1v5 \
    libuvc0 \
    python3-argcomplete \
    python3-colcon-common-extensions \
    python3-opencv \
    python3-pip \
    python3-rosinstall \
    python3-venv \
    python3-websocket \
    ros-dev-tools \
    ros-humble-ros-core

rosdep init && rosdep update --rosdistro=humble -q

# Update build tools and utilities for Python
sudo pip3 install -U "setuptools==58.2.0" pip "Cython==0.29.28" testresources

# Get OpenVINO
mkdir -p $DIR/dist/
cd $DIR/dist/
[ ! -f "$DIR/dist/openvino_2022.3.1_arm64.tgz" ] && curl -O https://aws-deepracer-community-sw.s3.eu-west-1.amazonaws.com/openvino/openvino_2022.3.1_arm64.tgz
cd /
tar xvzf $DIR/dist/openvino_2022.3.1_arm64.tgz
ln -sf /opt/intel/openvino_2022.3.1 /opt/intel/openvino_2022
ln -sf /opt/intel/openvino_2022.3.1 /opt/intel/openvino
/opt/intel/openvino_2022.3.1/install_dependencies/install_NCS_udev_rules.sh
systemctl restart systemd-resolved

# Tensorflow and dependencies
pip3 install -U pyudev \
    "flask<3" \
    flask_cors \
    flask_wtf \
    pam \
    networkx \
    unidecode \
    pyserial \
    "tensorflow" \
    "numpy>=1.16.6,<=1.23.4" \
    "protobuf" \
    "tensorboard" \
    "blinker==1.4" \
    pyclean \
    /opt/intel/openvino_2022.3.1/tools/openvino_dev-2022.3.1-1-py3-none-any.whl \
    /opt/intel/openvino_2022.3.1/tools/openvino-2022.3.1-1-cp310-cp310-manylinux_2_35_aarch64.whl

# Install packages
cp $DIR/install_scripts/rpi4-22.04/aws_deepracer-community.list /etc/apt/sources.list.d/aws_deepracer.list
cp $DIR/install_scripts/common/deepracer-community.asc /etc/apt/trusted.gpg.d/
apt update -y && apt install -y aws-deepracer-core aws-deepracer-device-console aws-deepracer-util aws-deepracer-sample-models

# Uncomment the below to disable deepracer-core automatic start
# systemctl disable deepracer-core
