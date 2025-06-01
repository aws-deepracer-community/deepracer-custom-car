#!/usr/bin/env bash

set -e

export DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/../.. >/dev/null 2>&1 && pwd)"

# Check we have the privileges we need
if [ $(whoami) != root ]; then
    echo "Please run this script as root or using sudo"
    exit 0
fi

# Build the core packages
systemctl stop deepracer-core

# DeepRacer Repos
cp $DIR/install_scripts/common/deepracer-community.asc /etc/apt/trusted.gpg.d/
cp $DIR/install_scripts/aws-20.04/aws_deepracer-community.list /etc/apt/sources.list.d/
apt update
apt upgrade -y

# Install GPU driver
/opt/intel/openvino_2021/install_dependencies/install_NEO_OCL_driver.sh -y

# Update DR
apt -y install aws-deepracer-core aws-deepracer-community-device-console

# Restart deepracer
systemctl start deepracer-core
