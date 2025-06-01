#!/usr/bin/env bash
# This script fixes the ROS 2 installation on Ubuntu by ensuring the correct packages are installed and configured.
set -e
export DEBIAN_FRONTEND=noninteractive
export DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. >/dev/null 2>&1 && pwd)"
# Check we have the privileges we need
if [ $(whoami) != root ]; then
    echo "Please run this script as root or using sudo"
    exit 1
fi

# Remove old ROS keys and config
echo -e -n "\n- Remove old ROS keys and config"
apt-key del "F42E D6FB AB17 C654"
rm -f /usr/share/keyrings/ros-archive-keyring.gpg
rm -f /etc/apt/sources.list.d/ros2-latest.list

# Add new ROS repository package
echo -e -n "\n- Add new ROS repository package"
export ROS_APT_SOURCE_VERSION=$(curl -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | grep -F "tag_name" | awk -F\" '{print $4}')
curl -L -o /tmp/ros2-apt-source.deb "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.$(. /etc/os-release && echo $UBUNTU_CODENAME)_all.deb"
apt install /tmp/ros2-apt-source.deb

apt -y update