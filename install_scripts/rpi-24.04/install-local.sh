#!/usr/bin/env bash

# Build the core packages
sudo systemctl stop deepracer-core

# Clean up older install
if [[ -d /opt/aws/deepracer/lib.custom ]]; then
    echo "Custom install exists. Deleting."
    sudo rm -rf /opt/aws/deepracer/lib.custom
fi

# Copy the build
echo "Copy files"
sudo cp -Rp $(pwd)/install /opt/aws/deepracer/lib.custom

# Copy in the console code
echo "Copying console code"
sudo cp -Rp /opt/aws/deepracer/lib/device_console /opt/aws/deepracer/lib.custom/

# Disable automatic video playing
sudo sed -i "s/isVideoPlaying\: true/isVideoPlaying\: false/" /opt/aws/deepracer/lib.custom/device_console/static/bundle.js

# Create logs directory
sudo mkdir -p /opt/aws/deepracer/logs

# Re-point start to custom stack
sudo sed -i "s/\/opt\/aws\/deepracer\/lib\/setup.bash/\/opt\/aws\/deepracer\/lib.custom\/setup.bash/g" /opt/aws/deepracer/start_ros.sh

# Doublecheck all dependencies (useful on remote install)
sudo rosdep install -i --from-path /opt/aws/deepracer/lib.custom/ --rosdistro humble -y

# Restart deepracer
sudo systemctl restart deepracer-core
