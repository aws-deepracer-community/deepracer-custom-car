#!/usr/bin/env bash

# This script sets up the build prerequisites for the DeepRacer project on an 'empty' Ubuntu 22.04 (either arm64 or amd64).
# It performs the following steps:
# 1. Sets up the environment and directories.
# 2. Configures locale settings.
# 3. Ensures the Ubuntu Universe repository is enabled.
# 4. Adds the ROS 2 GPG key and repository.
# 5. Installs ROS Core, development tools, and other dependencies.
# 6. Sets up a Python virtual environment and installs necessary Python packages.
# 7. Installs TensorFlow and other Python dependencies.
# 8. Compiles and installs OpenVINO.

set -e

export DEBIAN_FRONTEND=noninteractive

export DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. >/dev/null 2>&1 && pwd)"

mkdir -p $DIR/deps $DIR/dist

# From https://medium.com/@nullbyte.in/raspberry-pi-4-ubuntu-20-04-lts-ros2-a-step-by-step-guide-to-installing-the-perfect-setup-57c523f9d790
sudo apt update && sudo apt install locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

# First ensure that the Ubuntu Universe repository is enabled.
sudo apt install software-properties-common curl jq
sudo add-apt-repository -y universe
sudo apt -y update && sudo apt -y upgrade

# Now add the ROS 2 GPG key with apt.
# Then add the repository to your sources list.
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list >/dev/null

# Install ROS Core and Development Tools
sudo apt -y update && sudo apt install -y \
    cython3 \
    ffmpeg \
    libboost-all-dev \
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
    ros-humble-compressed-image-transport \
    ros-humble-cv-bridge \
    ros-humble-image-transport \
    ros-humble-pybind11-vendor \
    ros-humble-ros-base \
    ros-humble-test-msgs

sudo pip3 install -U "setuptools==58.2.0" pip catkin_pkg "Cython<3"

# Builds and installs OpenVINO
# $DIR/build_scripts/build-openvino.sh
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
    defusedxml \
    pyserial \
    "tensorflow" \
    "numpy" \
    "protobuf" \
    "tensorboard" \
    $(find /opt/intel/openvino_2022.3.1/tools/ -name *.whl) \
    "empy==3.3.4" \
    "lark"

sudo rosdep init
rosdep update --rosdistro humble -q

