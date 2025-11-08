#!/usr/bin/env bash

# This script builds TensorFlow 2.17.1 from source with optimizations suitable for Intel Atom processors
# that lack AVX/AVX2 instruction support (e.g., Intel Atom E3930).
#
# Building TensorFlow from source is resource-intensive.
# Build time on powerful machine: 1-3 hours
# Build time on Intel Atom E3930: 8-12+ hours
#
# Prerequisites:
# - At least 8GB RAM (16GB+ recommended for parallel builds)
# - At least 50GB free disk space
# - Python 3.10 or later
# - Bazel (will be installed if not present)

set -e

DEBIAN_FRONTEND=noninteractive

# Get the script directory
export DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. >/dev/null 2>&1 && pwd)"

# Configuration
TF_VERSION="2.17.1"
export TF_PYTHON_VERSION="3.12"
BUILD_DIR="${DIR}/deps/tensorflow"
INSTALL_PREFIX="${DIR}/dist"

echo "========================================"
echo "Building TensorFlow ${TF_VERSION} for Intel Atom"
echo "Build directory: ${BUILD_DIR}"
echo "Install prefix: ${INSTALL_PREFIX}"
echo "========================================"

# Install build dependencies
echo "Installing build dependencies..."
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libhdf5-dev \
    libssl-dev \
    openjdk-11-jdk \
    patchelf \
    python3-dev \
    python3-pip \
    python3-venv \
    unzip \
    wget \
    zip

# Install Bazelisk (manages Bazel versions)
echo "Installing Bazelisk..."
BAZEL_VERSION="1.21.0"
if [ ! -f /usr/local/bin/bazelisk ]; then
    sudo wget -O /usr/local/bin/bazelisk \
        "https://github.com/bazelbuild/bazelisk/releases/download/v${BAZEL_VERSION}/bazelisk-linux-$(dpkg --print-architecture)"
    sudo chmod +x /usr/local/bin/bazelisk
    sudo ln -sf /usr/local/bin/bazelisk /usr/local/bin/bazel
fi

# Create build directory
echo "Setting up build directory..."
mkdir -p ${BUILD_DIR}
cd ${BUILD_DIR}

# Clone TensorFlow repository if not already present
if [ ! -d "tensorflow" ]; then
    echo "Cloning TensorFlow repository..."
    git clone https://github.com/tensorflow/tensorflow.git
fi

cd tensorflow
git checkout "v${TF_VERSION}"

# Create Python virtual environment for build
echo "Creating Python virtual environment..."
python3 -m venv ${BUILD_DIR}/tf-build-env
source ${BUILD_DIR}/tf-build-env/bin/activate

# Install Python build dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip setuptools wheel
pip install numpy==1.26.4 packaging

# Configure build for Intel Atom (no AVX/AVX2)
echo "Configuring TensorFlow build..."
export PYTHON_BIN_PATH=$(which python3)
export PYTHON_LIB_PATH=$(python3 -c 'import site; print(site.getsitepackages()[0])')
export TF_NEED_CUDA=0
export TF_NEED_ROCM=0
export TF_DOWNLOAD_CLANG=0
export TF_SET_ANDROID_WORKSPACE=0
export TF_NEED_MPI=0
export CC_OPT_FLAGS="-march=silvermont -mtune=silvermont -msse4.1 -msse4.2 -mno-avx -mno-avx2"
export TF_CONFIGURE_IOS=0
export USE_DEFAULT_PYTHON_LIB_PATH=1
export TF_NEED_CLANG=0
export GCC_HOST_COMPILER_PATH=$(which gcc)
export CC=$(which gcc)
export CXX=$(which g++)

# Run configure
echo "Running TensorFlow configuration..."
yes "" | ./configure

# Build TensorFlow wheel package
echo "Building TensorFlow (this will take 1-3 hours on a powerful machine)..."
echo "Build started at: $(date)"

# Build with limited parallelism to avoid OOM
bazel build \
    --jobs=6 \
    --local_ram_resources=HOST_RAM*.5 \
    --config=opt \
    --copt=-march=silvermont \
    --copt=-mtune=silvermont \
    --copt=-msse4.1 \
    --copt=-msse4.2 \
    --copt=-mno-avx \
    --copt=-mno-avx2 \
    --copt=-mno-fma \
    --verbose_failures \
    //tensorflow/tools/pip_package:wheel

echo "Build completed at: $(date)"

# Copy wheel package
echo "Copying wheel package..."
mkdir -p ${BUILD_DIR}/tensorflow_pkg
cp bazel-bin/tensorflow/tools/pip_package/wheel_house/tensorflow-${TF_VERSION}*.whl ${BUILD_DIR}/tensorflow_pkg/ || \
    cp bazel-bin/tensorflow/tools/pip_package/*.whl ${BUILD_DIR}/tensorflow_pkg/

# Install the wheel
echo "Installing TensorFlow wheel..."
pip install ${BUILD_DIR}/tensorflow_pkg/tensorflow-${TF_VERSION}*.whl

# Copy wheel to install prefix for future use
echo "Copying wheel to ${INSTALL_PREFIX}..."
mkdir -p ${INSTALL_PREFIX}
cp ${BUILD_DIR}/tensorflow_pkg/tensorflow-${TF_VERSION}*.whl ${INSTALL_PREFIX}/

# Test TensorFlow installation from outside source directory (within venv)
echo "Testing TensorFlow installation..."
cd ${BUILD_DIR}
python3 -c "import tensorflow as tf; print('TensorFlow version:', tf.__version__)"

echo "========================================"
echo "TensorFlow ${TF_VERSION} build complete!"
echo "Wheel package location: ${INSTALL_PREFIX}/tensorflow-${TF_VERSION}*.whl"
echo ""
echo "The wheel is built for Intel Atom (Silvermont) without AVX/AVX2 instructions."
echo ""
echo "To install in other environments:"
echo "  pip install ${INSTALL_PREFIX}/tensorflow-${TF_VERSION}*.whl"
echo ""
echo "To install with system pip on target device:"
echo "  pip3 install --break-system-packages ${INSTALL_PREFIX}/tensorflow-${TF_VERSION}*.whl"
echo "========================================"

deactivate
