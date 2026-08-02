# DeepRacer Custom Car History

This history summarizes what the custom car stack changes compared with the
stock AWS DeepRacer ROS packages. Instead of following pull requests in time
order, it groups the work by package under `src/`.

## Baseline

The stock AWS DeepRacer stack is centered on the original Intel-based car,
Ubuntu 20.04, ROS 2 Foxy, OpenVINO CPU inference, the factory console, and the
original servo/ESC hardware path.

Most package folders under `src/` were imported from the upstream AWS DeepRacer
repositories as git subtrees on 2025-04-12. This makes a package-by-package
comparison possible: each section below compares the imported stock package to
the current `main` / `launch-24.04` line. The newer `experimental` 2.3.0 work is
intentionally left out of this pass.

## README Feature Alignment

The current README describes the `main` / `launch-24.04` custom-car feature set.
This package-level history maps those features to the packages that implement
them:

- **Faster perception pipeline:** covered by the camera and sensor-fusion changes
  for optimized image handling and compressed image transport.
- **Modern console backend:** covered by webserver, device-info, software-update,
  and emergency-control API additions that the community console can consume.
- **Inference flexibility:** covered by the inference package's TensorFlow Lite
  support, OpenVINO 2024 path for original DeepRacer on Ubuntu 24.04,
  architecture-specific tuning, and model optimizer updates.
- **Ubuntu 24.04 and Raspberry Pi support:** covered by launcher, I2C,
  servo/PWM, status LED, camera, inference, device-info, and platform-detection
  changes. The installer/image scripts live outside `src/`, but are part of the
  same current branch feature set.
- **Model handling and runtime speed:** covered by model-optimizer cleanup,
  inference threading, C++ navigation, and reduced unnecessary LiDAR/sensor work.
- **Logging, health, and latency visibility:** covered by the in-tree community
  logging package, new interface messages, `device_status_node.py`, API exposure,
  and timing data through control, inference, navigation, and servo paths.
- **OS/runtime hardening:** covered by system-package update changes, custom
  package provider support, network/API latency fixes, and platform-specific
  service handling.

Features from the newer 2.3.0 experimental line, such as structured runtime
configuration, differential drive, IMU work, gray overlay, camera rotation, and
later TFLite 2.19/equivalency testing, are deliberately listed under
**Excluded For Now**.

## Comparison Anchors

| Package | Stock import commit |
| --- | --- |
| `aws-deepracer-camera-pkg` | `6d4e617` |
| `aws-deepracer-ctrl-pkg` | `159361a` |
| `aws-deepracer-device-info-pkg` | `2c111a2` |
| `aws-deepracer-i2c-pkg` | `43bdbd5` |
| `aws-deepracer-inference-pkg` | `2a3ea28` |
| `aws-deepracer-interfaces-pkg` | `224f681` |
| `aws-deepracer-launcher` | `785fcb7` |
| `aws-deepracer-model-optimizer-pkg` | `86d5732` |
| `aws-deepracer-navigation-pkg` | `bb33385` |
| `aws-deepracer-sensor-fusion-pkg` | `30680e7` |
| `aws-deepracer-servo-pkg` | `0f687a6` |
| `aws-deepracer-status-led-pkg` | `42a0544` |
| `aws-deepracer-systems-pkg` | `21eeac7` |
| `aws-deepracer-usb-monitor-pkg` | `4a2a906` |
| `aws-deepracer-webserver-pkg` | `928caad` |
| `aws-deepracer-community-logging-pkg` | community-added on current branch |

## Package Changes

### `aws-deepracer-camera-pkg`

Stock role: publishes camera frames for the DeepRacer perception pipeline.

Main custom changes:

- Optimized `camera_node.cpp`, with most of the package delta concentrated in
  image handling code.
- Added build and runtime dependencies for the optimized camera path.
- Adjusted `camera_pkg_launch.py` and package metadata for the custom stack.

Benefit over stock: lower camera-node overhead and better fit with the custom
compressed-image perception path.

### `aws-deepracer-ctrl-pkg`

Stock role: manages manual/autonomous control state and coordinates vehicle
control modes.

Main custom changes:

- Updated `ctrl_node.cpp`, `ctrl_state.cpp`, and `ctrl_state.hpp` for the custom
  control state flow.
- Integrated device-status and latency tracking so control transitions can be
  observed by the rest of the stack.
- Moved earlier patch behavior into maintained source as part of the RPi5
  preparation work.

Benefit over stock: the control package participates in health/latency reporting
and works across the expanded hardware matrix instead of assuming only the
factory car profile.

### `aws-deepracer-device-info-pkg`

Stock role: reports hardware and software identity for the vehicle.

Main custom changes:

- Extended `device_info_node.py` with additional OS, CPU, ROS 2, and hardware
  detection fields.
- Added `device_status_node.py`, a `ring_buffer.py` helper, and supporting
  constants.
- Added system health collection for CPU, memory, disk, and end-to-end latency.
- Optimized the status node after the first implementation so telemetry is less
  expensive to publish.

Benefit over stock: device identity is no longer limited to the original AWS
DeepRacer hardware assumptions, and the car exposes runtime health information
that can be shown in the console and logged for analysis.

### `aws-deepracer-i2c-pkg`

Stock role: reads I2C-attached power and battery information.

Main custom changes:

- Added `battery_dummy_node.cpp` for platforms where stock battery readings are
  unavailable or not wired the same way.
- Updated `battery_node.cpp` and CMake wiring for Raspberry Pi and Ubuntu 24.04
  support.

Benefit over stock: Raspberry Pi and custom builds can run the stack without
being blocked by missing original-car battery hardware.

### `aws-deepracer-inference-pkg`

Stock role: runs model inference for camera and LiDAR inputs, originally through
OpenVINO on the factory Intel platform.

Main custom changes:

- Added a TensorFlow Lite inference engine implementation in
  `tflite_inference_eng.cpp` and `tflite_inference_eng.hpp`.
- Added the newer Intel OpenVINO runtime path in `intel_ov_inference_eng.cpp`
  and `intel_ov_inference_eng.hpp` for original DeepRacer on Ubuntu 24.04.
- Reworked CMake to fetch/build the needed inference backend and apply
  architecture-specific options.
- Added TFLite threading and CPU-specific optimization paths for Intel and ARM.
- Integrated latency measurement from inference into the broader device-status
  pipeline.
- Cleaned up image processing and base inference abstractions so OpenVINO and
  TFLite can coexist.

Benefit over stock: inference is no longer tied only to the factory OpenVINO
2021 CPU path. The custom stack supports TFLite across platforms and keeps
OpenVINO viable on the original car's Ubuntu 24.04/Jazzy line, while exposing
inference timing for performance analysis.

### `aws-deepracer-interfaces-pkg`

Stock role: defines ROS messages and services shared by the DeepRacer packages.

Main custom changes:

- Added `DeviceStatusMsg`, `LatencyMeasureMsg`, and `GetDeviceStatusSrv`.
- Extended `GetDeviceInfoSrv` with extra OS, CPU, ROS 2, and platform fields.
- Updated `ServoCtrlMsg` so latency measurements can travel through the control
  path.
- Adjusted camera, sensor, and inference message definitions for compatibility
  with the custom package changes.

Benefit over stock: the shared ROS contract now carries health, platform, and
latency data instead of only the original driving-control messages.

### `aws-deepracer-launcher`

Stock role: starts the DeepRacer ROS graph with the factory package set and
factory launch assumptions.

Main custom changes:

- Expanded `deepracer_launcher.py` with arguments for camera mode, LiDAR,
  logging, inference engine/device, dummy battery behavior, and platform-specific
  nodes.
- Converted the launcher from a fixed stock launch description into an
  `OpaqueFunction`-driven setup that reads launch arguments at runtime and builds
  the node graph conditionally.
- Added legacy/modern camera branching: stock `camera_pkg` for legacy mode and
  `camera_ros`/libcamera for modern mode.
- Added Raspberry Pi camera detection through `libcamera.CameraManager`, with
  sensor-mode choices for IMX219 and IMX708 cameras to avoid cropped input and
  enable autofocus on IMX708.
- Added launch support for the C++ navigation node and device-status node.
- Added launch selection for the in-tree logging package, including the C++ bag
  logger on Jazzy deployments.
- Configured bag logging to trigger from `/deepracer_navigation_pkg/auto_drive`,
  name bags from `/inference_pkg/model_artifact`, and record inference results
  plus device-status telemetry.
- Added inference/model-optimizer parameters so the same launch file can start
  TFLite, OpenVINO CPU, OpenVINO GPU, or MYRIAD/NCS-backed deployments.
- Made LiDAR conditional and passed that decision into sensor fusion so overlay
  generation is only enabled when RPLIDAR is present.
- Switched the web video server default transport to compressed images, matching
  the optimized perception/display pipeline.
- Updated modern camera launch behavior for libcamera/camera_ros changes,
  autofocus support, and USB camera configuration fixes.
- Added compatibility fixes for Python 3.8 and multiple ROS 2 distributions.
- Added timing/latency plumbing so launched nodes can participate in telemetry.

Benefit over stock: startup is no longer a single factory graph. The same launch
file can assemble the right runtime for original DeepRacer, Ubuntu 24.04,
Raspberry Pi, modern/legacy cameras, optional LiDAR, multiple inference engines,
and integrated logging/telemetry.

### `aws-deepracer-model-optimizer-pkg`

Stock role: converts trained models into OpenVINO intermediate representation
artifacts for inference.

Main custom changes:

- Reworked `model_optimizer_node.py` and constants to support the custom
  inference/backend matrix.
- Added OpenVINO IR-version validation for cached `model.xml` files, so a model
  optimized with OpenVINO 2021 IR v10 is re-optimized when the current runtime
  expects OpenVINO 2022+ IR v11.
- Moved common optimizer improvements from patches into source.
- Cleaned packaging metadata and setup configuration.

Benefit over stock: model optimization supports the custom runtime choices more
cleanly, caches safely across OpenVINO generations, and is easier to maintain
across ROS/Ubuntu variants.

### `aws-deepracer-navigation-pkg`

Stock role: converts inference results into steering and throttle commands.

Main custom changes:

- Added a C++ navigation implementation: headers, `deepracer_navigation_node.cpp`,
  `main.cpp`, CMake files, and a C++ launch file.
- Removed the old Python-only packaging path from the package build.
- Kept the Python node present but moved the custom stack toward the lower
  overhead C++ node.
- Integrated latency/status measurements into the navigation path.

Benefit over stock: the action-selection path can run with less runtime overhead
and can report timing through the telemetry pipeline.

### `aws-deepracer-sensor-fusion-pkg`

Stock role: combines camera and LiDAR information and publishes display/overlay
outputs.

Main custom changes:

- Updated `sensor_fusion_node.cpp` for the custom compressed-image and optional
  LiDAR behavior.
- Added build dependencies and CMake changes needed by the custom image
  transport path.
- Avoided unnecessary LiDAR overlay processing when LiDAR is not available.

Benefit over stock: cars without LiDAR avoid wasted processing, while cars with
LiDAR keep the sensor-fusion path available.

### `aws-deepracer-servo-pkg`

Stock role: drives the steering servo and throttle ESC on original hardware.

Main custom changes:

- Reworked PWM handling in `pwm.cpp` and `pwm.hpp` for Raspberry Pi and RPi5
  support.
- Updated `servo_mgr.cpp`, `servo_mgr.hpp`, and `servo_node.cpp` for telemetry
  and platform compatibility.
- Integrated latency measurements from servo output into device status.

Benefit over stock: servo control works beyond the original hardware assumptions
and contributes to end-to-end latency analysis.

### `aws-deepracer-status-led-pkg`

Stock role: controls DeepRacer status LEDs.

Main custom changes:

- Added `gpiod_module.py` for modern GPIO access on Raspberry Pi 5 and newer
  Linux stacks.
- Expanded status LED constants and adjusted `led_control.py` and
  `status_led_node.py` for non-stock GPIO mappings.

Benefit over stock: LED status works across original DeepRacer and Raspberry Pi
hardware instead of assuming the factory GPIO interface.

### `aws-deepracer-systems-pkg`

Stock role: manages system-level services such as network, model loading,
software update, OTG, and helper scripts.

Main custom changes:

- Updated software update handling to support multiple source lists and package
  provider relationships.
- Added `python3-apt` dependency support used by package/update flows.
- Reworked OTG configuration/control, network monitoring, model loading, and
  system scripts for the custom install layout.
- Reduced network/status API latency by avoiding slow Wi-Fi scans for the
  current SSID, and made rsyslog/OTG handling less disruptive during runtime.
- Moved common optimizations from patches into source.

Benefit over stock: updates can install community replacement packages cleanly,
network/status APIs respond faster under load, and system services are less tied
to the factory filesystem and networking assumptions.

### `aws-deepracer-usb-monitor-pkg`

Stock role: monitors USB devices and reacts to inserted media.

Main custom changes:

- Patched `usb_monitor_node.py` and setup configuration for the custom stack.
- Kept the package aligned with the modified logging and install behavior.

Benefit over stock: USB monitoring remains compatible with the custom logging and
deployment workflows.

### `aws-deepracer-webserver-pkg`

Stock role: provides the backend API used by the DeepRacer console.

Main custom changes:

- Extended `device_info_api.py` to expose the additional device-info and
  device-status fields.
- Added emergency stop support in `vehicle_control.py`.
- Added `time_api.py` with time/timezone reporting and timezone update support
  through the console backend.
- Updated login/auth handling and SSH API behavior for the custom console flow.
- Added API discovery support and improved restart tolerance in the webserver
  publisher node.
- Replaced a slow `nmcli` Wi-Fi SSID lookup with a faster `iwgetid` path.
- Adjusted software update and utility helpers for community package sources.

Benefit over stock: the webserver exposes the custom car's new status,
time-management, emergency-control, and update capabilities to the console.

### `aws-deepracer-community-logging-pkg`

Stock role: this package is community-added; stock DeepRacer did not ship an
in-tree logging package with both Python and C++ implementations.

Main custom changes:

- Added `logging_pkg` with a Python `bag_log_node` and a C++
  `bag_log_node_cpp` implementation.
- Records ROS 2 topics to bags when autonomous driving starts, using inference
  results and model-name topics to trigger and name sessions.
- Supports USB-aware log storage, configurable logging mode, configurable storage
  provider, and a `stop_logging` service.
- Uses the C++ node by default on Jazzy-style production deployments, where the
  README reports roughly 80-90% lower CPU use and 40-60% lower memory use than
  the Python implementation.

Benefit over stock: logs become a first-class part of the custom stack instead
of an external helper, making camera/inference/status data easier to capture and
analyze after runs.

## Mainline Features Outside `src/`

Some README features are intentionally outside the ROS package folders but are
part of the current `main` / `launch-24.04` line:

- **Ubuntu 24.04 image and installer flow:** `install_scripts/aws-24.04/`,
  `install_scripts/rpi-24.04/`, and related package scripts support fresh Noble
  installs for original DeepRacer and Raspberry Pi targets.
- **Custom image creation and flashing:** `create-image.sh` and
  `utils/custom_image/usb_flash.sh` support repeatable image generation and USB
  flashing workflows for original DeepRacer hardware.
- **Security and boot support:** the 24.04 image flow includes root-device
  encryption support, TPM/LUKS helper scripts, shim/GRUB certificate handling,
  and root partition resize fixes after flashing.
- **OS-level tuning:** install scripts apply performance and reliability settings
  such as CPU performance mode, Wi-Fi power-save changes, suspend avoidance, and
  reduced unnecessary services.
- **Runtime auto-selection:** `build_scripts/files/common/start_ros.sh` sources
  whichever OpenVINO setup is installed (`2022` first, then `2021`), selects the
  inference backend/device from attached hardware, enables a dummy battery node
  on Raspberry Pi, defaults non-Foxy systems to modern camera mode, reads
  `logging.conf`, detects RPLIDAR through the CP210x UART bridge, and passes all
  of those choices into `deepracer_launcher.py`.

Together, `start_ros.sh` and `deepracer_launcher.py` are the custom stack's
runtime adapter layer: the shell script detects the installed OS/hardware state,
and the launcher turns those detected choices into the ROS graph that actually
runs the car.

## Excluded For Now

The following areas are real project work, but they are outside this package
comparison pass because they belong to the newer experimental 2.3.0 line rather
than the current `main` / `launch-24.04` baseline:

- Structured `config.json` runtime configuration and console car-config API.
- Differential drive motor package.
- Gray overlay camera preprocessing.
- Camera rotation/orientation configuration.
- BMI160 IMU package and event API.
- Expanded equivalency testing and TensorFlow Lite 2.19 follow-up work.

These can be added in a second package pass once the 2.3.0 experimental scope is
included intentionally.