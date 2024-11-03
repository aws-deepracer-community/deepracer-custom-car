# DeepRacer Custom

## Description

DeepRacer Custom provides a set of features that will improve your DeepRacer car.

The repository is a merge of [deepracer-scripts](https://github.com/davidfsmith/deepracer-scripts) that contained improvements for the original car and [deepracer-pi](https://github.com/larsll/deepracer-pi) that ported DeepRacer to a Raspberry Pi4.

This repository contains a few different things:
 - Build and install scripts for a custom ROS2 software stack for DeepRacer.
 - Drawings and build instructions for building a DeepRacer compatible car based on a WLToys A979 and a Raspberry Pi4.
 - Utilities, e.g. to create a USB stick to flash the original DeepRacer.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Building a car with Raspberry Pi](#building-a-car-with-raspberry-pi)
- [Building the Software](#building-the-software)

## Features

The main features of the custom software stack is
- Performance improvement through using compressed image transport for main processing pipeline
- Inference using OpenVINO with Intel GPU (original DeepRacer), OpenVino with Myriad Neural Compute Stick (NCS), or Tensorflow Lite
- Model Optimizer caching, speeding up switching of models
- Capture in-car camera and inference results to a ROS Bag for logfile analysis
- UI tweaks and fixes
- Reduced log output

Additionally there are OS level tweaks for the original DeepRacer:
 - Uninstall unused packages and stop unnecessary services
 - Disable wifi power-save to avoid disconnects

## Installation

[Provide instructions on how to install and set up your project]

## Usage

Once installed the software will look very much like the original DeepRacer software.

The custom stack exposes the following arguments which can be changed through changing `/opt/aws/deepracer/start_ros.sh`.

| Argument | Default | Description | 
| -------- | ------- | ----------- |
| `camera_fps` | `30` | Number of camera frames per second, directly impacting how frequently the car takes new actions. |
| `camera_resize` | `True` | Does the camera resize from 640x480 to 160x120 at source. | 
| `inference_engine` | `TFLITE` | Inference engine to use (TFLITE or OV). |
| `inference_device` | `CPU` | Inference device to use, applicable to OV only (CPU, GPU or MYRIAD). |
| `logging_mode` | `usbonly` | Enable the logging of results to ROS Bag on USB stick. |
| `battery_dummy` | `False` | Use static dummy for battery measurements. |

Example custom `/opt/aws/deepracer/start_ros.sh`:
    
    source /opt/ros/foxy/setup.bash
    source /opt/aws/deepracer/lib.custom/setup.bash
    source /opt/intel/openvino_2021/bin/setupvars.sh
    ros2 launch deepracer_launcher deepracer_launcher.py camera_resize:=False camera_fps:=15 logging_mode:=Always

## Building a car with Raspberry Pi

To create a DeepRacer compatible car with WLToys A979 and a Raspberry Pi read the [building instructions](docs/raspberry_pi.md).

## Building the Software

There are many ways to build the software packages. The easiest is to use the VS.Code Dev Container configurations that are included in the repository. 

- Ubuntu 20.04 (AMD64) + ROS2 Foxy for building packages for original DeepRacer
- Ubuntu 22.04 (AMD64) + ROS2 Humble
- Ubuntu 22.04 (ARM64) + ROS2 Humble for Raspberry Pi4.

Opening VS.Code will prompt you if you want to open the DevContainer. It will require Docker to be installed on your computer, Windows or Linux should be supported. To keep the bash history between sessions run `docker volume create deepracer-ros-bashhistory` before starting the container.

Running the ARM64 container on a normal x86 computer will require enabling cross-compilation in Docker:

        docker run --privileged --rm tonistiigi/binfmt --install all

The cross-compiled container uses quemu and is quite a bit slower than the native containers.

Once DevContainer is runnning (first build might take a while) then packages can be installed with:

        ./build_scripts/build-core.sh

DEB packages can be created with:

        ./build_scripts/build-packages.sh

The packages will be created in the `dist/` folder.

## Dependencies

During installation a set of external packages are downloaded in the `src/` directory. These are primarily the official AWS DeepRacer packages as well as their dependencies, which will be patched as part of the build process.

| Package | Description |
|---------|-------------|
| [aws-deepracer-camera-pkg](https://github.com/aws-deepracer/aws-deepracer-camera-pkg.git) | Camera package for AWS DeepRacer |
| [aws-deepracer-ctrl-pkg](https://github.com/aws-deepracer/aws-deepracer-ctrl-pkg.git) | Control package for AWS DeepRacer |
| [aws-deepracer-device-info-pkg](https://github.com/aws-deepracer/aws-deepracer-device-info-pkg.git) | Device info package for AWS DeepRacer |
| [aws-deepracer-i2c-pkg](https://github.com/aws-deepracer/aws-deepracer-i2c-pkg.git) | I2C package for AWS DeepRacer |
| [aws-deepracer-inference-pkg](https://github.com/aws-deepracer/aws-deepracer-inference-pkg.git) | Inference package for AWS DeepRacer |
| [aws-deepracer-interfaces-pkg](https://github.com/aws-deepracer/aws-deepracer-interfaces-pkg.git) | Interfaces package for AWS DeepRacer |
| [aws-deepracer-model-optimizer-pkg](https://github.com/aws-deepracer/aws-deepracer-model-optimizer-pkg.git) | Model optimizer package for AWS DeepRacer |
| [aws-deepracer-navigation-pkg](https://github.com/aws-deepracer/aws-deepracer-navigation-pkg.git) | Navigation package for AWS DeepRacer |
| [aws-deepracer-sensor-fusion-pkg](https://github.com/aws-deepracer/aws-deepracer-sensor-fusion-pkg.git) | Sensor fusion package for AWS DeepRacer |
| [aws-deepracer-servo-pkg](https://github.com/aws-deepracer/aws-deepracer-servo-pkg.git) | Servo package for AWS DeepRacer |
| [aws-deepracer-status-led-pkg](https://github.com/aws-deepracer/aws-deepracer-status-led-pkg.git) | Status LED package for AWS DeepRacer |
| [aws-deepracer-systems-pkg](https://github.com/aws-deepracer/aws-deepracer-systems-pkg.git) | Systems package for AWS DeepRacer |
| [aws-deepracer-usb-monitor-pkg](https://github.com/aws-deepracer/aws-deepracer-usb-monitor-pkg.git) | USB monitor package for AWS DeepRacer |
| [aws-deepracer-webserver-pkg](https://github.com/aws-deepracer/aws-deepracer-webserver-pkg.git) | Webserver package for AWS DeepRacer |
| [async_web_server_cpp](https://github.com/GT-RAIL/async_web_server_cpp.git) | Async web server for C++ |
| [web_video_server](https://github.com/RobotWebTools/web_video_server.git) | Web video server |
| [rplidar_ros](https://github.com/Slamtec/rplidar_ros.git) | RPLIDAR ROS package |
| [aws-deepracer-launcher](https://github.com/aws-deepracer/aws-deepracer-launcher.git) | Launcher package for AWS DeepRacer |
| [larsll-deepracer-logging](https://github.com/larsll/larsll-deepracer-logging.git) | Logging package for AWS DeepRacer |

