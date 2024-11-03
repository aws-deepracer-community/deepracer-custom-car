#!/usr/bin/env bash

DEBIAN_FRONTEND=noninteractive

usage() {
    echo "Usage: sudo $0 -h HOSTNAME -p PASSWORD"
    exit 0
}

# Check we have the privileges we need
if [ $(whoami) != root ]; then
    echo "Please run this script as root or using sudo"
    exit 0
fi

oldHost=NULL
varHost=NULL
varPass=NULL

backupDir=/home/deepracer/backup
if [ ! -d ${backupDir} ]; then
    mkdir ${backupDir}
fi

optstring=":h:p:"

while getopts $optstring arg; do
    case ${arg} in
    h) varHost=${OPTARG} ;;
    p) varPass=${OPTARG} ;;
    ?) usage ;;
    esac
done

# Stop DeepRacer Stack
systemctl stop deepracer-core

# Disable IPV6 on all interfaces
echo -e -n "\nDisable IPV6\n"
cp /etc/sysctl.conf ${backupDir}/sysctl.conf.bak
printf "net.ipv6.conf.all.disable_ipv6 = 1" >>/etc/sysctl.conf

# Update the DeepRacer console password
if [ $varPass != NULL ]; then
    echo -e -n "\n\nUpdating password to: $varPass \n"
    tempPass=$(echo -n $varPass | sha224sum)
    IFS=' ' read -ra encryptedPass <<<$tempPass
    cp /opt/aws/deepracer/password.txt ${backupDir}/password.txt.bak
    printf "${encryptedPass[0]}" >/opt/aws/deepracer/password.txt
fi

# Grant deepracer user sudoers rights
echo deepracer ALL=\(root\) NOPASSWD:ALL >/etc/sudoers.d/deepracer
chmod 0440 /etc/sudoers.d/deepracer

# Check version
. /etc/lsb-release
if [ $DISTRIB_RELEASE = "16.04" ]; then
    echo 'Ubuntu 16.04 detected'
    echo "Please update your car to 20.04 -> https://docs.aws.amazon.com/deepracer/latest/developerguide/deepracer-ubuntu-update-preparation.html"
    exit 1

elif [ $DISTRIB_RELEASE = "20.04" ]; then
    echo 'Ubuntu 20.04 detected'

    bundlePath=/opt/aws/deepracer/lib/device_console/static
    webserverPath=/opt/aws/deepracer/lib/webserver_pkg/lib/python3.8/site-packages/webserver_pkg
    systemPath=/opt/aws/deepracer/lib/deepracer_systems_pkg/lib/python3.8/site-packages/deepracer_systems_pkg

else
    echo 'Not sure what version of OS, terminating.'
    exit 1
fi

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

# Get latest key from ROS
curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | tee /etc/apt/sources.list.d/ros2-latest.list >/dev/null

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

# If changing hostname need to change the flag in network_config.py
# /opt/aws/deepracer/lib/deepracer_systems_pkg/lib/python3.8/site-packages/deepracer_systems_pkg/network_monitor_module/network_config.py
# SET_HOSTNAME_TO_CHASSIS_SERIAL_NUMBER = False
if [ $DISTRIB_RELEASE = "20.04" ]; then
    if [ $varHost != NULL ]; then
        echo -e -n "\nSet hostname: ${varHost}\n"
        oldHost=$HOSTNAME
        hostnamectl set-hostname ${varHost}
        cp /etc/hosts ${backupDir}/hosts.bak
        rm /etc/hosts
        cat ${backupDir}/hosts.bak | sed -e "s/${oldHost}/${varHost}/" >/etc/hosts

        cp ${systemPath}/network_monitor_module/network_config.py ${backupDir}/network_config.py.bak
        rm ${systemPath}/network_monitor_module/network_config.py
        cat ${backupDir}/network_config.py.bak | sed -e "s/SET_HOSTNAME_TO_CHASSIS_SERIAL_NUMBER = True/SET_HOSTNAME_TO_CHASSIS_SERIAL_NUMBER = False/" >${systemPath}/network_monitor_module/network_config.py

    fi

fi

# Allow multiple logins on the console
echo -e -n "\nEnable multiple logins to the console\n"
cp /etc/nginx/sites-enabled/default ${backupDir}/default.bak
rm /etc/nginx/sites-enabled/default
cat ${backupDir}/default.bak | sed -e "s/auth_request \/auth;/#auth_request \/auth;/" >/etc/nginx/sites-enabled/default

# Change the cookie duration
echo -e -n "\nUpdate the cookie duration\n"
cp $webserverPath/login.py ${backupDir}/login.py.bak
rm $webserverPath/login.py
cat ${backupDir}/login.py.bak | sed -e "s/datetime.timedelta(hours=1)/datetime.timedelta(hours=12)/" >$webserverPath/login.py

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
#  [ + ]  uuidd
#  [ + ]  wd_keepalive

# Restart services
echo 'Restarting services'
systemctl start deepracer-core
service nginx restart

echo "Done!"
