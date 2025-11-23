#!/bin/bash
VER="V1.1"
IMAGE="dlrc_image_noble_20251122.1_tpm.img"
IMAGE_MD5="dlrc_image_noble_20251122.1_tpm.md5"

#Default encrypt setting
Disk_PASS="pega#1234"
ENCRYPT_NAME="encrypt_blk"
OTG_LABEL_NAME="DEEPRACER"
#OTG_LABEL_NAME="DEEPLENS"

CHECK_MD5=1
SEAL_TPM=1
FSCK_MMCBLK=1
OTG_ENABLE=0
RESIZE=1



#Partition Define
if [ $SEAL_TPM == 1 ]; then
  ROOT_PARTITION="p3"
  OTG_PARTITION="p4"
  ROOT_PARTITION_NUMBER="3"
  OTG_PARTITION_NUMBER="4"
else
  ROOT_PARTITION="p2"
  OTG_PARTITION="p3"
  ROOT_PARTITION_NUMBER="2"
  OTG_PARTITION_NUMBER="3"
fi       

#TPM define
PCR_DAT="DLRC_0.0.8_21WW09.5_pcr_fuse.dat"
#SIGN_PUBLIC_KEY_DER="pubkey.der.aws"
SIGN_PUBLIC_KEY_DER="DLRC_rootCA.crt.pubkey.der"
#RANDOM_KEY="aa.key"
TPM_SCRIPT="seal_and_luksChangeKey.sh"

BIOS_VER=$(echo ${PCR_DAT} | cut -d "_" -f 2)

#8G OTG partition for 32G eMMC
OTG_PART=$[8*1024*1024*1024/512] #sectes

#8G OTG partition for 32G eMMC
OTG_PART_B=$[8*1024*1024]  #K bytes

#500M sectors OTG partition for 16G eMMC
#OTG_PART=$[500*1024*1024/512] #K bytes

#500M OTG partition for 32G eMMC
#OTG_PART_B=$[500*1024]  #K bytes

#OTG Threshold for check OTG partition 100M
OTG_THRESHOLD=$[100 * 1024 ] #K bytes

echo $(date -u) "USB flash version : $VER"

keyCreat(){ 
   echo "keyCreat"
   mkdir -p /media/ubuntu/DEEPRACER_ROOT
   if [ $RESIZE_ENCRYPT_PARTITION == 1 ]; then
       sudo mount -o subvol=@ /dev/mapper/${ENCRYPT_NAME} /media/ubuntu/DEEPRACER_ROOT 
   else
       sudo mount ${EMMC_ROOT_PATH} /media/ubuntu/DEEPRACER_ROOT   
   fi
   
   echo "Creat ssl key and password.txt for UI login"
   sudo -S openssl req -x509 -nodes -days 3650 -newkey rsa:2048 -keyout /media/ubuntu/DEEPRACER_ROOT/etc/ssl/private/nginx-selfsigned.key -out /media/ubuntu/DEEPRACER_ROOT/etc/ssl/certs/nginx-selfsigned.crt -subj '/C=US/ST=Washington/L=Seattle/O=Amazon.com Inc./OU=Amazon Web Services/CN=deepracer.io'

  sudo -S python `dirname $0`/dlrc_key.py 
  sudo -S python `dirname $0`/set_hostname.py
  if sudo test ! -f /media/ubuntu/DEEPRACER_ROOT/etc/ssl/private/nginx-selfsigned.key; then
    echo "Creat nginx-selfsigned.key fail"
  elif sudo test ! -f /media/ubuntu/DEEPRACER_ROOT/etc/ssl/certs/nginx-selfsigned.crt; then
    echo "Creat nginx-selfsigned.crt fail"
  elif sudo test ! -f /media/ubuntu/DEEPRACER_ROOT/opt/aws/deepracer/password.txt; then
    echo "Creat password.txt fail"
  else
    echo "key Creat success"
  fi
  sync
  sudo umount -f /media/ubuntu/DEEPRACER_ROOT
}

setHostname(){ 
   echo "setHostname"
   sudo mkdir -p /media/ubuntu/DEEPRACER_ROOT
   if [ $RESIZE_ENCRYPT_PARTITION == 1 ]; then
       sudo mount -o subvol=@ /dev/mapper/${ENCRYPT_NAME} /media/ubuntu/DEEPRACER_ROOT 
   else
       sudo mount ${EMMC_ROOT_PATH} /media/ubuntu/DEEPRACER_ROOT   
   fi
   
  sudo -S python `dirname $0`/set_hostname.py
  sleep 2
  sync
  sudo umount -f /media/ubuntu/DEEPRACER_ROOT
}

OTGFileCreat(){ 
  echo "CreatOTGFile"
  mkdir -p /media/ubuntu/DEEPRACER
  sudo mount ${EMMC_OTG_PATH} /media/ubuntu/DEEPRACER
  sudo mkdir -p /media/ubuntu/DEEPRACER/models
  if [ -d /media/ubuntu/DEEPRACER/models ]; then
    echo "Creat OTG models folder success"
  else
    echo "Creat OTG models folder fail"
  fi

  if [ ! -f /media/ubuntu/DEEPRACER/wifi-creds.txt ]; then
      sudo bash -c "echo \"ssid     : <wifi-ssid>\" > /media/ubuntu/DEEPRACER/wifi-creds.txt"
      sudo bash -c "echo \"password : <wifi-password>\" >> /media/ubuntu/DEEPRACER/wifi-creds.txt"
      echo "Check wifi-creds.txt"
      cat /media/ubuntu/DEEPRACER/wifi-creds.txt
      if [ $? != 0 ]; then
        echo "Creat wifi-creds.txt fail"
      else
        echo "Creat wifi-creds.txt success"
      fi
  fi 

  sudo umount -f /media/ubuntu/DEEPRACER
}

OTGPartitionCheck(){
  echo "OTG Partition Check"
  sudo mount  ${EMMC_OTG_PATH} /mnt
  echo "=========df OTG Partiion==========="
  sudo  df -h ${EMMC_OTG_PATH}
  OTG_SIZE=`sudo  df  ${EMMC_OTG_PATH} |grep ${EMMC_OTG_PATH} | awk '{print $2}'`
  echo "OTG_SIZE : $[$OTG_SIZE / 1024 ] M"
  sudo umount -f ${EMMC_OTG_PATH}
  echo "OTG Threshold range : $[($OTG_PART_B - $OTG_THRESHOLD)/1024]M ~ $[($OTG_PART_B + $OTG_THRESHOLD)/1024]M"
  echo "OTG_PART_B $OTG_PART_B"
  if [ $OTG_SIZE -gt $[$OTG_PART_B  + $OTG_THRESHOLD] ] || 
     [ $OTG_SIZE -lt $[$OTG_PART_B  - $OTG_THRESHOLD] ]; then
    echo "OTG Partition size check FAIL"
  else
    echo "OTG Partition size check PASS"
  fi
  echo "==================================="
}

ResizeEncryptPartition(){
  echo $(date -u) "Resize encrypt partition"
  #Fix partition table
  printf 'x\ne\nw\nY\n' | sudo gdisk ${EMMC_PATH}
  #MMC_TOTLE_SIZE=`sudo parted ${EMMC_PATH} print free Fix | grep "Disk ${EMMC_PATH}" | cut -d' ' -f3`
  MMC_TOTLE_SIZE=`echo "Fix" | sudo parted ${EMMC_PATH} ---pretend-input-tty print free | grep "Disk ${EMMC_PATH}" | cut -d' ' -f3`
  MMC_TOTLE_SECTORS_SIZE=`sudo fdisk -l ${EMMC_PATH} | grep "Disk ${EMMC_PATH}" | cut -d' ' -f 7`
  #Reserv OTG Partition
  ROOT_END_SIZE=$[$MMC_TOTLE_SECTORS_SIZE - $OTG_PART] 
  ROOT_END_SIZE_K=$[$ROOT_END_SIZE * 512 / 1024]

  echo "MMC_TOTAL_SIZE $MMC_TOTLE_SIZE"
  echo "MMC_TOTLE_SECTORS_SIZE $MMC_TOTLE_SECTORS_SIZE"
  echo "ROOT_END_SIZE $ROOT_END_SIZE"
  echo "ROOT_END_SIZE_K $ROOT_END_SIZE_K"

  #Update partition table
  sudo partprobe ${EMMC_PATH}
  echo -n "${Disk_PASS}" | sudo cryptsetup luksOpen --allow-discards ${EMMC_ROOT_PATH} ${ENCRYPT_NAME} --key-file=-
  if [ -L /dev/mapper/${ENCRYPT_NAME} ]; then
    echo $(date -u) "Resize encrypt partition"

    
    if [ $OTG_ENABLE == 1 ]; then
      echo $(date -u) "Resize encrypt and OTG partition"
      echo "EMMC_OTG_PATH : ${EMMC_OTG_PATH}" 
      OTG_PARTITION=`sudo fdisk -l ${EMMC_PATH} | grep ${EMMC_OTG_PATH}`
      echo "$OTG_PARTITION"
      if test -n "$OTG_PARTITION"; then
        echo "Remove old OTG partition table and resize"
        #Remove old OTG partition table and resize
        sudo parted ${EMMC_PATH} rm ${OTG_PARTITION_NUMBER} 
      fi

      #Reload partition table
      sudo partprobe ${EMMC_PATH}
        
      #Resize root partition table
      sudo parted ${EMMC_PATH} resizepart ${ROOT_PARTITION_NUMBER} ${ROOT_END_SIZE}s

      #Reload partition table
      sudo partprobe ${EMMC_PATH}
        
      #Resize root btrfs encrypt partition
      sudo cryptsetup resize ${ENCRYPT_NAME}
      sudo mount /dev/mapper/${ENCRYPT_NAME} /mnt
      sudo btrfs filesystem resize max /mnt

      #Creat new OTG partition table and format OTG partition
      (
        echo n
        echo
        echo
        echo
        echo w
      )|sudo fdisk ${EMMC_PATH}
      sudo partprobe ${EMMC_PATH}
      sudo mkfs.fat ${EMMC_OTG_PATH}
      #Reload partition table
      sudo partprobe ${EMMC_PATH}

      #Add OTG partition label
      echo "mtools_skip_check=1" > ~/.mtoolsrc
      sudo mlabel -i ${EMMC_OTG_PATH} ::$OTG_LABEL_NAME
    else
      echo $(date -u) "Resize encrypt partition"

      #Resize root btrfs encrypt partition
      echo "step-1"
      sudo parted ${EMMC_PATH} resizepart ${ROOT_PARTITION_NUMBER} ${MMC_TOTLE_SIZE}
      echo "step-2"
      #sudo cryptsetup resize ${ENCRYPT_NAME}
      echo -n "${Disk_PASS}" | sudo cryptsetup resize ${ENCRYPT_NAME}
      echo "step-3"
      sudo mount /dev/mapper/${ENCRYPT_NAME} /mnt
      echo "step-4"
      sudo btrfs filesystem resize max /mnt   
    fi
  fi     
    sudo btrfs check /dev/mapper/${ENCRYPT_NAME}
    sudo btrfs filesystem show

    #List Partition information
    echo "==========df Root Partition========"
    sudo btrfs filesystem df /mnt
    sudo df -h /dev/mapper/${ENCRYPT_NAME}
    echo "==================================="
    sudo umount -f /mnt
    echo "==============fdisk================"
    sudo fdisk -l ${EMMC_PATH}
    echo "==================================="
    echo "==============parted==============="
    sudo parted ${EMMC_PATH} print free
    echo "==================================="
    sudo partprobe ${EMMC_PATH}
    sleep 1
    #keyCreat
    setHostname
    if [ $OTG_ENABLE == 1 ]; then
      keyCreat
      OTGFileCreat
      OTGPartitionCheck
    fi  
    sudo cryptsetup luksClose ${ENCRYPT_NAME}
}

ResizePartition(){
  echo $(date -u) "Resize partition"
  #Fix partition table

  printf 'x\ne\nw\nY\n' | sudo gdisk ${EMMC_PATH}
  #MMC_TOTLE_SIZE=`sudo parted ${EMMC_PATH} print free fix| grep "Disk ${EMMC_PATH}" | cut -d' ' -f3`
  MMC_TOTLE_SIZE=`echo "Fix" | sudo parted ${EMMC_PATH} ---pretend-input-tty print free | grep "Disk ${EMMC_PATH}" | cut -d' ' -f3`
  MMC_TOTLE_SECTORS_SIZE=`sudo fdisk -l ${EMMC_PATH} | grep "Disk ${EMMC_PATH}" | cut -d' ' -f 7`
  #Reserv OTG Partition
  ROOT_END_SIZE=$[$MMC_TOTLE_SECTORS_SIZE - $OTG_PART]

  echo "MMC_TOTAL_SIZE $MMC_TOTLE_SIZE"
  echo "MMC_TOTLE_SECTORS_SIZE : $MMC_TOTLE_SECTORS_SIZE"
  echo "ROOT_END_SIZE : $ROOT_END_SIZE"

  if [ $OTG_ENABLE == 1 ]; then
    echo $(date -u) "Resize root and OTG partition"

    echo "EMMC_OTG_PATH : ${EMMC_OTG_PATH}" 
    OTG_PARTITION=`sudo fdisk -l ${EMMC_PATH} | grep ${EMMC_OTG_PATH}`
    echo "$OTG_PARTITION"
    if test -n "$OTG_PARTITION"; then
      #Remove old OTG partition table and resize
      echo "Remove old OTG partition table and resize"
      sudo parted ${EMMC_PATH} rm ${OTG_PARTITION_NUMBER} 
    fi
    
    #Reload partition table
    sudo partprobe ${EMMC_PATH}

    #Resize root partition 
    sudo parted ${EMMC_PATH} resizepart ${ROOT_PARTITION_NUMBER} ${ROOT_END_SIZE}s
    sudo e2fsck -fy ${EMMC_ROOT_PATH}
    sudo resize2fs ${EMMC_ROOT_PATH}
    #sudo parted /dev/mmcblk1 mkpart OTG ${OTG_Start}s 100%
    (
      echo n
      echo
      echo
      echo
      echo w
    )|sudo fdisk ${EMMC_PATH}
    sudo partprobe ${EMMC_PATH}
    sudo mkfs.fat ${EMMC_OTG_PATH}
    #Reload partition table
    sudo partprobe ${EMMC_PATH}

    #Add OTG partition label  
    echo "mtools_skip_check=1" > ~/.mtoolsrc
    sudo mlabel -i ${EMMC_OTG_PATH} ::$OTG_LABEL_NAME
  
  else
    #Resize root partition 
    sudo partprobe ${EMMC_PATH}
    sudo parted ${EMMC_PATH} resizepart ${ROOT_PARTITION_NUMBER} ${MMC_TOTLE_SIZE}
    sudo e2fsck -fy ${EMMC_ROOT_PATH}
    sudo resize2fs ${EMMC_ROOT_PATH}

  fi   
    echo "==============fdisk================"
    sudo fdisk -l ${EMMC_PATH}
    echo "==================================="
    echo "==============parted==============="
    sudo parted ${EMMC_PATH} print free   
    echo "===================================" 
    sudo mount  ${EMMC_ROOT_PATH} /mnt
    echo "==========df Root Partition========"
    sudo df -h ${EMMC_ROOT_PATH}
    echo "==================================="
    sudo umount -f ${EMMC_ROOT_PATH}
    sleep 1
    setHostname
    if [ $OTG_ENABLE == 1 ]; then
      keyCreat
      OTGFileCreat
      OTGPartitionCheck
    fi
}

RemoveOldPartitionTable(){
  sudo sgdisk --zap-all --clear --mbrtogpt -g ${EMMC_PATH}
  sudo partprobe ${EMMC_PATH}
}


IFS=$'\n'

BIOS=`cat /sys/class/dmi/id/bios_version`
     
if [ "$BIOS" == "0.0.6" ]; then
PCR_DAT="DLRC_0.0.6_21WW09.5_pcr_fuse.dat"
BIOS_VER=$(echo ${PCR_DAT} | cut -d "_" -f 2)
fi

for mtabline in `cat /etc/mtab`; do 
  DEVICE=`echo $mtabline | cut -f 1 -d ' '`
  UDEV_LINE=`udevadm info -q path -n $DEVICE 2>&1 |grep usb` 
  
  if [ $? == 0 ] ; then
    DEV_PATH=`echo $mtabline | cut -f 2 -d ' '`
    #echo "DEV_PATH: $DEV_PATH"

    declare -a FILE=($(find $DEV_PATH -name "${IMAGE}"))
    declare -a MD5=($(find $DEV_PATH -name "${IMAGE_MD5}"))
    
    declare -a PCR_DAT_PATH=($(find $DEV_PATH -name "${PCR_DAT}"))
    declare -a SIGN_PUBLIC_KEY_DER_PATH=($(find $DEV_PATH -name "${SIGN_PUBLIC_KEY_DER}"))
    declare -a RANDOM_KEY_PATH=($(find $DEV_PATH -name "${RANDOM_KEY}"))
    declare -a TPM_SCRIPT_PATH=($(find $DEV_PATH -name "${TPM_SCRIPT}"))
    

    if  [ -f ${FILE[0]} ] && [[ -n ${FILE[0]} ]]; then
      IMG_MD5=`cat $MD5 | cut -d' ' -f 1`
     # EMMC_PATH=`sudo blkid | grep "gpt" | cut -d' ' -f 1 | tr -d ":"`
      EMMC_PATH=`sudo blkid /dev/mmc* | grep "gpt" | cut -d' ' -f 1 | tr -d ":"`
      EMMC_ROOT_PATH=${EMMC_PATH}${ROOT_PARTITION}
      EMMC_OTG_PATH=${EMMC_PATH}${OTG_PARTITION}
      HASH_SIZE=`sudo fdisk -l ${EMMC_PATH} | grep "Disk ${EMMC_PATH}" | cut -d' ' -f 5`
      Encrypt_Check=`echo ${FILE[0]} | grep -i tpm`
  
      #check image encrypt or not
      if test -n "$Encrypt_Check"; then
        RESIZE_ENCRYPT_PARTITION=1
      else
        RESIZE_ENCRYPT_PARTITION=0
      fi

      #set log file
      LOG_FILE="$DEV_PATH/result.log"
      exec &> >(tee ${LOG_FILE} ) 

      echo $(date -u) "Check Bios version match?"
      BIOS=`cat /sys/class/dmi/id/bios_version`
     
      if [ ! "$BIOS" == "$BIOS_VER" ]; then 
        echo $(date -u) "Current BIOS version is $BIOS not match require version $BIOS_VER"
        echo $(date -u) "Please update BIOS to match version then do again"
        exit 1;
      fi
      echo $(date -u) "Current BIOS version is $BIOS match require"

      SB=$(od -An -t u2 /sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c | awk '{print $3}')
      #if [ "$SB" -eq 1 ]; then
      # $SB=1 is SB on $SB=0 is SB off
      if [ "$SB" -eq 1 ]; then
         echo $(date -u) "This is fuse board match require"
         #echo SB on
      else
         #echo SB off
         echo $(date -u) "This is unfuse board no match require"
         echo $(date -u) "Please change to fuse board then do again"
         exit 1;
      fi

      echo $(date -u) "USB flash version : $VER"
      echo $(date -u) "Image file ${FILE[0]} exists."
      echo $(date -u) "Image MD5       : $IMG_MD5."
      if [ $SEAL_TPM == 1 ]; then
        echo $(date -u) "PCR_DAT_PATH    : $PCR_DAT_PATH"
        echo $(date -u) "SIGN_PUBLIC_KEY_DER_PATH : $SIGN_PUBLIC_KEY_DER_PATH"
        echo $(date -u) "RANDOM_KEY_PATH : $RANDOM_KEY_PATH"
        echo $(date -u) "TPM_SCRIPT_PATH : $TPM_SCRIPT_PATH"
      fi
      if [ $RESIZE == 1 ]; then
        echo $(date -u) "OTG Function :    $OTG_ENABLE"
        if [ $OTG_ENABLE == 1 ]; then
          echo $(date -u) "OTG Partition Size :  $[$OTG_PART * 512 / 1024 / 1024] MB" 
        fi
        echo $(date -u) "Resize Encrype Partition : $RESIZE_ENCRYPT_PARTITION"
      fi
      
      echo "System image will auto recovery after 10 sec...."
      echo "Are you sure you want to recovery system image? (y/n)"
      read -t 10 ANS 
      case $ANS in
          n | N | no | NO )
            echo $(date -u) "Cancel recovery system image"
            sleep 2
            exit 1;; 
          *) 
            echo $(date -u) "Recovery system image...now"
            echo $(date -u) "eMMC Path : $EMMC_PATH"
            echo $(date -u) "Root Partition Path :   $EMMC_ROOT_PATH"
            if [ $OTG_ENABLE == 1 ]; then
              echo $(date -u) "OTG Partition Path :    $EMMC_OTG_PATH"
            fi 
            if [[ -z $EMMC_PATH ]]; then
                echo $(date -u) "Can not find GPT partition table"
                exit 1;			
            fi
            
            sudo umount -f /dev/mmcblk*

            #Remove old partition
            RemoveOldPartitionTable
            
            #Format old partition
            DISK_LIST=`sudo fdisk -l $EMMC_PATH | grep $EMMC_PATH | cut -d' ' -f1 | sed -e '1d'`
            if test -z "$DISK_LIST"; then
               echo "Format Disk : $EMMC_PATH"
               printf 'y\n' | sudo mkfs $EMMC_PATH
            else
                for list in $DISK_LIST; do
                    echo "Format Disk : $list"
                    printf 'y\n' | sudo mkfs $list
                done
            fi
            
            #dd tool       
            #sudo dd if=${FILE[0]} of=${EMMC_PATH} bs=10M status=progress 
            #time gzip -dc ${FILE[0]} | sudo dd of=${EMMC_PATH} bs=10M status=progress
            
            #dcfldd tool   
            time sudo dcfldd if=${FILE[0]} of=${EMMC_PATH} conv=notrunc statusinterval=1000 md5log=dd.md5 hashconv=after errlog=dd_error.log hashwindow=$HASH_SIZE
            #time gzip -dc ${FILE[0]} | sudo dcfldd of=${EMMC_PATH} conv=notrunc,sync statusinterval=1000  md5log=dd.md5 hashconv=after errlog=dd_error.log hashwindow=$HASH_SIZE
            
            sync
            echo $(date -u) "===========Result==========="
            echo $(date -u) "Recovery image finish..."
            if [ $CHECK_MD5 == 1 ]; then
                echo $(date -u) "Check MD5..."
                if  [ -f "dd.md5" ] && [[ -n "dd.md5" ]]; then
                    DD_MD5=`cat dd.md5 | head -n 1 | cut -d' ' -f 4`
                    echo $(date -u) "Hash size      :$HASH_SIZE"
                    echo $(date -u) "Image MD5      :$IMG_MD5"
                    echo $(date -u) "DD finish MD5  :$DD_MD5"
                    if  [ $IMG_MD5 == $DD_MD5 ]; then
                        echo $(date -u) "MD5 verify PASS"
                        FSCK_MMCBLK=1
                        MD5_PASS=1
                    else
                        echo $(date -u) "MD5 verify FAIL"
                        echo $(date -u) "Please download again"
                  RESIZE=0
                        FSCK_MMCBLK=0
                        MD5_PASS=0
                    fi
                else
                    echo $(date -u) "Download FAIL, Can not find DD finish MD5, ignore the MD5 check"  
                    echo $(date -u) "Please download again"
                fi
            fi
            echo $(date -u) "===========================" 
            if [ $RESIZE == 1 ]; then
              if [ $RESIZE_ENCRYPT_PARTITION == 1 ]; then
                ResizeEncryptPartition
              else
                ResizePartition   
              fi
            fi
            
            if [ $FSCK_MMCBLK == 1 ]; then
              echo $(date -u) "fsck mmcblk"	
              #sudo fdisk -l /dev/mmcblk1 | grep /dev/mmcblk1 | cut -d' ' -f1

              sudo fsck -fy ${EMMC_PATH}p1
              sudo fsck -fy ${EMMC_PATH}p2
              sudo fsck -fy ${EMMC_PATH}p3
              sync		
            fi
              
            if [ $MD5_PASS == 1 ]; then
              if [ $SEAL_TPM == 1 ]; then
                # Run pre-seal configuration for Ubuntu 24.04 FIRST
                # This updates initramfs so PCRs will be measured correctly
                PRE_SEAL_SCRIPT="`dirname $TPM_SCRIPT_PATH`/tpm2_pre_seal.sh"
                if [ -f "$PRE_SEAL_SCRIPT" ]; then
                  echo $(date -u) "Configuring TPM2 boot environment for Ubuntu 24.04..."
                  $PRE_SEAL_SCRIPT ${EMMC_PATH} ${ENCRYPT_NAME} ${EMMC_ROOT_PATH} ${Disk_PASS} "`dirname $TPM_SCRIPT_PATH`"
                  if [ $? == 0 ]; then
                    echo $(date -u) "TPM2 pre-seal configuration PASS!"
                  else
                    echo $(date -u) "TPM2 pre-seal configuration FAIL!"
                    exit 1
                  fi
                else
                  echo $(date -u) "Warning: tpm2_pre_seal.sh not found, skipping TPM2 boot configuration"
                fi              
                $TPM_SCRIPT_PATH ${EMMC_PATH} $RANDOM_KEY_PATH $PCR_DAT_PATH $SIGN_PUBLIC_KEY_DER_PATH $Disk_PASS $ENCRYPT_NAME $EMMC_ROOT_PATH
                if [ $? == 0 ] ; then 
                  echo $(date -u) "Seal and luksChangeKey PASS!"
                  
                  echo $(date -u) "Reboot system now..."
                  sleep 2
                  #reboot
                else
                    echo $(date -u) "Seal and luksChangeKey FAIL!"		
                fi 
              else
                echo $(date -u) "Reboot system now..."
                sleep 2
                sync
                #reboot
              fi       
            fi
            exit 1;
      esac
    fi	
  fi
done

echo $(date -u) "Image file ${FILE[0]} does not exist." 
echo $(date -u) "Please check the image file is in the USB disk!"


 

