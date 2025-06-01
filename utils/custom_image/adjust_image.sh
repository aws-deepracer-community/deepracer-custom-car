# Update OpenVINO
echo -e -n "\nUpdate OpenVINO\n"
curl -o GPG-PUB-KEY-INTEL-SW-PRODUCTS https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB
apt-key add GPG-PUB-KEY-INTEL-SW-PRODUCTS
rm GPG-PUB-KEY-INTEL-SW-PRODUCTS

# Add new ROS repository package
echo -e -n "\nAdd new ROS repository package"
export ROS_APT_SOURCE_VERSION=$(curl -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | grep -F "tag_name" | awk -F\" '{print $4}')
curl -L -o /tmp/ros2-apt-source.deb "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.$(. /etc/os-release && echo $UBUNTU_CODENAME)_all.deb"
apt install /tmp/ros2-apt-source.deb

# Community Packages
echo -e -n "\nAdd Community Packages\n"
curl -sSL https://raw.githubusercontent.com/aws-deepracer-community/deepracer-custom-car/refs/heads/main/install_scripts/common/deepracer-community.asc -o /etc/apt/trusted.gpg.d/deepracer-community.asc
curl -sSL https://raw.githubusercontent.com/aws-deepracer-community/deepracer-custom-car/refs/heads/main/install_scripts/aws-20.04/aws_deepracer-community.list -o /etc/apt/sources.list.d/aws_deepracer-community.list

# Update the package cache
apt update

# Install the required packages
apt-mark hold linux-image-deeplens linux-generic-hwe-20.04
apt-mark manual ubuntu-standard ros-foxy-ros-base libboost-all-dev

# Remove snap
apt remove -y snapd 
rm -rf /var/snap /var/lib/snapd /var/cache/snapd /snap
rm $(find /etc/systemd/system -name snap*)

# Remove unnecessary packages
apt purge -y ubuntu-desktop ubuntu-desktop-minimal ubuntu-wallpapers ros-foxy-desktop firefox-locale-en firefox fonts-indic gnome-shell gnome-keyring gnome-terminal gnome-control-center language-pack-gnome-en-base wbritish wamerican mplayer hplip gvfs
apt autoremove -y --purge
apt upgrade -y -o Dpkg::Options::="--force-overwrite" -o Dpkg::Options::='--force-confold' 
apt install -y --no-install-recommends python3-websocket python3-click aws-deepracer-community-device-console
apt autoremove -y --purge
apt clean

# Disable IPV6 on all interfaces
echo -e -n "\nDisable IPV6\n"
printf "net.ipv6.conf.all.disable_ipv6 = 1" >>/etc/sysctl.conf

# Grant deepracer user sudoers rights
echo deepracer ALL=\(root\) NOPASSWD:ALL >/etc/sudoers.d/deepracer
chmod 0440 /etc/sudoers.d/deepracer

# Disable system suspend
echo -e -n "\nDisable system suspend\n"
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target

# Disable X on startup
echo -e -n "\nSet console-only at startup\n"
systemctl set-default multi-user.target

# Disable network power saving
echo -e -n "\nDisable network power saving"
echo -e '#!/bin/sh\n/usr/sbin/iw dev mlan0 set power_save off\n' >/etc/network/if-up.d/disable_power_saving
chmod 755 /etc/network/if-up.d/disable_power_saving

# Remove Swap
swapoff -a
sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab
rm /swapfile

# Clean-up
echo -e -n "\nClean-up\n"
rm -rf /var/lib/apt/lists/*
rm -rf /root/.ros
rm -rf /root/.cache
rm /var/log/dpkg.log