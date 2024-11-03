# Copyright (C) 2019-2022 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
FROM ros:humble-ros-base

ARG USERNAME=user-name-goes-here
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    libboost-all-dev \
    libpugixml-dev \
    python3-pip \
    python3-websocket \
    python3-colcon-common-extensions \
    python3-rosinstall \
    python3-venv \
    ros-humble-cv-bridge \
    ros-humble-rqt-console \
    ros-humble-rqt-graph \
    ros-humble-image-transport \
    ros-humble-compressed-image-transport \
    ros-humble-pybind11-vendor \
    libjsoncpp-dev \
    v4l-utils \
    ffmpeg \
    sudo \
    curl \
    wget \
    jq \
    cython3

RUN cd / && curl -O https://larsll-build-artifact-share.s3.eu-north-1.amazonaws.com/openvino/openvino_2022.3.1_amd64.tgz && \
    tar -xvzf openvino_2022.3.1_amd64.tgz && \
    ln -sf /opt/intel/openvino_2022.3.1 /opt/intel/openvino_2022 && \
    ln -sf /opt/intel/openvino_2022.3.1 /opt/intel/openvino && \
    rm /openvino_2022.3.1_amd64.tgz

RUN pip3 install -U smbus2 pillow transforms3d autopep8 opencv-python pyserial "setuptools==58.2.0" "Cython<3" $(find /opt/intel/openvino_2022.3.1/tools/ -name *.whl)

# Create the user
RUN groupadd --gid $USER_GID $USERNAME \
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

ENTRYPOINT ["/bin/bash", "source /opt/ros/humble/setup.bash"]