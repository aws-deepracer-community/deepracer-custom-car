#!/usr/bin/env bash

# This script builds and installs libcamera for ROS2 on ARM64 architecture.
# It performs the following steps:
# 1. Sets the DEBIAN_FRONTEND to noninteractive to avoid prompts during package installation.
# 2. Determines the directory of the script and sets it to the DIR variable.
# 3. Detects the installed ROS distribution (foxy, humble, or jazzy).
# 4. Sources the appropriate ROS setup script.
# 5. Reads the libcamera version from versions.json file.
# 6. Clones the libcamera repository from Raspberry Pi GitHub with the specified version tag.
# 7. Configures the build with Meson, enabling RPI/PISP pipelines and V4L2 support.
# 8. Compiles libcamera using Ninja build system.
# 9. Installs the compiled libcamera binaries to the build directory.
# 10. Creates a Debian package control file with version information.
# 11. Builds a .deb package for the compiled libcamera.
# 12. Renames the package using dpkg-name for proper versioning.

set -e

export DEBIAN_FRONTEND=noninteractive
export DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. >/dev/null 2>&1 && pwd)"

# Detect ROS version
if [ -f /opt/ros/foxy/setup.bash ]; then
    ROS_DISTRO="foxy"
elif [ -f /opt/ros/humble/setup.bash ]; then
    ROS_DISTRO="humble"
elif [ -f /opt/ros/jazzy/setup.bash ]; then
    ROS_DISTRO="jazzy"
else
    echo "Unsupported ROS version"
    exit 1
fi
echo "Detected ROS version: $ROS_DISTRO"
source /opt/ros/$ROS_DISTRO/setup.bash

VERSION_BASE=$(jq -r ".[\"ros-$ROS_DISTRO-libcamera\"]" $DIR/build_scripts/versions.json)
VERSION=1:${VERSION_BASE}-$(lsb_release -cs)

cd $DIR/deps/
if [ ! -d "$DIR/deps/libcamera" ]; then
    git clone --branch v0.5.0+rpt20250429 https://github.com/raspberrypi/libcamera.git
else
    cd $DIR/deps/libcamera
    git fetch origin
    git checkout v0.5.0+rpt20250429
fi
cd $DIR/deps/libcamera

meson setup build --buildtype=release -Dpipelines=uvcvideo,rpi/vc4,rpi/pisp -Dipas=rpi/vc4,rpi/pisp -Dv4l2=enabled -Dgstreamer=disabled -Dtest=false -Dlc-compliance=disabled -Dcam=enabled -Dqcam=disabled -Ddocumentation=disabled -Dpycamera=enabled --prefix=/opt/ros/$ROS_DISTRO
export DESTDIR=${DIR}/deps/libcamera-build
rm -rf ${DESTDIR}
ninja -C build install
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
mkdir -p ${DESTDIR}/opt/ros/$ROS_DISTRO/lib/python${PYTHON_VERSION}/site-packages
mv ${DESTDIR}/opt/ros/$ROS_DISTRO/lib/aarch64-linux-gnu/python${PYTHON_VERSION}/site-packages/libcamera ${DESTDIR}/opt/ros/$ROS_DISTRO/lib/python${PYTHON_VERSION}/site-packages/libcamera

mkdir -p ${DIR}/deps/libcamera-build/DEBIAN
cp ${DIR}/build_scripts/files/common/ros-$ROS_DISTRO-libcamera-control ${DIR}/deps/libcamera-build/DEBIAN/control
sed -i "s/Version: .*/Version: $VERSION/" ${DIR}/deps/libcamera-build/DEBIAN/control
dpkg-deb --root-owner-group --build ${DIR}/deps/libcamera-build ${DIR}/deps/ros-$ROS_DISTRO-libcamera.deb
dpkg-name -o ${DIR}/deps/ros-$ROS_DISTRO-libcamera.deb

FILE=$(compgen -G ${DIR}/deps/ros-$ROS_DISTRO-libcamera_*.deb)
NEW_FILENAME=$(basename $FILE | sed -e 's/\+/\-/')
mv $FILE ${DIR}/dist/${NEW_FILENAME}
echo "libcamera package built and renamed to ${NEW_FILENAME} in ${DIR}/dist/"