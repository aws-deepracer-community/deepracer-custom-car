# AWS DeepRacer Community Differential Drive Motor Package

This package replaces the existing AWS DeepRacer servo package with a differential drive motor control system. Instead of using a servo for steering and a single motor for throttle (traditional RC car setup), the new system uses two motors (left and right) to control both movement and steering through differential speeds.

## Features

- **Differential Drive Control**: Converts servo-style commands (angle + throttle) to left/right motor speeds
- **Hardware Compatibility**: Supports both Raspberry Pi with Waveshare Motor Driver HAT and original DeepRacer hardware
- **Backward Compatibility**: Maintains the same ROS interfaces as the original servo package
- **Configurable Turning**: Adjustable turning radius constraints for realistic vehicle behavior
- **Silent LED Support**: Provides LED service compatibility (commands are silently ignored on Motor Driver HAT)

## Hardware Requirements

### Raspberry Pi Setup
- Raspberry Pi 4 (recommended)
- Waveshare Motor Driver HAT for Raspberry Pi
- Two DC motors (compatible with TB6612FNG H-bridge)
- I2C connection enabled

### Original DeepRacer Setup
- AWS DeepRacer vehicle
- Two motors connected to appropriate PWM channels

## Installation

1. Clone this package into your ROS2 workspace:
```bash
cd ~/deepracer_ws/src
git clone <repository_url> aws-deepracer-community-diffdrive-motor-pkg
```

2. Install dependencies:
```bash
cd ~/deepracer_ws
rosdep install --from-paths src --ignore-src -r -y
```

3. Build the package:
```bash
colcon build --packages-select aws_deepracer_community_diffdrive_motor_pkg
```

4. Source the workspace:
```bash
source install/setup.bash
```

## Usage

### Launch the Node

```bash
ros2 launch aws_deepracer_community_diffdrive_motor_pkg diffdrive_motor_pkg_launch.py
```

### Launch with Custom Parameters

```bash
ros2 launch aws_deepracer_community_diffdrive_motor_pkg diffdrive_motor_pkg_launch.py \
  max_turn_differential:=0.3 \
  invert_left_motor:=true
```

### Available Parameters

- `max_turn_differential`: Maximum speed difference between wheels (0.0-1.0, default: 0.5)
- `pwm_device`: PWM device identifier for chip discovery (default: i2c-1)
- `invert_left_motor`: Invert left motor direction (default: false)
- `invert_right_motor`: Invert right motor direction (default: false)

## ROS2 Interface

### Subscribed Topics

- `/ctrl_pkg/servo_msg` (deepracer_interfaces_pkg/msg/ServoCtrlMsg): Servo control commands
- `/ctrl_pkg/raw_pwm` (deepracer_interfaces_pkg/msg/ServoCtrlMsg): Raw PWM commands

### Published Topics

- `/differential_drive_pkg/latency` (deepracer_interfaces_pkg/msg/LatencyMeasureMsg): Latency measurements

### Services

- `/get_calibration` (deepracer_interfaces_pkg/srv/GetCalibrationSrv): Get calibration values
- `/set_calibration` (deepracer_interfaces_pkg/srv/SetCalibrationSrv): Set calibration values
- `/servo_gpio` (deepracer_interfaces_pkg/srv/ServoGPIOSrv): GPIO control
- `/get_led_ctrl` (deepracer_interfaces_pkg/srv/GetLedCtrlSrv): Get LED state
- `/set_led_ctrl` (deepracer_interfaces_pkg/srv/SetLedCtrlSrv): Set LED state

## Configuration

The package can be configured through the `config/diffdrive_motor_config.yaml` file or launch parameters. Key configuration options include:

- **Differential Drive Parameters**: Control turning behavior and motor response
- **Hardware Configuration**: I2C settings and motor channel mapping
- **Motor Inversion**: Handle motors wired in reverse
- **Calibration**: File path for calibration data persistence

## Calibration

The package maintains compatibility with existing DeepRacer calibration workflows:

1. Use the DeepRacer web console for calibration
2. Calibration values are automatically converted to appropriate motor parameters
3. Calibration data is persisted in the same JSON format as the original servo package

## Testing

Run unit tests:
```bash
colcon test --packages-select aws_deepracer_community_diffdrive_motor_pkg
```

View test results:
```bash
colcon test-result --verbose
```

## Troubleshooting

### Common Issues

1. **I2C Permission Errors**: Ensure the user is in the `i2c` group
2. **Motor Not Responding**: Check wiring and I2C address configuration
3. **Inverted Motor Direction**: Use `invert_left_motor` or `invert_right_motor` parameters
4. **Calibration Issues**: Reset to defaults using the calibration service

### Debug Logging

Enable debug logging to troubleshoot issues:
```bash
ros2 run aws_deepracer_community_diffdrive_motor_pkg diffdrive_motor_node --ros-args --log-level debug
```

## Contributing

Contributions are welcome! Please follow the standard ROS2 development practices and ensure all tests pass before submitting pull requests.

## License

This project is licensed under the Apache 2.0 License - see the LICENSE file for details.