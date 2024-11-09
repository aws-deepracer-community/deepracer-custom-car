#!/usr/bin/env bash

export DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. >/dev/null 2>&1 && pwd)"

CODENAME="experimental"
ARCHITECTURE=$(dpkg --print-architecture)
BUCKET="aws-deepracer-community-sw"
PREFIX="deepracer-custom-car/"
REGION="eu-west-1"
PROFILE="default"

while getopts "c:m:a:r:" opt; do
    case $opt in
    a)
        ARCHITECTURE=$OPTARG
        ;;
    c)
        CODENAME=$OPTARG
        ;;
    m)
        COMPONENT=$OPTARG
        ;;      
    r)
        PROFILE=$OPTARG
        ;;          
    \?)
        echo "Invalid option -$OPTARG" >&2
        usage
        ;;
    esac
done

AWS_ACCESS_KEY_ID=$(aws configure get aws_access_key_id --profile $PROFILE)
AWS_SECRET_ACCESS_KEY=$(aws configure get aws_secret_access_key --profile $PROFILE)

if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "AWS credentials not found for profile $PROFILE. Exiting."
    exit 1
fi

export AWS_ACCESS_KEY_ID
export AWS_SECRET_ACCESS_KEY

deb-s3 clean --bucket=$BUCKET --prefix=$PREFIX --s3-region=$REGION -m $COMPONENT -c $CODENAME