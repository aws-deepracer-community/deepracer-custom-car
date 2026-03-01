#!/bin/bash

# Load required modules
modprobe libcomposite
modprobe usb_f_rndis
modprobe usb_f_ncm

# Mount configfs if not mounted
if [ ! -d /sys/kernel/config/usb_gadget ]; then
    mount -t configfs none /sys/kernel/config
fi

CONFIGS="/sys/kernel/config"
GADGET="$CONFIGS/usb_gadget"
GADGETS_DIR="multi"
USB_VID="0x1949"
USB_PID="0x1101"
SERIAL="0123456789"
PRODUCT="Deeplens"
MSFT_STR="MSFT100"
MANUF="Amazon"
COMPATIBLE_ID="RNDIS"
RNDIS_CONF="Config 1: RNDIS network"
USE_RNDIS=true
USE_ECM=true
USB0_ADDR="10.0.0.1"
USB0_RANGE="10.0.0.0"
USB1_ADDR="10.0.1.1"
USB1_RANGE="10.0.1.0"

# Auto-detect WiFi interface
WIFI_IF=$(ip -o link show | awk -F': ' '$2 ~ /^(wlan|wls|mlan)/ {print $2; exit}')
if [ -z "$WIFI_IF" ]; then
    WIFI_IF="wlan0"  # Fallback
fi

# Auto-detect UDC
UDC_NAME=$(ls /sys/class/udc/ 2>/dev/null | head -n1)
if [ -z "$UDC_NAME" ]; then
    echo "Error: No UDC found"
    exit 1
fi


function uninit_usb()
{
    echo "Stop DHCP server"
    systemctl stop isc-dhcp-server
    echo "OK"

    echo "Delete iptables"
    ip addr del $USB0_ADDR/30 dev usb0 2>/dev/null || true
    ip addr del $USB1_ADDR/30 dev usb1 2>/dev/null || true
    iptables -t nat -D POSTROUTING -s $USB0_RANGE/30 -o $WIFI_IF -j MASQUERADE 2>/dev/null || true
    iptables -t nat -D POSTROUTING -s $USB1_RANGE/30 -o $WIFI_IF -j MASQUERADE 2>/dev/null || true
    echo "OK"

    cd $GADGET/$GADGETS_DIR
    if [ $? -ne 0 ]; then
        echo "Error: no configfs gadget found"
        exit 1;
    fi
    echo "Disable composite USB gadgets"
    echo > UDC
    echo "OK"
	
    echo "Removing rndis usb0 OK"
    if $USE_RNDIS; then
    	rm -f configs/c.1/rndis.usb0
        rmdir functions/rndis.usb0
    fi
    echo "OK"
    
    echo "Removing ecm usb1"
    if $USE_ECM; then
    	rm -f configs/c.1/ncm.usb1
        rmdir functions/ncm.usb1
    fi
    echo "OK"
    
    echo "Removing gadget directory"
    rmdir strings/0x409
    rm -f os_desc/c.1
    rmdir configs/c.1/strings/0x409
    rmdir configs/c.1

    #rmdir configs/c.2/strings/0x409
    #rmdir configs/c.2
    cd $GADGET

    rmdir -p multi
    cd /
    echo "OK"
}

function init_usb()
{
    cd $GADGET
    mkdir -p $GADGETS_DIR
    cd $GADGETS_DIR

    echo $USB_VID > idVendor # RNDIS /ECM
    echo $USB_PID > idProduct # RNDIS /ECM
    echo 0x0100 > bcdDevice
    echo 0x0200 > bcdUSB
    echo 0xEF > bDeviceClass
    echo 0x02 > bDeviceSubClass
    echo 0x01 > bDeviceProtocol

    mkdir -p strings/0x409 # English language strings
# set serial
    echo $SERIAL > strings/0x409/serialnumber
# set manufacturer
    echo $MANUF > strings/0x409/manufacturer
# set product
    echo $PRODUCT > strings/0x409/product

# create RNDIS function
# =======================================================
    echo "Creating RNDIS"
    if $USE_RNDIS; then
	mkdir -p configs/c.1/strings/0x409
	echo $RNDIS_CONF > configs/c.1/strings/0x409/configuration
	echo 250 > configs/c.1/MaxPower
	echo 0x80 > configs/c.1/bmAttributes
        mkdir -p functions/rndis.usb0
	# set up mac address of remote device
        echo "12:34:56:78:90:10" > functions/rndis.usb0/host_addr
	# set up local mac address
        echo "12:34:56:78:90:11" > functions/rndis.usb0/dev_addr

        mkdir -p os_desc
        echo "1" > os_desc/use
        echo 0xbc > os_desc/b_vendor_code
        echo $MSFT_STR > os_desc/qw_sign

        mkdir -p functions/rndis.usb0/os_desc/interface.rndis
        echo $COMPATIBLE_ID > functions/rndis.usb0/os_desc/interface.rndis/compatible_id
        echo "5162001" > functions/rndis.usb0/os_desc/interface.rndis/sub_compatible_id

        ln -s functions/rndis.usb0 configs/c.1/ # RNDIS on config 1 # RNDIS has to be the first 
        ln -s configs/c.1/ os_desc # add config 1 to OS descriptors

    fi
    echo "OK"


# create CDC ECM function
# =======================================================
    echo "Creating ECM"
    if $USE_ECM; then
        mkdir -p functions/ncm.usb1
	# set up mac address of remote device
        echo "12:34:56:78:90:20" > functions/ncm.usb1/host_addr
	# set up local mac address
        echo "12:34:56:78:90:21" > functions/ncm.usb1/dev_addr

        ln -s functions/ncm.usb1 configs/c.1/ # ECM on config  1
    fi
    echo "OK"

    sleep 0.2
    echo "$UDC_NAME" > UDC

    ip link set usb0 up
    ip addr add $USB0_ADDR/30 dev usb0
    iptables -t nat -A POSTROUTING -s $USB0_RANGE/30 -o $WIFI_IF -j MASQUERADE

    ip link set usb1 up
    ip addr add $USB1_ADDR/30 dev usb1
    iptables -t nat -A POSTROUTING -s $USB1_RANGE/30 -o $WIFI_IF -j MASQUERADE
    echo 1 > /proc/sys/net/ipv4/ip_forward
    # Keep all ufw setting same as before, just add on the USB range
    #ufw default allow FORWARD
	#ufw allow http
	#ufw allow 53
	ufw allow from $USB0_RANGE/30 to any port http
	ufw allow from $USB1_RANGE/30 to any port http
	ufw allow from $USB0_RANGE/30 to any port 53
	ufw allow from $USB1_RANGE/30 to any port 53
        #ufw allow 22 # ssh
        #ufw allow "Nginx Full"  # Nginx
    systemctl restart dnsmasq
    systemctl restart isc-dhcp-server

}

function status_usb()
{
    # Check UDC state
    UDC_STATE=$(cat /sys/class/udc/*/state 2>/dev/null | head -n1)
    if [ "$UDC_STATE" = "configured" ] || [ "$UDC_STATE" = "connected" ]; then
        echo "Connect"
    else 
        echo "No Connect"
    fi
}


case "$1" in 
    start)
	init_usb
    ;;
    stop)
	uninit_usb
    ;;
	status)
	status_usb
	;;

esac
