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
apt-mark hold linux-firmware

# Ensure we have UTF-8
locale-gen en_US en_US.UTF-8
update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

# Switch nameserver
ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf
echo "DNSStubListener=no" | tee -a /etc/systemd/resolved.conf >/dev/null
systemctl restart systemd-resolved

# Disable audio
cat > /etc/modprobe.d/blacklist-audio.conf << EOF
blacklist snd_soc_avs
blacklist snd_soc_skl
blacklist snd_hda_intel
blacklist snd_hda_codec_hdmi
blacklist snd_sof_pci_intel_apl
EOF

# Fix Wifi Stability
cat > /etc/modprobe.d/mwifiex.conf << EOF
options mwifiex disable_auto_ds=1 disable_tx_amsdu=1
EOF

# Update initramfs
update-initramfs -u

# Configure GRUB kernel parameters for DeepRacer compatibility and stability
echo -e -n "\nConfiguring GRUB boot parameters\n"
GRUB_PARAMS="net.ifnames=0 biosdevname=0 noxsave reboot=efi fsck.mode=skip"
sed -i "s/^GRUB_CMDLINE_LINUX=\".*\"/GRUB_CMDLINE_LINUX=\"${GRUB_PARAMS}\"/" /etc/default/grub
update-grub

# Firewall enable
ufw allow "OpenSSH"
ufw enable
ufw logging off

# Install other tools / configure network management
apt -y --no-install-recommends install linux-generic-hwe-24.04 url network-manager wireless-tools net-tools i2c-tools v4l-utils wpasupplicant rfkill iw
echo "" > /etc/NetworkManager/conf.d/default-wifi-powersave-on.conf
cp $DIR/build_scripts/files/dr/10-manage-wifi.conf /etc/NetworkManager/conf.d/
systemctl disable systemd-networkd-wait-online
# Copy netplan configuration if it doesn't exist
if [ ! -f /etc/netplan/01-netcfg.yaml ]; then
  cp $DIR/build_scripts/files/dr/01-netcfg.yaml /etc/netplan/01-netcfg.yaml
else
  # Replace the existing sed line with this more robust approach
  if grep -q "mlan0:" /etc/netplan/01-netcfg.yaml; then
    # Check if renderer already exists under mlan0
    if ! grep -A5 "mlan0:" /etc/netplan/01-netcfg.yaml | grep -q "renderer:"; then
      # Add renderer under mlan0 using awk
      awk '/mlan0:/{print; print "      renderer: NetworkManager"; next}1' /etc/netplan/01-netcfg.yaml > /tmp/netplan.yaml && mv /tmp/netplan.yaml /etc/netplan/01-netcfg.yaml
    fi
  else
    # If mlan0 section doesn't exist, fall back to replacing top-level renderer
    sed -i 's/renderer: networkd/renderer: NetworkManager/' /etc/netplan/01-netcfg.yaml
  fi
fi
# Set proper permissions for netplan configuration file (secure from others)
chmod 600 /etc/netplan/01-netcfg.yaml

echo -e "\nRestarting the network stack. This might require reconnection. Pi might receive a new IP address."
echo -e "After script has finished, reboot.\n"
systemctl restart NetworkManager
netplan apply
