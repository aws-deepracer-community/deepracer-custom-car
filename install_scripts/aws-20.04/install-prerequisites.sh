#!/usr/bin/env bash

DEBIAN_FRONTEND=noninteractive

# Check we have the privileges we need
if [ $(whoami) != root ]; then
    echo "Please run this script as root or using sudo"
    exit 0
fi

# Check version
. /etc/lsb-release
if [ $DISTRIB_RELEASE = "16.04" ]; then
    echo 'Ubuntu 16.04 detected'
    echo "Please update your car to 20.04 -> https://docs.aws.amazon.com/deepracer/latest/developerguide/deepracer-ubuntu-update-preparation.html"
    exit 1

elif [ $DISTRIB_RELEASE = "20.04" ]; then
    echo 'Ubuntu 20.04 detected'
else
    echo 'Not sure what version of OS, terminating.'
    exit 1
fi

# Stop DeepRacer Stack
systemctl stop deepracer-core

# Disable IPV6 on all interfaces
echo -e -n "\nDisable IPV6\n"
cp /etc/sysctl.conf ${backupDir}/sysctl.conf.bak
printf "net.ipv6.conf.all.disable_ipv6 = 1" >>/etc/sysctl.conf

# Grant deepracer user sudoers rights
echo deepracer ALL=\(root\) NOPASSWD:ALL >/etc/sudoers.d/deepracer
chmod 0440 /etc/sudoers.d/deepracer

# Disable system suspend
echo -e -n "\nDisable system suspend\n"
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target

# Disable network power saving
echo -e -n "\nDisable network power saving"
echo -e '#!/bin/sh\n/usr/sbin/iw dev mlan0 set power_save off\n' >/etc/network/if-up.d/disable_power_saving
chmod 755 /etc/network/if-up.d/disable_power_saving

# Enable SSH
echo -e -n "\nEnable SSH\n"
service ssh start
ufw allow ssh

# Disable Gnome and other services
# - to enable gnome - systemctl set-default graphical
# - to start gnome -  systemctl start gdm3
systemctl stop bluetooth
systemctl stop cups-browsed

# Disable X on startup
echo -e -n "\nSet console-only at startup\n"
systemctl set-default multi-user.target

echo -e -n "\nUpdating car...\n"

# Get latest key from OpenVINO
curl -o GPG-PUB-KEY-INTEL-SW-PRODUCTS https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB
apt-key add GPG-PUB-KEY-INTEL-SW-PRODUCTS

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

# Update package lists
echo -e -n "\nUpdating Ubuntu packages\n"
apt update

# Remove unnecessary packages - first hold the smaller versions
apt-mark manual ubuntu-standard ros-foxy-ros-base libboost-all-dev
snap remove gnome-3-34-1804 gtk-common-themes snap-store && snap remove core18 && snap remove snapd
apt purge -y ubuntu-desktop ubuntu-desktop-minimal ubuntu-wallpapers ros-foxy-desktop firefox-locale-en firefox fonts-indic gnome-shell gnome-keyring gnome-terminal gnome-control-center language-pack-gnome-en-base wbritish wamerican mplayer hplip gvfs snapd

echo -e -n "\nRemove redundant packages\n"
apt autoremove -y --purge

# Update Ubuntu
apt upgrade -o Dpkg::Options::="--force-overwrite" -o Dpkg::Options::='--force-confold' -y

# Additional packages
apt install -y --no-install-recommends python3-websocket python3-click

# Remove redundant packages
apt autoremove -y

# Remove Swap
swapoff -a
sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab
rm /swapfile

# Default running service list
# service --status-all | grep '\[ + \]'
#  [ + ]  alsa-utils
#  [ + ]  apparmor
#  [ + ]  avahi-daemon
#  [ + ]  cron
#  [ + ]  dbus
#  [ + ]  dnsmasq
#  [ + ]  fail2ban
#  [ + ]  irqbalance
#  [ + ]  isc-dhcp-server
#  [ + ]  kmod
#  [ + ]  network-manager
#  [ + ]  nginx
#  [ + ]  procps
#  [ + ]  rsyslog
#  [ + ]  ssh
#  [ + ]  system-init
#  [ + ]  udev
#  [ + ]  ufw
#  [ + ]  watchdog

# Restart services
echo 'Restarting services'
systemctl start deepracer-core
service nginx restart

echo "Done!"
