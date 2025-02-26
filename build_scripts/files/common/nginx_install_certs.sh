#!/usr/bin/env bash

ROOT_DIR=$(cd $(dirname ${BASH_SOURCE[0]}) && pwd)

#####################################################################
#               For secure signing of NGINX server
#####################################################################

CERT_FILE="/etc/ssl/certs/nginx-selfsigned.crt"
KEY_FILE="/etc/ssl/private/nginx-selfsigned.key"
SUBJECT="/C=US/ST=Washington/L=Seattle/O=Amazon.com Inc./OU=Amazon Web Services/CN=deepracer.io"

# Function to check if the certificate is valid for at least 365 days
is_cert_valid_for_365_days() {
    local cert_file=$1
    local end_date=$(openssl x509 -enddate -noout -in "$cert_file" | cut -d= -f2)
    local end_date_epoch=$(date -d "$end_date" +%s)
    local current_date_epoch=$(date +%s)
    local diff_days=$(( (end_date_epoch - current_date_epoch) / 86400 ))
    [ $diff_days -ge 365 ]
}

# Check if the certificate and key exist
if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
    # Check if the certificate and key match
    if openssl x509 -noout -modulus -in "$CERT_FILE" | openssl md5 == openssl rsa -noout -modulus -in "$KEY_FILE" | openssl md5; then
        # Check if the certificate is issued by the required subject
        if openssl x509 -in "$CERT_FILE" -noout -subject | grep -q "$SUBJECT"; then
            # Check if the certificate is valid for at least 365 days
            if is_cert_valid_for_365_days "$CERT_FILE"; then
                echo "Existing certificate is valid and matches the required criteria. Skipping certificate creation."
                exit 0
            fi
        fi
    fi
fi

# Creating the Nginx certificates and placing to appropriate directory
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 -keyout "$KEY_FILE" -out "$CERT_FILE" -subj "$SUBJECT"

# Check if the default password file exists
if [ ! -f /opt/aws/deepracer/password.txt ]; then
    # Creating the webserver default username and password (deepracer)
    python3 $ROOT_DIR/reset_default_password.py
fi
