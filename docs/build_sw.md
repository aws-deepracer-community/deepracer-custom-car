# Building the Software Packages

There are many ways to build the software packages. The easiest is to use the VS.Code Dev Container configurations that are included in the repository. 

## VS.Code Development Container Approach

The repository ships ready-to-use Dev Container definitions under `.devcontainer/`:

- **Ubuntu 20.04 (AMD64) + ROS2 Foxy** – builds packages for the original DeepRacer (factory OS)
- **Ubuntu 22.04 (AMD64/ARM64) + ROS2 Humble** – general development, CI validation, and Raspberry Pi builds (x86 hosts run AMD64, Apple/ARM hosts run ARM64)
- **Ubuntu 24.04 (AMD64/ARM64) + ROS2 Jazzy ("Noble")** – builds the new 24.04-based images for Raspberry Pi 5 and the original DeepRacer (same host-architecture matching as above)

Opening VS.Code will prompt you if you want to open the DevContainer. It will require Docker to be installed on your computer, Windows or Linux should be supported. To keep the bash history between sessions run `docker volume create deepracer-ros-bashhistory` before starting the container.

Pick the Dev Container whose ROS/OS version matches the target you need to build. On Apple Silicon and other ARM64 hosts, VS Code will automatically choose the ARM64 image; on x86 it will use the AMD64 variant.

Once DevContainer is runnning (first build might take a while) then packages can be installed with:

        ./build_scripts/build-core.sh

`build-core.sh` accepts a few switches to tailor the build:

| Option | Description |
|--------|-------------|
| `-c` | Reuse the previous `build/`, `install/`, and `log/` trees. Skip fresh dependency import to speed up incremental builds. |
| `-p <DR\|RPI>` | Target platform override. Defaults to `DR` (original car); use `RPI` for Raspberry Pi images so the right overlays and dependencies are pulled. |
| `-s` | “Single package” mode: forces sequential colcon execution and limits `MAKEFLAGS` to two cores to reduce memory pressure on smaller hosts. |

DEB packages can be created with:

        ./build_scripts/build-packages.sh

`build-packages.sh` focuses on Debian packages and currently exposes one main flag:

| Option | Description |
|--------|-------------|
| `-p "pkg1 pkg2"` | Restrict the build to a space-separated subset of `aws-deepracer-util`, `aws-deepracer-device-console`, `aws-deepracer-core`, `aws-deepracer-sample-models`. Defaults to building all four. |

The packages will be created in the `dist/` folder.

Additional helper scripts:

- `build_scripts/build-libcamera.sh` – builds the patched libcamera stack used on Raspberry Pi
- `build_scripts/build-openvino.sh` – assembles the OpenVINO runtime used on the original DeepRacer
- `build_scripts/build-tensorflow.sh` – builds the TensorFlow wheel for TensorFlow Lite inference
- `build_scripts/clean-packages.sh` / `delete-packages.sh` – remove local build artifacts
- `build_scripts/list-packages.sh` / `upload-packages.sh` / `verify-packages.sh` – manage the package repository when publishing a release

## Dependencies

The repository contains a set of external packages that are forked into the `src/` directory. These are primarily the official AWS DeepRacer packages as well as their dependencies, which have been patched with community updates.

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
| [aws-deepracer-launcher](https://github.com/aws-deepracer/aws-deepracer-launcher.git) | Launcher package for AWS DeepRacer |
| [aws-deepracer-community-logging-pkg](../src/aws-deepracer-community-logging-pkg/README.md) | In-tree Python & C++ bag logging nodes |

### Additional vcstool manifests

Some dependencies are not vendored directly in `src/` but are pulled on demand through the vcstool manifests in `src/external/.rosinstall*`. The build scripts import the correct manifest for the ROS 2 distribution you are targeting:

| Package | Description | ROS releases using it |
|---------|-------------|-----------------------|
| [rosbag2](https://github.com/ros2/rosbag2) (`foxy-future`) | Foxy overlay with future rosbag features | Foxy (`.rosinstall-foxy`) |
| [web_video_server](https://github.com/RobotWebTools/web_video_server.git) | Streams ROS image topics over HTTP | Foxy (`.rosinstall-foxy`) |
| [async_web_server_cpp](https://github.com/GT-RAIL/async_web_server_cpp.git) | Async HTTP server implementation | Foxy (`.rosinstall-foxy`) |
| [rplidar_ros](https://github.com/Slamtec/rplidar_ros.git) | RPLIDAR sensor driver | Foxy (`.rosinstall-foxy`) |
| [camera_ros](https://github.com/christianrauch/camera_ros.git) | Generic ROS 2 camera driver | Humble (`.rosinstall-humble`), Jazzy (`.rosinstall-jazzy`) |

When updating or re-vendoring third-party code, make sure to touch the appropriate `.rosinstall-*` file so Dev Containers and CI jobs keep fetching the right revisions.
