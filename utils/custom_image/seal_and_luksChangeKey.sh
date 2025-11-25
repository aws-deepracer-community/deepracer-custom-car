#!/bin/bash

VER="V0.4"

HANDLE_PRIMARY="0x81010001"
HANDLE_SEAL_DATA="0x81010011"
HANDLE_NV_KEY_SIGN="0x1500018"
PCR_LIST="sha1:0,1,2"
#RANDOM_KEY="random.key"
RANDOM_NUM="/tmp/randomnum"
RANDOM_KEY="/tmp/new_random.key"
EMMC_PATH="$1"
#RANDOM_KEY="$2"
PCR_DAT="$2"
SIGN_PUBLIC_KEY_DER="$3"
Disk_PASS="$4"
ENCRYPT_NAME="$5"
EMMC_ROOT_PATH="$6"

TMP_FOLDER="/tmp/"
unseal_key="/tmp/unseal_key.dat"
TCTI_INTERFACE=" -T /usr/local/lib/libtss2-tcti-device.so.0"

function flushcontext(){
      echo flushcontext
      sudo tpm2_flushcontext -t $TCTI_INTERFACE
      sudo tpm2_flushcontext -l $TCTI_INTERFACE
      sudo tpm2_flushcontext -s $TCTI_INTERFACE
}

#set log file
#LOG_FILE="key_result.log"
#exec &> >(tee -a ${LOG_FILE} ) 

if [[ -z $EMMC_PATH ]]; then
    echo $(date -u) "Error ! Please input eMMC path"
    echo $(date -u) "seal_and_luksChangeKey.sh <EMMC_PATH> <RANDOM_KEY> <PCR_DAT> <SIGN_PUBLIC_KEY> <passphrase> <ENCRYPT_NAME>"
    echo $(date -u) "Example : seal_and_luksChangeKey.sh /dev/mmcblk1 pega.key pcr.dat sign.public.der 'pega#1234' 'mmcblk1p3_crypt'"
    exit 1			
fi

#if [[ -z $RANDOM_KEY ]]; then
#    echo $(date -u) "Error ! Please input random key"
#    echo $(date -u) "reseal.sh <EMMC_PATH> <RANDOM_KEY> <PCR_DAT> <SIGN_PUBLIC_KEY> <passphrase>  <ENCRYPT_NAME>"
#    echo $(date -u) "Example : reseal.sh /dev/mmcblk1 pega.key pcr.dat sign.public.der 'pega#1234' 'mmcblk1p3_crypt'"
#    exit 1			
#fi

if [[ -z $Disk_PASS ]]; then
    echo $(date -u) "Error ! Please default luks encrypt passphrase"
    echo $(date -u) "seal_and_luksChangeKey.sh <EMMC_PATH> <RANDOM_KEY> <PCR_DAT> <SIGN_PUBLIC_KEY> <passphrase>  <ENCRYPT_NAME>"
    echo $(date -u) "Example : seal_and_luksChangeKey.sh /dev/mmcblk1 pega.key pcr.dat sign.public.der 'pega#1234' 'mmcblk1p3_crypt'"
    exit 1			
fi

if  [ ! -f "$PCR_DAT" ] || [[ -z "$PCR_DAT" ]]; then
    echo $(date -u) "Error ! Could not open input file $PCR_DAT"
    exit 1
fi

if  [ ! -f "$SIGN_PUBLIC_KEY_DER" ] || [[ -z "$SIGN_PUBLIC_KEY_DER" ]]; then
    echo $(date -u) "Error ! Could not open input file $SIGN_PUBLIC_KEY_DER"
    exit 1
fi

echo $(date -u) "TPM reseal version : $VER"
echo $(date -u) "eMMc Path : $EMMC_PATH"
echo $(date -u) "Encrypt Root Partition Path : $EMMC_ROOT_PATH"
#echo $(date -u) "Random key : $RANDOM_KEY"
echo $(date -u) "Default luks Passphrase : $Disk_PASS"


echo $(date -u) "************Generate new key**************"
sudo tpm2_getrandom -o $RANDOM_NUM 32 $TCTI_INTERFACE
cat $RANDOM_NUM | sha256sum | awk '{print $1}' | tr -d "\n" > $RANDOM_KEY

#Check Random key 
echo $(date -u) "************Check Random key Start**************"
#step 0
sudo tpm2_pcrlist -L $PCR_LIST -o ${TMP_FOLDER}/pcr.dat $TCTI_INTERFACE

#step 1
sudo tpm2_clear $TCTI_INTERFACE

#step 4
echo $(date -u) "tpm2_createpolicy"
flushcontext
sudo tpm2_createpolicy -P -L $PCR_LIST -F ${TMP_FOLDER}/pcr.dat -f ${TMP_FOLDER}policy.dat $TCTI_INTERFACE

flushcontext
sudo tpm2_createprimary -a e -g sha256 -G ecc -o ${TMP_FOLDER}primary.ctx $TCTI_INTERFACE
sudo tpm2_evictcontrol -a o -c ${TMP_FOLDER}primary.ctx -p $HANDLE_PRIMARY $TCTI_INTERFACE

flushcontext
sudo tpm2_create -g sha256 -G keyedhash -u ${TMP_FOLDER}key.pub -r ${TMP_FOLDER}key.pri -C $HANDLE_PRIMARY -L ${TMP_FOLDER}policy.dat -A 0x492 -I $RANDOM_KEY $TCTI_INTERFACE
sudo tpm2_load -C $HANDLE_PRIMARY -u ${TMP_FOLDER}key.pub -r ${TMP_FOLDER}key.pri -n ${TMP_FOLDER}key.name -o ${TMP_FOLDER}key.ctx $TCTI_INTERFACE
sudo tpm2_evictcontrol -a o -c ${TMP_FOLDER}key.ctx -p $HANDLE_SEAL_DATA $TCTI_INTERFACE

#sudo tpm2_unseal -c $HANDLE_SEAL_DATA -L $PCR_LIST $TCTI_INTERFACE > $unseal_key
key=`sudo tpm2_unseal -c $HANDLE_SEAL_DATA -L $PCR_LIST $TCTI_INTERFACE`
echo -n "$key" > $unseal_key
#hexdump -C "$unseal_key"
result=`diff -qs $RANDOM_KEY $unseal_key | cut -d' ' -f 6`
echo $result
if [ "$result" == "identical" ] ; then
    echo $(date -u) "Seal and unseal key is identical!"
else
    echo $(date -u) "Seal and unseal key is different!"
    echo $(date -u) "RANDOM_KEY"
    hexdump -C "$RANDOM_KEY"
    echo $(date -u) "unseal_key"
    hexdump -C "$unseal_key"
    #diff -y <(xxd $key) <(xxd $unseal_key)
    #echo "$i.key" >> error_key.log 
    #diff -y <(xxd $key) <(xxd $unseal_key) > "log/issue_$i.log"
    #mv $key "log/issue_$i.key"
    exit
fi
echo $(date -u) "************Check Random key end**************"


#Use default pega key to open encrypt partition
echo -n "${Disk_PASS}" | sudo cryptsetup luksOpen ${EMMC_ROOT_PATH} ${ENCRYPT_NAME} --key-file=-
if [ $? == 0 ] ; then
    echo $(date -u) "Seal key to TPM and change luks Passphrase"

    #step 0
    # sudo tpm2_pcrlist -L $PCR_LIST -o $PCR_DAT $TCTI_INTERFACE
    # sudo tpm2_pcrlist -L sha1:0,1,2,4 -o pcr.dat  -T /usr/local/lib/libtss2-tcti-device.so.0

    #step 1
    sudo tpm2_clear $TCTI_INTERFACE

    #step 2
    PUB_KEY_SIZE=$(wc $SIGN_PUBLIC_KEY_DER | tr -s " " | cut -d " " -f4)
    sudo tpm2_nvdefine -x $HANDLE_NV_KEY_SIGN -a o -s $PUB_KEY_SIZE -t 0x2000A $TCTI_INTERFACE
    sudo tpm2_nvwrite -x $HANDLE_NV_KEY_SIGN -a o $SIGN_PUBLIC_KEY_DER $TCTI_INTERFACE

    #step 3
    #sudo tpm2_getrandom -o $RANDOM_KEY 32 $TCTI_INTERFACE

    #step 4
    echo $(date -u) "tpm2_createpolicy"
    flushcontext
    sudo tpm2_createpolicy -P -L $PCR_LIST -F $PCR_DAT -f ${TMP_FOLDER}policy.dat $TCTI_INTERFACE

    flushcontext
    sudo tpm2_createprimary -a e -g sha256 -G ecc -o ${TMP_FOLDER}primary.ctx $TCTI_INTERFACE
    sudo tpm2_evictcontrol -a o -c ${TMP_FOLDER}primary.ctx -p $HANDLE_PRIMARY $TCTI_INTERFACE

    flushcontext
    sudo tpm2_create -g sha256 -G keyedhash -u ${TMP_FOLDER}key.pub -r ${TMP_FOLDER}key.pri -C $HANDLE_PRIMARY -L ${TMP_FOLDER}policy.dat -A 0x492 -I $RANDOM_KEY $TCTI_INTERFACE
    sudo tpm2_load -C $HANDLE_PRIMARY -u ${TMP_FOLDER}key.pub -r ${TMP_FOLDER}key.pri -n ${TMP_FOLDER}key.name -o ${TMP_FOLDER}key.ctx $TCTI_INTERFACE
    sudo tpm2_evictcontrol -a o -c ${TMP_FOLDER}key.ctx -p $HANDLE_SEAL_DATA $TCTI_INTERFACE

    #Step 5
    echo $(date -u) "Add random key in slot 2"
    #echo -n "${Disk_PASS}" | sudo cryptsetup luksOpen ${EMMC_ROOT_PATH} mmcblk1p3 --key-file=-
    echo -n "${Disk_PASS}" | sudo cryptsetup luksAddKey --key-slot 2 ${EMMC_ROOT_PATH} $RANDOM_KEY --key-file=-

    #Dump LUKS partition information 
    echo -n "${Disk_PASS}" | sudo cryptsetup luksDump ${EMMC_ROOT_PATH} --key-file=-
    sudo cryptsetup luksClose ${ENCRYPT_NAME}

    echo -n "${seal_key}" | sudo cryptsetup luksOpen ${EMMC_ROOT_PATH} ${ENCRYPT_NAME} --key-file=$RANDOM_KEY
    if [ $? == 0 ] ; then
        echo $(date -u) "PASS ! Verify random key in LUKS partition PASS"
        #Remove default luks key in slot 0
        echo $(date -u) "Remove default luks key in slot 0"
        sudo cryptsetup luksKillSlot ${EMMC_ROOT_PATH} 0 --key-file $RANDOM_KEY
        #Dump LUKS partition information 
        echo -n "${Disk_PASS}" | sudo cryptsetup luksDump ${EMMC_ROOT_PATH} --key-file=-
        sudo cryptsetup luksClose ${ENCRYPT_NAME}
        exit 0
    else
        echo $(date -u) "Fail ! Verify random key in LUKS partition fail"
        echo $(date -u) "Please check your random key"
        exit 1
    fi       
fi
exit 1

