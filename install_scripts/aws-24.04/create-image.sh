#!/usr/bin/env bash
set -uoe pipefail

export DEBIAN_FRONTEND=noninteractive
export DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/../.. >/dev/null 2>&1 && pwd)"

# Default values
TARGET_DISK=""
TARGET_FILE=""
TARGET_DIR="/mnt/DEEPRACER"
CUSTOM_SHIM=""
UNMOUNT_ON_EXIT=""
UNMOUNT_ONLY=""
LOOPBACK_DEVICE=""
DISK_SIZE_GIB=8

# Function to unmount all mounts
unmount_all() {
    echo "Unmounting ${TARGET_DIR}..."
    
    # Unmount bind mounts (in reverse order)
    mountpoint -q "${TARGET_DIR}/run" && umount -l "${TARGET_DIR}/run" || true
    mountpoint -q "${TARGET_DIR}/sys" && umount -l "${TARGET_DIR}/sys" || true
    mountpoint -q "${TARGET_DIR}/proc" && umount -l "${TARGET_DIR}/proc" || true
    mountpoint -q "${TARGET_DIR}/dev/pts" && umount -l "${TARGET_DIR}/dev/pts" || true
    mountpoint -q "${TARGET_DIR}/dev" && umount -l "${TARGET_DIR}/dev" || true
    
    # Unmount EFI partition
    mountpoint -q "${TARGET_DIR}/boot/efi" && umount "${TARGET_DIR}/boot/efi" || true
    
    # Unmount root partition
    mountpoint -q "${TARGET_DIR}" && umount "${TARGET_DIR}" || true
    
    # Detach loopback device if it was set up
    if [ -n "${LOOPBACK_DEVICE}" ] && [ -e "${LOOPBACK_DEVICE}" ]; then
        echo "Detaching loopback device ${LOOPBACK_DEVICE}..."
        losetup -d "${LOOPBACK_DEVICE}" || true
    fi
    
    echo "Unmount complete"
}

# Parse command-line arguments
while getopts "d:f:m:s:uUh" opt; do
    case ${opt} in
        d )
            TARGET_DISK="${OPTARG}"
            ;;
        f )
            TARGET_FILE="${OPTARG}"
            ;;
        m )
            TARGET_DIR="${OPTARG}"
            ;;
        s )
            CUSTOM_SHIM="${OPTARG}"
            ;;
        u )
            UNMOUNT_ON_EXIT="true"
            ;;
        U )
            UNMOUNT_ONLY="true"
            ;;
        h )
            echo "Usage: $0 [-d TARGET_DISK | -f TARGET_FILE | -U ] [-m TARGET_DIR] [-s CUSTOM_SHIM] [-u]"
            echo "  -d TARGET_DISK   Target disk device (default: /dev/sdc)"
            echo "  -f TARGET_FILE   Target file for loopback device (alternative to -d)"
            echo "  -m TARGET_DIR    Target mount directory (default: /mnt/dr-disk)"
            echo "  -s CUSTOM_SHIM   Path to custom shim file (shimx64.efi.signed)"
            echo "  -u               Unmount bind mounts and target disk on exit"
            echo "  -U               Unmount only - unmount and exit without creating image"
            echo "  -h               Show this help message"
            exit 0
            ;;
        \? )
            echo "Invalid option: -${OPTARG}" 1>&2
            echo "Use -h for help"
            exit 1
            ;;
        : )
            echo "Option -${OPTARG} requires an argument" 1>&2
            exit 1
            ;;
    esac
done

# Check we have the privileges we need
if [ $(whoami) != root ]; then
    echo "Please run this script as root or using sudo"
    exit 1
fi

# Handle unmount-only mode
if [ -n "${UNMOUNT_ONLY}" ]; then
    unmount_all
    exit 0
fi

# Validate that one and only one of -d or -f is provided
if [ -n "${TARGET_DISK}" ] && [ -n "${TARGET_FILE}" ]; then
    echo "Error: Cannot specify both -d (disk) and -f (file). Please use only one."
    exit 1
elif [ -z "${TARGET_DISK}" ] && [ -z "${TARGET_FILE}" ]; then
    echo "Error: Must specify either -d (disk) or -f (file)."
    exit 1
fi

# Validate custom shim if provided
if [ -n "${CUSTOM_SHIM}" ] && [ ! -f "${CUSTOM_SHIM}" ]; then
    echo "Error: Custom shim file not found: ${CUSTOM_SHIM}"
    exit 1
fi

# Calculate partition layout based on total disk size
ESP_START_MIB=1
ESP_SIZE_MIB=127
ESP_END_MIB=$((ESP_START_MIB + ESP_SIZE_MIB))
ROOT_START_MIB=$((ESP_END_MIB + 1))
# Leave 1 MiB at the end for GPT backup table
ROOT_END_MIB=$((DISK_SIZE_GIB * 1024 - 1))
ROOT_SIZE_MIB=$((ROOT_END_MIB - ROOT_START_MIB))

# If using file mode, create the file and set up loopback device
if [ -n "${TARGET_FILE}" ]; then
    # File must be at least 1 MiB larger than the last partition end
    FILE_SIZE_MB=$((DISK_SIZE_GIB * 1024))
    
    echo "Creating image file: ${TARGET_FILE} (${FILE_SIZE_MB} MiB / ${DISK_SIZE_GIB} GiB)"
    echo "  ESP: ${ESP_START_MIB}MiB - ${ESP_END_MIB}MiB (${ESP_SIZE_MIB}MiB)"
    echo "  ROOT: ${ROOT_START_MIB}MiB - ${ROOT_END_MIB}MiB (${ROOT_SIZE_MIB}MiB)"
    dd if=/dev/zero of="${TARGET_FILE}" bs=1M count="${FILE_SIZE_MB}" status=progress
    
    echo "Setting up loopback device..."
    LOOPBACK_DEVICE=$(losetup -f --show "${TARGET_FILE}")
    echo "Loopback device: ${LOOPBACK_DEVICE}"
    
    # Use loopback device as target
    TARGET_DISK="${LOOPBACK_DEVICE}"
fi

if [ -n "${TARGET_FILE}" ]; then
    echo "Target file: ${TARGET_FILE}"
fi
echo "Target disk: ${TARGET_DISK}"
echo "Target directory: ${TARGET_DIR}"
[ -n "${CUSTOM_SHIM}" ] && echo "Custom shim: ${CUSTOM_SHIM}"
echo ""

parted --script "${TARGET_DISK}" \
    mklabel gpt \
    mkpart DR2404-ESP fat32 ${ESP_START_MIB}MiB ${ESP_END_MIB}MiB \
    set 1 esp on \
    mkpart DR2404-ROOT ext4 ${ROOT_START_MIB}MiB ${ROOT_END_MIB}MiB

# Determine partition suffix (p for devices ending in a number, empty otherwise)
if [[ "${TARGET_DISK}" =~ [0-9]$ ]]; then
    PART_SUFFIX="p"
else
    PART_SUFFIX=""
fi

mkfs.fat -F32 -n "DR2404-ESP" "${TARGET_DISK}${PART_SUFFIX}1"
mkfs.ext4 -F -L "DR2404-ROOT" "${TARGET_DISK}${PART_SUFFIX}2"

mkdir -p ${TARGET_DIR}
mount "${TARGET_DISK}${PART_SUFFIX}2" ${TARGET_DIR}
mkdir -p ${TARGET_DIR}/boot/efi
mount "${TARGET_DISK}${PART_SUFFIX}1" ${TARGET_DIR}/boot/efi

debootstrap --arch=amd64 noble ${TARGET_DIR} http://archive.ubuntu.com/ubuntu/

mount --bind /dev ${TARGET_DIR}/dev
mount --bind /dev/pts ${TARGET_DIR}/dev/pts
mount --bind /proc ${TARGET_DIR}/proc
mount --bind /sys ${TARGET_DIR}/sys
mount --bind /run ${TARGET_DIR}/run

# Copy custom shim if provided
if [ -n "${CUSTOM_SHIM}" ]; then
    mkdir -p ${TARGET_DIR}/usr/lib/shim
    
    # Copy custom shim with a distinct name
    cp "${CUSTOM_SHIM}" ${TARGET_DIR}/usr/lib/shim/shimx64.efi.signed.custom
    echo "Custom shim copied as shimx64.efi.signed.custom"
fi

ROOT_UUID=$(blkid -s UUID -o value ${TARGET_DISK}${PART_SUFFIX}2)
EFI_UUID=$(blkid -s UUID -o value ${TARGET_DISK}${PART_SUFFIX}1)

chroot ${TARGET_DIR} /bin/bash -c "
    set -uoe pipefail

    echo \"UUID=${ROOT_UUID} / ext4 defaults 0 1\" > /etc/fstab
    echo \"UUID=${EFI_UUID} /boot/efi vfat umask=0077 0 1\" >> /etc/fstab
    echo "deepracer" > /etc/hostname
    echo "127.0.0.1 localhost deepracer" > /etc/hosts
    echo "::1 localhost" >> /etc/hosts

    # Add user deepracer
    useradd -m -s /bin/bash -c 'AWS DeepRacer' deepracer
    echo 'deepracer:deepracer' | chpasswd
    usermod -aG adm deepracer
    
    # Grant deepracer user sudoers rights
    echo 'deepracer ALL=(root) NOPASSWD:ALL' >/etc/sudoers.d/deepracer
    chmod 0440 /etc/sudoers.d/deepracer

    # Ensure we have UTF-8
    locale-gen en_US en_US.UTF-8
    update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
    export LANG=en_US.UTF-8

    # First ensure that the Ubuntu repositories are enabled.
    echo deb http://archive.ubuntu.com/ubuntu noble main restricted universe >/etc/apt/sources.list
    echo deb http://archive.ubuntu.com/ubuntu noble-updates main restricted universe >>/etc/apt/sources.list
    echo deb http://archive.ubuntu.com/ubuntu noble-backports main restricted universe >>/etc/apt/sources.list
    echo deb http://security.ubuntu.com/ubuntu noble-security main restricted universe >>/etc/apt/sources.list
    apt update -y
    apt upgrade -y

    # Basic packages
    apt-get install -y --no-install-recommends \
        linux-image-generic \
        initramfs-tools \
        curl \
        gpg \
        ufw \
        openssh-server \
        network-manager \
        wireless-tools \
        net-tools \
        i2c-tools \
        v4l-utils \
        wpasupplicant \
        rfkill \
        iw \
        grub-efi-amd64 \
        shim-signed \
        zstd
    
    apt-mark hold linux-firmware

    # Register custom shim as an alternative if provided
    if [ -f /usr/lib/shim/shimx64.efi.signed.custom ]; then
        update-alternatives --install /usr/lib/shim/shimx64.efi.signed shimx64.efi.signed /usr/lib/shim/shimx64.efi.signed.custom 100
        update-alternatives --set shimx64.efi.signed /usr/lib/shim/shimx64.efi.signed.custom
        echo \"Custom shim registered and activated via alternatives system\"
    fi

    # Install and configure GRUB
    GRUB_PARAMS=\"net.ifnames=0 biosdevname=0 noxsave reboot=efi fsck.mode=skip rootwait\"
    sed -i \"s/^GRUB_CMDLINE_LINUX=.*/GRUB_CMDLINE_LINUX=\\\"\${GRUB_PARAMS}\\\"/\" /etc/default/grub
    sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT=.*/GRUB_CMDLINE_LINUX_DEFAULT=\"\"/' /etc/default/grub
    echo 'GRUB_DISABLE_OS_PROBER=true' >> /etc/default/grub
    
    grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=deepracer --recheck --no-floppy
    update-grub
    
    # Remove hardcoded disk hints from grub.cfg files (hd2,gpt2 won't exist on target system)
    sed -i \"/set root='hd/d\" /boot/grub/grub.cfg
    sed -i 's/--hint-bios=[^ ]* --hint-efi=[^ ]* --hint-baremetal=[^ ]* //' /boot/grub/grub.cfg
    
    # Fix kernel command line - replace /dev/sdX with UUID (device name won't be same on target)
    ROOT_UUID=\$(blkid -s UUID -o value /dev/disk/by-label/DR2404-ROOT)
    sed -i \"s|root=/dev/[^ ]*|root=UUID=\${ROOT_UUID}|g\" /boot/grub/grub.cfg
    
    # Fix EFI stub grub.cfg - remove disk hint from search command
    sed -i 's/ hd[0-9]*,gpt[0-9]*//' /boot/efi/EFI/deepracer/grub.cfg

    # Fix Kernel Modules / Disable audio
    echo -e \"blacklist snd_soc_avs\nblacklist snd_soc_skl\nblacklist snd_hda_intel\nblacklist snd_hda_codec_hdmi\nblacklist snd_sof_pci_intel_apl\" > /etc/modprobe.d/blacklist-audio.conf

    # Fix Wifi Stability
    echo 'options mwifiex disable_auto_ds=1 disable_tx_amsdu=1' > /etc/modprobe.d/mwifiex.conf

    # Switch nameserver
    echo 'DNSStubListener=no' | tee -a /etc/systemd/resolved.conf >/dev/null

    # Firewall
    ufw allow "OpenSSH"
    ufw --force enable
    ufw logging off

    # Don't wait for network on boot
    systemctl disable systemd-networkd-wait-online
    systemctl disable NetworkManager-wait-online.service
"

# Network Manager configuration
echo "" > ${TARGET_DIR}/etc/NetworkManager/conf.d/default-wifi-powersave-on.conf
cp $DIR/build_scripts/files/dr/10-manage-wifi.conf ${TARGET_DIR}/etc/NetworkManager/conf.d/
cp $DIR/build_scripts/files/dr/01-netcfg.yaml ${TARGET_DIR}/etc/netplan/01-netcfg.yaml
chmod 600 ${TARGET_DIR}/etc/netplan/01-netcfg.yaml

# Prepare for installation of DeepRacer packages
cp $DIR/install_scripts/aws-24.04/aws_deepracer-community.list ${TARGET_DIR}/etc/apt/sources.list.d/aws_deepracer-community.list
cp $DIR/install_scripts/common/deepracer-community.asc ${TARGET_DIR}/etc/apt/trusted.gpg.d/
cp $DIR/install_scripts/aws-24.04/rc.local ${TARGET_DIR}/etc/rc.local
chmod +x ${TARGET_DIR}/etc/rc.local

chroot ${TARGET_DIR} /bin/bash -c "
    set -uoe pipefail

    # ROS 2 GPG key and repository
    curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key | gpg --dearmor -o /usr/share/keyrings/ros-archive-keyring.gpg
    echo \"deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main\" | tee /etc/apt/sources.list.d/ros2.list >/dev/null

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
        python3-opencv \
        python3-pip \
        python3-protobuf \
        python3-pyudev \
        python3-venv \
        python3-testresources \
        python3-websocket \
        python3-networkx \
        python3-unidecode \
        python3-requests \
        ros-dev-tools \
        ros-jazzy-ros-core

    rosdep init && rosdep update --rosdistro=jazzy -q

    # Python packages, Tensorflow and dependencies
    curl -o /tmp/tensorflow-2.17.1-cp312-cp312-linux_x86_64.whl https://aws-deepracer-community-sw.s3.eu-west-1.amazonaws.com/tensorflow/tensorflow-2.17.1-cp312-cp312-linux_x86_64.whl
    pip3 install --break-system-packages \
        'flask<3' \
        flask_cors \
        flask_wtf \
        pyserial \
        /tmp/tensorflow-2.17.1-cp312-cp312-linux_x86_64.whl \
        tensorboard \
        pyclean \
        pam \
        'typing_extensions==4.10.0'
    rm /tmp/tensorflow-2.17.1-cp312-cp312-linux_x86_64.whl

    # Install OpenVINO
    wget -qO- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor -o /usr/share/keyrings/intel-openvino-2024.gpg 
    echo \"deb [signed-by=/usr/share/keyrings/intel-openvino-2024.gpg] https://apt.repos.intel.com/openvino/2024 ubuntu24 main\" | tee /etc/apt/sources.list.d/intel-openvino-2024.list >/dev/null
    apt-get update && apt-get install -y --no-install-recommends libopenvino-2024.6.0 python3-openvino-2024.6.0

    # Install DeepRacer
    apt install -y --no-install-recommends aws-deepracer-core aws-deepracer-community-device-console aws-deepracer-util aws-deepracer-sample-models

"

if [ -n "${UNMOUNT_ON_EXIT}" ]; then
    unmount_all
fi