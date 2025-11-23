#!/bin/bash
#
# Pre-seal configuration script for Ubuntu 24.04 encrypted DeepRacer
# This script runs BEFORE seal_and_luksChangeKey.sh to configure the target system
# for TPM2 automatic unlocking at boot
#
# Must be run from Ubuntu 20.04 flashing system before TPM sealing
# This ensures initramfs is updated FIRST, so PCR measurements include the final boot config

VER="V1.0"

EMMC_PATH="$1"
ENCRYPT_NAME="$2"
EMMC_ROOT_PATH="$3"
Disk_PASS="$4"
SCRIPT_DIR="$5"

function usage() {
    echo "Usage: $0 <EMMC_PATH> <ENCRYPT_NAME> <EMMC_ROOT_PATH> <Disk_PASS> <SCRIPT_DIR>"
    echo "Example: $0 /dev/mmcblk1 encrypt_blk /dev/mmcblk1p3 'pega#1234' /media/usb/utils"
}

if [[ -z $EMMC_PATH ]] || [[ -z $ENCRYPT_NAME ]] || [[ -z $EMMC_ROOT_PATH ]] || [[ -z $Disk_PASS ]]; then
    echo "$(date -u) Error! Missing required parameters"
    usage
    exit 1
fi

if [[ -z $SCRIPT_DIR ]]; then
    SCRIPT_DIR="$(dirname $0)"
fi

echo "$(date -u) TPM2 pre-seal configuration version: $VER"
echo "$(date -u) eMMC Path: $EMMC_PATH"
echo "$(date -u) Encrypt Root Partition: $EMMC_ROOT_PATH"
echo "$(date -u) Encrypt Name: $ENCRYPT_NAME"
echo "$(date -u) Script Directory: $SCRIPT_DIR"

# Check that required files exist
if [ ! -f "$SCRIPT_DIR/tpm2-unseal-keyscript" ]; then
    echo "$(date -u) Error! tpm2-unseal-keyscript not found in $SCRIPT_DIR"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/tpm2-initramfs-hook" ]; then
    echo "$(date -u) Error! tpm2-initramfs-hook not found in $SCRIPT_DIR"
    exit 1
fi

# Mount the encrypted partition
echo "$(date -u) Mounting encrypted partition..."
sudo mkdir -p /mnt/emmc_root

# Try to unlock with TPM-sealed key first (if seal_and_luksChangeKey.sh removed password)
if [ -f "/tmp/new_random.key" ]; then
    echo "$(date -u) Attempting to unlock with TPM-sealed key..."
    sudo cryptsetup luksOpen ${EMMC_ROOT_PATH} ${ENCRYPT_NAME} --key-file=/tmp/new_random.key 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "$(date -u) TPM key unlock failed, trying password..."
        echo -n "${Disk_PASS}" | sudo cryptsetup luksOpen ${EMMC_ROOT_PATH} ${ENCRYPT_NAME} --key-file=-
    fi
else
    echo "$(date -u) Unlocking with password..."
    echo -n "${Disk_PASS}" | sudo cryptsetup luksOpen ${EMMC_ROOT_PATH} ${ENCRYPT_NAME} --key-file=-
fi

if [ $? -ne 0 ]; then
    echo "$(date -u) Error! Failed to unlock encrypted partition"
    exit 1
fi

# Mount the btrfs root with @ subvolume
sudo mount -o subvol=@ /dev/mapper/${ENCRYPT_NAME} /mnt/emmc_root
if [ $? -ne 0 ]; then
    echo "$(date -u) Error! Failed to mount encrypted filesystem"
    sudo cryptsetup luksClose ${ENCRYPT_NAME}
    exit 1
fi

echo "$(date -u) Installing TPM2 keyscript and initramfs hook..."

# Install the keyscript to cryptsetup scripts directory (will be included in initramfs automatically)
sudo mkdir -p /mnt/emmc_root/lib/cryptsetup/scripts
sudo cp "$SCRIPT_DIR/tpm2-unseal-keyscript" /mnt/emmc_root/lib/cryptsetup/scripts/tpm2-unseal-keyscript
sudo chmod +x /mnt/emmc_root/lib/cryptsetup/scripts/tpm2-unseal-keyscript

# Install the initramfs hook
sudo cp "$SCRIPT_DIR/tpm2-initramfs-hook" /mnt/emmc_root/etc/initramfs-tools/hooks/tpm2
sudo chmod +x /mnt/emmc_root/etc/initramfs-tools/hooks/tpm2

# Update crypttab with keyscript for TPM2 auto-unlock
echo "$(date -u) Updating crypttab for TPM2 auto-unlock..."
ROOT_UUID=$(sudo blkid -s UUID -o value ${EMMC_ROOT_PATH})
echo "${ENCRYPT_NAME} UUID=${ROOT_UUID} none luks,discard,keyscript=/lib/cryptsetup/scripts/tpm2-unseal-keyscript" | sudo tee /mnt/emmc_root/etc/crypttab > /dev/null

echo "$(date -u) Rebuilding initramfs with TPM2 support..."
# Bind mount necessary devices for chroot
sudo mount --bind /dev /mnt/emmc_root/dev
sudo mount --bind /sys /mnt/emmc_root/sys
sudo mount --bind /proc /mnt/emmc_root/proc

# Mount the boot partition
echo "$(date -u) Mounting boot partition..."
sudo mount ${EMMC_PATH}p2 /mnt/emmc_root/boot

echo "$(date -u) Running update-initramfs in chroot..."
# Rebuild initramfs in the target system
sudo chroot /mnt/emmc_root /bin/bash -c "update-initramfs -u -k all 2>&1"

REBUILD_RESULT=$?
echo "$(date -u) update-initramfs completed with exit code: $REBUILD_RESULT"

# Unmount boot partition
sudo umount /mnt/emmc_root/boot

# Cleanup bind mounts
sudo umount /mnt/emmc_root/proc
sudo umount /mnt/emmc_root/sys
sudo umount /mnt/emmc_root/dev

if [ $REBUILD_RESULT -ne 0 ]; then
    echo "$(date -u) Warning! initramfs rebuild returned error code $REBUILD_RESULT"
    echo "$(date -u) Continuing anyway..."
fi

# Cleanup
echo "$(date -u) Cleaning up..."
sudo umount /mnt/emmc_root
sudo cryptsetup luksClose ${ENCRYPT_NAME}
sudo rm -rf /mnt/emmc_root

echo "$(date -u) TPM2 pre-seal configuration complete!"
echo "$(date -u) Initramfs has been updated with TPM2 tools and keyscript"
echo "$(date -u) Ready for TPM sealing with correct PCR measurements"

exit 0
