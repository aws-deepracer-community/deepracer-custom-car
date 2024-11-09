#!/usr/bin/env bash

export DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. >/dev/null 2>&1 && pwd)"

PACKAGES="aws-deepracer-util aws-deepracer-device-console aws-deepracer-core aws-deepracer-sample-models"
CODENAME="experimental"
ARCHITECTURE=$(dpkg --print-architecture)
KEY="CFB167A8F18DE6A634A6A2E4A63BC335D48DF8C6"
BUCKET="aws-deepracer-community-sw"
PREFIX="deepracer-custom-car/"
REGION="eu-west-1"
PROFILE="default"

while getopts "p:c:m:a:r:" opt; do
    case $opt in
    a)
        ARCHITECTURE=$OPTARG
        ;;
    p)
        PACKAGES=$OPTARG
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

if [ -z "$PACKAGES" ]; then
    echo "No packages provided. Exiting."
    exit 1
fi

if [ -z "$COMPONENT" ]; then
    echo "No component provided. Exiting."
    exit 1
fi

for PKG in $PACKAGES; do
    VERSION=$(jq -r ".[\"$PKG\"]" $DIR/build_scripts/versions.json)
    FILE_NAME=$(echo ${PKG}_${VERSION}_${ARCHITECTURE}.deb | sed -e 's/\+/\-/')   
    if [ ! -f "dist/$FILE_NAME" ]; then
        if [ -f "dist/$(echo ${PKG}_${VERSION}_all.deb | sed -e 's/\+/\-/')" ]; then
            FILE_NAME=$(echo ${PKG}_${VERSION}_all.deb | sed -e 's/\+/\-/')
        else
            echo Can\'t find file $FILE_NAME
            exit 1
        fi
    fi

    echo Uploading $FILE_NAME to $CODENAME/$COMPONENT
    deb-s3 upload dist/$FILE_NAME -c $CODENAME -v public -p -b $BUCKET --prefix $PREFIX -m $COMPONENT --s3-region=$REGION --sign=$KEY

done