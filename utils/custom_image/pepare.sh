# Description: This script is used to create a custom image for the AWS DeepRacer.
# It needs to be run as root or with sudo privileges.

# Expand the filesystems onto an empty disk (e.g., /dev/sdc)
# This script assumes that the disk is empty and does not contain any partitions.
# The encrypted partition is assumed to be /dev/sdc3, and is mounted on /mnt/DEEPRACER.
dcfldd if=dlrc_image_21WW09.5_tpm.img of=/dev/sdc bs=1M conv=notrunc statusinterval=1000
cryptsetup luksOpen --allow-discards /dev/sdc3 encrypt_blk
mkdir -p /mnt/DEEPRACER
mount -o subvol=@ /dev/mapper/encrypt_blk /mnt/DEEPRACER

# Mount the necessary filesystems to enable chroot and networking
mount -t proc /proc /mnt/DEEPRACER/proc
mount -t sysfs /sys /mnt/DEEPRACER/sys
mount --bind /dev /mnt/DEEPRACER/dev
mount --bind /dev/pts /mnt/DEEPRACER/dev/pts
mount --bind /run /mnt/DEEPRACER/run

# Move adjust_image.sh to the root directory of the mounted filesystem
cp adjust_image.sh /mnt/DEEPRACER/root/
chmod +x /mnt/DEEPRACER/root/adjust_image.sh

#### RUN THE CUSTOMIZATION SCRIPT IN CHROOT ####

# Clean up
rm /mnt/DEEPRACER/root/.bash_history
rm /mnt/DEEPRACER/root/*
rm /mnt/DEEPRACER/tmp/.*
rm /mnt/DEEPRACER/tmp/*
rm /mnt/DEEPRACER/opt/aws/deepracer/password.txt

# Unmount the filesystems, close the encrypted partition, and create the image
umount /mnt/DEEPRACER/dev/pts 
umount /mnt/DEEPRACER/dev
umount /mnt/DEEPRACER/proc
umount /mnt/DEEPRACER/run
umount /mnt/DEEPRACER/sys

# Resize the filesystem and partition
btrfs filesystem resize -8g /mnt/DEEPRACER
parted /dev/sdc resizepart 3 8249212927B ### MANUAL STEP
cryptsetup resize /dev/mapper/encrypt_blk

# Unmount the encrypted partition and close it
umount /mnt/DEEPRACER
cryptsetup luksClose encrypt_blk

# Create the image file
dcfldd if=/dev/sdc of=dlrc_image_20250529.1_tpm.img bs=4M count=$((8249212927/4194304+1)) conv=notrunc statusinterval=1000

