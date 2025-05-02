#!/usr/bin/env bash

# This script installs prerequisites for setting up a Raspberry Pi with Ubuntu.
# It performs the following steps:
# 1. Checks if the script is run with root privileges.
# 2. Sets up the working directory.
# 3. Stops and removes unattended-upgrades to prevent automatic updates during setup.
# 4. Ensures the Ubuntu Universe repository is enabled.
# 5. Installs necessary packages including software-properties-common, curl, locales, and others.
# 6. Configures locale settings to en_US.UTF-8.
# 7. Enables PWM / PCA9685 on I2C address 0x40.
# 8. Switches the nameserver to use systemd-resolved.
# 9. Configures and enables the firewall to allow OpenSSH.
# 10. Installs additional tools and configures network management.
# 11. Copies a custom NetworkManager configuration file.
# 12. Disables systemd-networkd-wait-online service.
# 13. Adjusts WiFi power save settings and network renderer.
# 14. Restarts the network stack and applies netplan configuration.
# 15. Provides instructions for enabling legacy camera support and rebooting the system.
set -e

export DEBIAN_FRONTEND=noninteractive

# Check we have the privileges we need
if [ $(whoami) != root ]; then
    echo "Please run this script as root or using sudo"
    exit 1
fi

export DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/../.. >/dev/null 2>&1 && pwd)"

# Grant deepracer user sudoers rights
if [ -n "${SUDO_USER}" ]; then
    echo ${SUDO_USER} ALL=\(root\) NOPASSWD:ALL >/etc/sudoers.d/${SUDO_USER}
    chmod 0440 /etc/sudoers.d/${SUDO_USER}
fi

mkdir -p $DIR/dist

systemctl stop unattended-upgrades
apt update -y && apt remove -y --autoremove unattended-upgrades needrestart

# First ensure that the Ubuntu Universe repository is enabled.
add-apt-repository -y universe
apt update -y && apt upgrade -y

# From https://medium.com/@nullbyte.in/raspberry-pi-4-ubuntu-20-04-lts-ros2-a-step-by-step-guide-to-installing-the-perfect-setup-57c523f9d790
locale-gen en_US en_US.UTF-8
update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

# Enable PWM / PCA9685 on I2C 0x40
echo "dtoverlay=i2c-pwm-pca9685a,addr=0x40" | tee -a /boot/firmware/config.txt

# Switch nameserver
ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf
echo "DNSStubListener=no" | tee -a /etc/systemd/resolved.conf >/dev/null
systemctl restart systemd-resolved

# Firewall enable
ufw allow "OpenSSH"
ufw enable

# Install other tools / configure network management
apt -y --no-install-recommends install curl network-manager wireless-tools net-tools i2c-tools v4l-utils libraspberrypi-bin
cp $DIR/build_scripts/files/pi/10-manage-wifi.conf /etc/NetworkManager/conf.d/
systemctl disable systemd-networkd-wait-online

sed -i 's/wifi.powersave = 3/wifi.powersave = 2/' /etc/NetworkManager/conf.d/default-wifi-powersave-on.conf
# Replace the existing sed line with this more robust approach
if grep -q "wlan0:" /etc/netplan/50-cloud-init.yaml; then
  # Check if renderer already exists under wlan0
  if ! grep -A5 "wlan0:" /etc/netplan/50-cloud-init.yaml | grep -q "renderer:"; then
    # Add renderer under wlan0 using awk
    awk '/wlan0:/{print; print "      renderer: NetworkManager"; next}1' /etc/netplan/50-cloud-init.yaml > /tmp/netplan.yaml && mv /tmp/netplan.yaml /etc/netplan/50-cloud-init.yaml
  fi
else
  # If wlan0 section doesn't exist, fall back to replacing top-level renderer
  sed -i 's/renderer: networkd/renderer: NetworkManager/' /etc/netplan/50-cloud-init.yaml
fi
echo -e "\nRestarting the network stack. This might require reconnection. Pi might receive a new IP address."
echo -e "After script has finished, reboot.\n"
systemctl restart NetworkManager
netplan apply
