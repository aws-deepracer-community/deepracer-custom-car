# Copyright (C) 2019-2022 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
FROM ros:jazzy-ros-base

ARG USERNAME=user-name-goes-here
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    cython3-legacy \
    curl \
    ffmpeg \
    gpiod \
    jq \
    libboost-all-dev \
    libglib2.0-dev \
    libgpiod-dev \
    libgnutls28-dev \
    libjsoncpp-dev \
    libpugixml-dev \
    libtiff-dev \
    libyaml-dev \
    meson \
    nano \
    openssl \
    pipx \
    pkg-config \
    python3-apt \
    python3-autopep8 \
    python3-colcon-common-extensions \
    python3-jinja2 \
    python3-libgpiod \
    python3-opencv \
    python3-pip \
    python3-ply \
    python3-smbus2 \
    python3-venv \
    python3-websocket \
    python3-yaml \
    ros-dev-tools \
    ros-jazzy-camera-ros \
    ros-jazzy-compressed-image-transport \
    ros-jazzy-cv-bridge \
    ros-jazzy-image-transport \
    ros-jazzy-pybind11-vendor \
    ruby \
    sudo \
    unzip \
    v4l-utils \
    wget

RUN gem install deb-s3

RUN pip install flask flask-cors flask-wtf --break-system-packages

# Install AWS CLI v2 (support both ARM and x86 architectures)
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then \
        AWS_CLI_URL="https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip"; \
    elif [ "$ARCH" = "aarch64" ]; then \
        AWS_CLI_URL="https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip"; \
    else \
        echo "Unsupported architecture: $ARCH" && exit 1; \
    fi && \
    curl "$AWS_CLI_URL" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    rm -rf awscliv2.zip aws

# Create the user
RUN userdel ubuntu && groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME \
    && usermod -a -G audio $USERNAME \
    && usermod -a -G video $USERNAME \
    && groupadd --gid 136 i2c \
    && usermod -a -G i2c $USERNAME \
    && usermod -a -G dialout $USERNAME


# Persist history
RUN SNIPPET="export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" \
    && mkdir /commandhistory \
    && touch /commandhistory/.bash_history \
    && chown -R $USERNAME /commandhistory \
    && echo $SNIPPET >> "/home/$USERNAME/.bashrc"

ENTRYPOINT ["/bin/bash", "source /opt/ros/jazzy/setup.bash"]