# DeepRacer Custom Car

## Description

DeepRacer Custom Car provides an updated software stack that contains a set of features that will improve your DeepRacer car.

This repository contains a few different things:
 - Build and install scripts for a custom ROS2 software stack for DeepRacer, supporting original DeepRacer, Raspberry Pi 4 and Raspberry Pi 5.
 - Drawings and build instructions for building a DeepRacer compatible car based on a WLToys A979 and a Raspberry Pi.
 - Utilities, e.g. to create a USB stick to flash the original DeepRacer with the custom 

The repository is a merge of [deepracer-scripts](https://github.com/davidfsmith/deepracer-scripts) that contained improvements for the original car and [deepracer-pi](https://github.com/larsll/deepracer-pi) that ported DeepRacer to a Raspberry Pi4.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Building a car with Raspberry Pi](#building-a-car-with-raspberry-pi)
- [Building the Software](#building-the-software)

## Features

The main features of the custom software stack is
- Performance improvement through using compressed image transport for the primary perception pipeline
- Modern user-interface from [Deepracer Custom Console](https://github.com/aws-deepracer-community/deepracer-custom-console)
- Inference using OpenVINO with Intel GPU (original DeepRacer), OpenVINO with Myriad Neural Compute Stick (NCS), or TensorFlow Lite across RPi and original hardware
- Ubuntu 24.04 support for Raspberry Pi 5 and the original DeepRacer including an updated installer and flashing flow
- Model Optimizer caching, speeding up switching of models
- Capture in-car camera and inference results to a ROS Bag for logfile analysis (Python or high-performance C++ logging node)
- Car health and latency analysis both in console and the ROS Bag
- Reduced log output from chatty nodes

Additionally there are OS level tweaks for the original DeepRacer and Raspberry Pi4 alike:
 - Original: Uninstall unused packages and stop unnecessary services
 - RPi: Minimal install, required packages only
 - Disable wifi power-save to avoid disconnects
 - Disable suspend
 - CPU governors in performance mode to ensure that CPU is running at max frequency during inference.

In the `utils/` folder there are utilities to create a USB flash stick for the original DeepRacer. See [documentation](docs/utilities.md).

## Installation

Choose the guide that matches your scenario:

| Scenario | Guide |
|---|---|
| Original DeepRacer — flash to Ubuntu 24.04 (fresh install, recommended) | [Flashing to Ubuntu 24.04](docs/flash-2404.md) |
| Original DeepRacer — install community stack on existing Ubuntu 20.04 | [Upgrading on Ubuntu 20.04](docs/upgrade-2004.md) |
| Raspberry Pi 4 or 5 | [Building with Raspberry Pi](docs/raspberry_pi.md) |

All installation scripts require root privileges (`sudo`). Run
`install-prerequisites.sh` first, then `install-deepracer.sh`. Basic
installation uses pre-packaged apt/deb packages and does not require compiling
on the car.

## Usage

Once installed the software will look very much like the original DeepRacer software.

The custom stack exposes the following arguments which can be changed through changing `/opt/aws/deepracer/start_ros.sh`.

| Argument | Default | Description | 
| -------- | ------- | ----------- |
| `camera_fps` | `30` | Number of camera frames per second, directly impacting how frequently the car takes new actions. |
| `camera_resize` | `True` | Does the camera resize from 640x480 to 160x120 at source. | 
| `camera_mode` | `legacy` | Camera integration method (`legacy` or `modern`). |
| `inference_engine` | `TFLITE` | Inference engine to use (`TFLITE` or `OV`). |
| `inference_device` | `CPU` | Inference device to use, applicable to OV only (`CPU`, `GPU` or `MYRIAD`). |
| `logging_mode` | `usbonly` | Enable the logging of results to ROS Bag on USB stick. |
| `logging_provider` | `sqlite3` | Database provider to use for logging. |
| `battery_dummy` | `False` | Use static dummy for battery measurements. |
| `rplidar` | `True` | Enable RPLIDAR node for LiDAR sensor integration. |


### Inference engine 

The different combinations of `inference_engine` and `inference_device` are not all compatible with the RPi, and each option comes with pros and cons. The original car software only supports OpenVINO CPU.

| Feature                   | Original (Ubuntu 20.04, ROS2 Foxy)  | Original (Ubuntu 24.04, ROS2 Jazzy)  | RPi4/RPi5 (Ubuntu 24.04, ROS2 Jazzy)  | Notes                                                                 |
|---------------------------|-------------------------------------|--------------------------------------|---------------------------------------|-----------------------------------------------------------------------|
| Camera                    | Original USB (incl. Stereo)         | Original USB (incl. Stereo)          | RPi Camera Module 2 & 3 + USB         |                                                                       |
| TensorFlow Lite (CPU)     | Yes                                 | Yes                                  | Yes                                   | Default for RPi                                                       |
| OpenVINO (CPU)            | Yes                                 | Yes                                  | No                                    | Default for Original                                                  |
| OpenVINO (GPU)            | Yes                                 | No                                   | No                                    | Reduces CPU load, but model takes longer to load                      |
| OpenVINO (NCS2/Myriad X)  | Yes                                 | No                                   | No                                    | Reduces CPU load, requires NCS2 stick, model takes longer to load     |

The different modes have been tested for equivalency, and it is verified that they provide the same results (identical picture in -> identical action taken). Less than 1 per 1000 frames are differing, mainly due to the model not having a clear action, and several actions are having very similar probabilities.

### Logging

If you insert a USB stick or SD card with a folder called `logs/` then this will be automatically mounted, and when you start the car in autonomous mode a ROS 2 bag is created capturing inference results, camera images, and health metrics. The community logging package now ships in-tree (`src/aws-deepracer-community-logging-pkg`) with two implementations:

- **Python node:** Used on Foxy/Humble deployments
- **C++ node:** Default on Jazzy (e.g., Ubuntu 24.04) with ~80–90% lower CPU and 40–60% lower memory usage

Images are only captured if the autonomous mode is running ("Start Vehicle"). If stopped no images are stored. If the same model is restarted within 15 seconds the new images are appended to the same bag. After 15 seconds the bag is closed, and if restarted a new bag is created. If the selected model changes, the current bag is immediately closed, and a new one created once the car is started.

[larsll-deepracer-logging](https://github.com/larsll/larsll-deepracer-logging.git) still hosts supplementary scripts (e.g., bag-to-video with grad-cam overlays) for offline analysis.

## Building a car with Raspberry Pi

To create a DeepRacer compatible car with WLToys A979 and a Raspberry Pi read the [building instructions](docs/raspberry_pi.md).

## Building the Software

To build the software packages, either for the Raspberry Pi4 or for the original Deepracer [read the instructions](docs/build_sw.md).

