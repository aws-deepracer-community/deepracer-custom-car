#!/usr/bin/env bash

disk=
ssid=
wifiPass=
all_disks=false
ignore_lock=false
custom_reset_url=

uuid=$(uuidgen)

url_factory_reset=https://s3.amazonaws.com/deepracer-public/factory-restore/Ubuntu20.04/BIOS-0.0.8/factory_reset.zip
url_iso=https://s3.amazonaws.com/deepracer-public/factory-restore/Ubuntu20.04/BIOS-0.0.8/ubuntu-20.04.1-20.11.13_V1-desktop-amd64.iso

#################################################################
log()
{
    [[ -z "$disk" ]] && log_disk="" || log_disk="[disk=$disk]" 
    echo "[$(date '+%Y/%m/%d %H:%M:%S')][pid=$$]$log_disk $1"
}

lock_set()
{
    log "Adding a lock file to prevent paralel execution"
    
    lock_file_path="$PWD/$0.lck.$disk"
    
    if [ ! -f ${lock_file_path} ]; then
        log "  --> Lock file doesn't exists, creating ..."
        echo $disk > $lock_file_path
    else
        if [ "$ignore_lock" = "true" ]; then
            log "  --> Disk is already in use as per lock file, ignoring lock as per command parameters ..."            
        else
            log "  --> Disk is already in use as per lock file, exiting ..."
            exit 1
        fi
    fi
}

lock_remove()
{
    lock_file_path="$PWD/$0.lck.$disk"

    if [ -f ${lock_file_path} ]; then
        log "Removing lock file for Disk Id $disk ..."
        rm $lock_file_path
    else
        log " Disk Id $disk lock file doesn't exists. Strange!!!!!"
    fi
}

donwload_file()
{
    url="$1"
    file_name=${url##*/}
    output_name="${2:-$file_name}"  # Use second parameter as output name if provided, otherwise use original filename
    dir_name="${output_name%.*}"
    
    log "Checking if ${output_name} has been downloaded ..."
    if [ ! -f ${output_name} ]; then
        log "  --> downloading from ${url} to ${output_name}"
        wget -q -O ${output_name} ${url} 2>&1 | while read line ; do log "  --> $line" ; done
        log "exit code $?"
    else
        log "  --> ${output_name} is already present"
    fi
}

unzip_file()
{
    file_name="$1"
    dir_name="${file_name%.*}"
    
    log "Checking if ${file_name} has been unzipped ..."
    if [ ! -d ${dir_name} ]; then
            log "  --> extracting ${file_name}"
            unzip -qq ${file_name} 
            ret=$?
            if [ $ret != 0 ]; then
                  log "Unexpected exit code ${ret}. Exiting ..."
                  exit 1
            fi    
    else
            log "  --> ${file_name} is already extracted"
    fi
}

get_factory_reset()
{
    # Use custom URL if provided
    local reset_url="${custom_reset_url:-$url_factory_reset}"
    
    log "Using factory reset URL: $reset_url"
    
    # Grab the zip -> $reset_url and save directly as factory_reset.zip
    donwload_file $reset_url factory_reset.zip
    unzip_file factory_reset.zip
    
    log "Adjusting flash script ..."    
    # uncomment `# reboot` on lines 520 & 528 of `usb_flash.sh`
    cp factory_reset/usb_flash.sh factory_reset/usb_flash.sh.bak
    rm -f factory_reset/usb_flash.sh
    cat factory_reset/usb_flash.sh.bak | sed -e "s/#reboot/reboot/g" > factory_reset/usb_flash.sh
    log "  --> done"
}

get_iso()
{
    # Grab the ISO -> $url_iso
    donwload_file $url_iso
}

download_files()
{
    get_factory_reset
    get_iso
}
#################################################################
show_usage()
{
    log ""
    log "Usage: "
    log ""
    log "  $0 (-d <disk id> | -a) [ -s <SSID> -w <WIFI_PASSWORD>] [-l] [-r <RESET_URL>]"
    log ""
    log "  -d <disk id>       : selected usb device id on which the content will be created (required if -a is not used)"
    log "  -a                 : select all usb device id (required if -d is not used)"
    log "  -s <SSID>          : wifi ssid (optional, but requires -w when used)"
    log "  -w <WIFI_PASSWORD> : wifi password(optional, but requires -s when used)"
    log "  -l                 : ignore lock file (optional)"
    log "  -r <RESET_URL>     : custom factory reset URL (optional)"
    log ""
}
show_disk()
{
    log  ""
    log "List of available usb devices:"
    log  ""
    lsblk -o name,tran,size | grep -v " loop.*snap" | grep usb | while read line ; do log "  --> $line" ; done
    log  ""
}
get_usb_device_size()
{
    device_name="$1"
    device_size="$(lsblk -o name,tran,size | grep -v " loop.*snap" | grep usb | grep "$device_name  " | awk '{print $3}' )"
    if [ -z "$device_size" ]; then
        # if nothing returned then set to -1
        device_size=-1
    else
        # remove last character (G)
        device_size=${device_size::-1}
    # replace , by . incase you are using a differnt decimal separator, then extract the integer value
        device_size=$(echo $device_size | sed -r 's/,/./g' | xargs printf "%.*f\n" "$p")
    fi
}
create_partitions()
{
    sudo parted /dev/$disk -s -a optimal -- mktable msdos mklabel msdos                                  2>&1 | while read line ; do log "  --> $line" ; done
    sudo parted /dev/$disk -s -a optimal -- mkpart primary fat32 1MiB 4GiB   2>&1 | while read line ; do log "  --> $line" ; done
    sudo parted /dev/$disk -s -a optimal -- mkpart primary fat32 4GiB 5GiB   2>&1 | while read line ; do log "  --> $line" ; done
    sudo parted /dev/$disk -s -a optimal -- mkpart primary NTFS  5GiB 25GiB  2>&1 | while read line ; do log "  --> $line" ; done

    sudo parted /dev/$disk set 1 boot on 2>&1 | while read line ; do log "  --> $line" ; done

}
format_partitions()
{
    sudo mkfs.vfat   /dev/$(echo $disk)1 -n "BOOT"        2>&1 | while read line ; do log "  --> [dev/$(echo $disk)1] $line" ; done 
    sudo mkfs.vfat   /dev/$(echo $disk)2 -n "DEEPRACER"   2>&1 | while read line ; do log "  --> [dev/$(echo $disk)2] $line" ; done 
    sudo mkfs.exfat  /dev/$(echo $disk)3 -n "FLASH"       2>&1 | while read line ; do log "  --> [dev/$(echo $disk)3] $line" ; done 
}
mount_partitions()
{
    sudo rm -rf $mnt_boot      > /dev/null 2>&1
    sudo rm -rf $mnt_deepracer > /dev/null 2>&1
    sudo rm -rf $mnt_flash     > /dev/null 2>&1

    sudo mkdir -p $mnt_boot      > /dev/null 2>&1
    sudo mkdir -p $mnt_deepracer > /dev/null 2>&1
    sudo mkdir -p $mnt_flash     > /dev/null 2>&1

    sudo mount /dev/$(echo $disk)1   $mnt_boot      > /dev/null 2>&1
    sudo mount /dev/$(echo $disk)2   $mnt_deepracer > /dev/null 2>&1
    sudo mount /dev/$(echo $disk)3   $mnt_flash     > /dev/null 2>&1
}
unmount_partitions()
{
    sudo ls /dev/$disk[1-99] 2> /dev/null | xargs -n1 sudo umount -l > /dev/null 2>&1
    
    sudo rm -rf $mnt_boot      > /dev/null 2>&1
    sudo rm -rf $mnt_deepracer > /dev/null 2>&1
    sudo rm -rf $mnt_flash     > /dev/null 2>&1    
}
mount_dr_iso()
{
    log "Mounting DeepRacer ISO Ubuntu in $mnt_iso"
    is_mounted=$(mount | grep "${url_iso##*/} on $mnt_iso")
    if [ -z "$is_mounted" ]; then
        log "  --> not mounted, mounting ${url_iso##*/} at $mnt_iso"
        sudo rm   -rf $mnt_iso      > /dev/null 2>&1
        sudo mkdir -p $mnt_iso      > /dev/null 2>&1
        sudo mount -o loop ${url_iso##*/}   $mnt_iso      > /dev/null 2>&1
    else
        log "  --> already mounted, skipping $is_mounted"
    fi    
}
unmount_dr_iso()
{
    log "Unounting DeepRacer ISO Ubuntu in $mnt_iso"
    lock_cnt=$(ls -la *.lck.* 2>/dev/null | wc -l)
    if [[ ${lock_cnt} -eq  "1" ]]; then
        log "  --> Unmounting"
        sudo umount ${url_iso##*/} 
        sudo rm -rf $mnt_iso > /dev/null 2>&1        
    else 
        log "  --> some process are still running ($lock_cnt lock files present)."
        log "  --> Do you want to unmount anyway? (y/n)"
        while true; do
            read -p "" yn
            case $yn in
                [Yy]* ) log "  --> unmounting"; sudo umount ${url_iso##*/} ; sudo rm -rf $mnt_iso ; break;;
                [Nn]* ) log "  --> exiting without unmounting";break;;
                * ) log "Please answer yes/y or no/n.";;
            esac
        done
    fi
  
}
check_packages(){
    need_install=false
    
    # Check Ubuntu version
    ubuntu_version=$(lsb_release -rs)
    log "Detected Ubuntu version: $ubuntu_version"
    
    # Base packages needed in all versions
    packages="mtools parted pv dosfstools syslinux"
    
    # Version-specific packages
    if [ "$(echo "$ubuntu_version >= 22.04" | bc)" -eq 1 ]; then
        # For Ubuntu 22.04 and newer
        packages="$packages exfatprogs"
    else
        # For older Ubuntu versions
        packages="$packages exfat-utils"
    fi
    
    # Check which packages need installation
    for package in $packages; do
        dpkg-query -W -f='${Package}\n' | grep "^$package$" > /dev/null
        if [ $? != 0 ]; then
            need_install=true
            log "  --> Package $package needs to be installed"
        fi
    done
    
    if [ "$need_install" = "true" ]; then
        log "  -> Installing additional packages ..."
        sudo apt update -y 2>&1 | while read line; do log "  --> $line"; done
        for package in $packages; do
            sudo apt-get --ignore-missing -o DPkg::Lock::Timeout=-1 install $package -y -qq 2>&1 | while read line; do log "  --> $line"; done
        done
    else
        log "  -> All additional packages are already installed..."
    fi
}
#################################################################
process_all(){
    disk_cnt=$(lsblk -o name,tran | grep usb | cut -d' ' -f1 | wc -l)

    if [ "$disk_cnt" -eq 0 ]; then
        log "Unable to find disk devices! Exiting ..."
        exit 1
    fi

    log "You selected to execute the script on all attached USB drives below."

    show_disk

    log "Are you sure ? (y/n)"

    while true; do
        read -p "" yn
        case $yn in
            [Yy]* ) break;;
            [Nn]* ) exit 0;;
            * ) log "Please answer yes/y or no/n.";;
        esac
    done

    trap 'kill $(jobs -pr) 2>/dev/null' SIGINT SIGTERM EXIT

    while IFS= read -r result
    do
        log "Starting USB Build script for USB device $result"
        arg_wifi="-s $ssid -w $wifiPass"
        if [[ -z "$ssid" ]]; then
            arg_wifi=""
        else 
            arg_wifi="-s $ssid -w $wifiPass"
        fi
        if [ "$ignore_lock" = "true" ]; then
            arg_ignore_lock="-l"
        else
            arg_ignore_lock=""
        fi
        
        if [ -n "$custom_reset_url" ]; then
            arg_reset_url="-r $custom_reset_url"
        else
            arg_reset_url=""
        fi

        $0 -d $result $arg_wifi $arg_ignore_lock $arg_reset_url &
        pids="$pids $!"
    done < <(lsblk -o name,tran | grep usb | cut -d' ' -f1 )

    RESULT=0
    for pid in $pids; do
        wait $pid || let "RESULT=1"
    done

    if [ "$RESULT" == "0" ]; then
        log "Execution completed without issues."
    else
        log "One of the execition failed. Please check the logs."
    fi
}
#################################################################
process(){
    if [ "$all_disks" = "true" ]; then
        process_all
        exit 0
    fi

    mnt_flash="/media/ubuntu/FLASH-$uuid"
    mnt_boot="/media/ubuntu/BOOT-$uuid"
    mnt_deepracer="/media/ubuntu/DEEPRACER-$uuid"
    mnt_iso="/media/ubuntu/DEEPRACER-UBUNTU-ISO"

    # check sudo permission, and add to sudoer with no password if not there yet
    sudo_response=$(SUDO_ASKPASS=/bin/false sudo -A whoami 2>&1 | wc -l)
    if [ $sudo_response = 2 ]; then
        can_sudo=1
    elif [ $sudo_response = 1 ]; then
        can_sudo=0
    else
        log "Unexpected sudo response: $sudo_response" >&2
        exit 1
    fi

    if [[ "$EUID" != 0 ]]; then
        sudo -k # make sure to ask for password on next sudo
        if sudo true; then
            sudo_ok=1        
            sudoer_user_file="/etc/sudoers.d/dont-prompt-$USER-for-sudo-password"
            if [ ! -f "$sudoer_user_file" ]; then
                log "Adding current user to sudoers nopasswd list"
                echo "$USER ALL=(ALL:ALL) NOPASSWD: ALL" | sudo tee $sudoer_user_file > /dev/null 2>&1 
            fi     

        else
            log "Please provide the sudo password"
            exit 1
        fi
    fi

    # check if the device exists and its size, must be bigger than 25GB
    get_usb_device_size $disk

    if [ "$device_size" -lt 0 ]; then
        log "Unable to find the provided disk device : $disk"
        show_usage
        show_disk
        exit 1
    fi

    if [ "$device_size" -lt "25" ]; then
        log "USB device is too small. It must be at least 25GB!"        
        show_usage
        show_disk
        exit 1
    fi

    lock_set

    log "Checking if required packages are installed ..."
    check_packages

    log "Unmounting device existing partitions ..."
    unmount_partitions

    log "Erasing device current partition table ..."
    sudo dd if=/dev/zero of=/dev/$disk bs=4k count=100 status=progress 2>&1 | while read line ; do log "  --> $line" ; done
    sudo sync 2>&1 | while read line ; do log "  --> $line" ; done
    sudo wipefs --all --force /dev/$disk 2>&1 | while read line ; do log "  --> $line" ; done 

    log "Creating new partitions ..."
    create_partitions

    log "Informing the OS of partition table changes using partprobe ..."
    sudo partprobe /dev/$disk 2>&1 | while read line ; do log "  --> $line" ; done 

    if ! sudo mkfs.vfat /dev/$(echo $disk)1 > /dev/null 2>&1  ; then
        log "Unable to use to format the partitions."
        log "Consider using a different USB port or retry in little while."
        log "Exiting ..."
        lock_remove
        exit 1
    fi

    log "Formating the device partitions ..."
    format_partitions

    log "Downloading file ..."
    download_files

    log "Mounting the partitions & iso ..."
    mount_partitions
    mount_dr_iso
        
    log "Generating the FLASH partition content using rsync with factory_reset ..."
    sudo rsync -rDvz   --out-format="[%t][pid=$$][disk=$disk]  --> %n (size: %''l)" --progress --human-readable                  factory_reset/* $mnt_flash 2>&1 # | while read line ; do log "  --> $line" ; done 
    
    log "Generating the BOOT partition content using rsync with the ubuntu iso ..."
    sudo cp -TRP $mnt_iso $mnt_boot 2>&1 | while read line ; do log "  --> $line" ; done 
    sudo sync

    # Create wifi-creds.txt for auto network goodness
    if [ ! -z "$ssid" ] && [ ! -z "$wifiPass" ]; then
        log "Generating the DEEPRACER partition content with WiFi credentials ..."
        (
            echo "ssid: ${ssid}" 
            echo "password: ${wifiPass}" 
        ) | sudo tee $mnt_deepracer/wifi-creds.txt > /dev/null 2>&1
    fi

    log "Displaying fdisk details ..."
    sudo fdisk -l /dev/$disk 2>&1 | while read line ; do log "  --> $line" ; done 
    log "Displaying lsblk details ..."
    sudo lsblk /dev/$disk -o name,fstype,label,size,mountpoint,partflags,partlabel 2>&1 | while read line ; do log "  --> $line" ; done 

    log "Unmounting device partitions ..."
    unmount_partitions
    unmount_dr_iso

    log "Ejecting the disk ..."
    sudo eject /dev/$disk

    usb=$(find /sys/bus/usb/devices/usb*/ -name dev | grep "/$disk/dev")
    log "You can now remove your device : "
    log "  --> USB port id     : $(echo ${usb##*/usb} | cut -d/ -f 1)"
    log "  --> USB port host   : $(echo ${usb##*/host} | cut -d/ -f 1)"
    log "  --> USB port target : $(echo ${usb##*/target} | cut -d/ -f 1)"

    lock_remove 
}
#################################################################

# check if you are running ubuntu or macos darwin, and if not exit
if [[ $OSTYPE == 'linux'* ]]; then
    if [  -n "$(uname -a | grep Ubuntu)" ]; then
        log "Detected Ubuntu system"

        optstring=":d:s:w:r:al"
        while getopts $optstring arg; do
            case ${arg} in
                a) all_disks=true;;
                l) ignore_lock=true;;
                d) disk=${OPTARG};;
                s) ssid=${OPTARG};;
                w) wifiPass=${OPTARG};;
                r) custom_reset_url=${OPTARG};;
                ?) show_usage ;exit 1;
            esac
        done
        if [ $OPTIND -eq 1 ]; then
            log "No options selected."
            show_usage
            exit 1
        fi

        process

    else
        log "Detected a non Ubuntu system"
        log "  --> -> Unfortunately this script is only compatible with Ubuntu like systems"
        exit 0   
    fi
elif [[ $OSTYPE == 'darwin'* ]]; then
    log "Detected Mac OS system"
    log "  --> -> Unfortunately this script is only compatible with Ubuntu like systems"
    exit 0
fi

log "Done"
exit 0
