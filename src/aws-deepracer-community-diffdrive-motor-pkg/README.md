# AWS DeepRacer Community Differential Drive Motor Package

This package provides a comprehensive differential drive motor control system that replaces the traditional AWS DeepRacer servo-based steering. Instead of using a servo for steering and a single motor for throttle (traditional RC car setup), this system uses two independent motors (left and right) to control both movement and steering through differential speeds, enabling more precise control and advanced robotic capabilities.

## Key Features

- **Differential Drive Control**: Advanced kinematics converting servo-style commands (angle + throttle) to precise left/right motor speeds
- **Multi-Platform Hardware Support**: 
  - Raspberry Pi with Waveshare Motor Driver HAT (TB6612FNG)
  - Original AWS DeepRacer hardware via PWM channels
  - Automatic platform detection and configuration
- **Complete Backward Compatibility**: Drop-in replacement maintaining identical ROS2 interfaces
- **Configurable Control Parameters**: 
  - Adjustable turning radius constraints
  - Motor speed limits and differential controls
  - Center offset compensation
  - Motor polarity inversion support
- **Silent LED Compatibility**: Provides LED service interfaces for platforms without RGB LEDs
- **Comprehensive Testing**: Full unit test coverage with hardware abstraction
- **Calibration Persistence**: Compatible with existing DeepRacer calibration workflows

## Hardware Requirements

### Raspberry Pi Setup (Recommended)
- **Platform**: Raspberry Pi 4 (2GB+ RAM recommended)
- **Motor Driver**: Waveshare Motor Driver HAT for Raspberry Pi
- **Motors**: Two DC motors compatible with TB6612FNG H-bridge (6V-12V)
- **Connectivity**: I2C enabled (`sudo raspi-config` → Interface Options → I2C → Enable)
- **Power**: Adequate power supply for Pi + motors (consider external battery pack)

### Original DeepRacer Hardware
- **Vehicle**: AWS DeepRacer with accessible PWM channels
- **Motors**: Two independent motors connected to PWM channels 0-5
- **Power**: Standard DeepRacer power management

### Wiring Notes
- **TB6612FNG Channels**: 
  - Motor A (Left): PWM0 (speed), PWM1+PWM2 (direction)
  - Motor B (Right): PWM5 (speed), PWM3+PWM4 (direction)
- **I2C Bus**: Automatically detected (`i2c-1` for RPi, `i2c-0` for DeepRacer)

## Installation

### Prerequisites
```bash
# Ensure ROS2 Humble is installed and sourced
source /opt/ros/humble/setup.bash

# Install build dependencies
sudo apt update
sudo apt install -y build-essential cmake pkg-config libjsoncpp-dev
```

### Build from Source

1. **Clone the repository** (if not already in workspace):
```bash
cd ~/deepracer_ws/src
# Repository should already be present as part of deepracer-custom-car
```

2. **Install ROS dependencies**:
```bash
cd ~/deepracer_ws
rosdep update
rosdep install --from-paths src --ignore-src -r -y
```

3. Build the package:
```bash
colcon build --packages-select diffdrive_motor_pkg
```

4. **Source the workspace**:
```bash
source install/setup.bash
```

## Usage

### Quick Start

**Basic launch** (with default parameters):
```bash
ros2 launch diffdrive_motor_pkg diffdrive_motor_pkg_launch.py
```

**Launch with custom parameters**:
```bash
ros2 launch diffdrive_motor_pkg diffdrive_motor_pkg_launch.py \
  max_turn_differential:=0.3 \
  motor_polarity:=-1
```

### Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_forward_speed` | float | 1.0 | Maximum forward speed (0.0-1.0) |
| `max_backward_speed` | float | 1.0 | Maximum backward speed (0.0-1.0) |
| `max_left_differential` | float | 0.5 | Maximum left turn differential (0.0-1.0) |
| `max_right_differential` | float | 0.5 | Maximum right turn differential (0.0-1.0) |
| `center_offset` | float | 0.0 | Steering center offset compensation (-1.0 to 1.0) |
| `motor_polarity` | int | 1 | Global motor polarity (1 or -1) |

### Platform-Specific Configuration

**Raspberry Pi Example**:
```bash
ros2 launch diffdrive_motor_pkg diffdrive_motor_pkg_launch.py \
  max_turn_differential:=0.6 \
  max_forward_speed:=0.8
```

**DeepRacer Hardware Example**:
```bash
ros2 launch diffdrive_motor_pkg diffdrive_motor_pkg_launch.py \
  max_turn_differential:=0.4 \
  center_offset:=0.1
```

## ROS2 Interface

### Subscribed Topics

| Topic | Message Type | Description |
|-------|--------------|-------------|
| `/ctrl_pkg/servo_msg` | `deepracer_interfaces_pkg/msg/ServoCtrlMsg` | Primary servo control commands (angle + throttle) |
| `/ctrl_pkg/raw_pwm` | `deepracer_interfaces_pkg/msg/ServoCtrlMsg` | Raw PWM commands for direct control |

### Published Topics

| Topic | Message Type | Description |
|-------|--------------|-------------|
| `/diffdrive_motor_pkg/latency` | `deepracer_interfaces_pkg/msg/LatencyMeasureMsg` | Control loop latency measurements |

### Services

| Service | Type | Description |
|---------|------|-------------|
| `/get_calibration` | `deepracer_interfaces_pkg/srv/GetCalibrationSrv` | Retrieve current calibration values |
| `/set_calibration` | `deepracer_interfaces_pkg/srv/SetCalibrationSrv` | Update calibration parameters |
| `/servo_gpio` | `deepracer_interfaces_pkg/srv/ServoGPIOSrv` | GPIO control (compatibility) |
| `/get_led_ctrl` | `deepracer_interfaces_pkg/srv/GetLedCtrlSrv` | Get LED state (silent implementation) |
| `/set_led_ctrl` | `deepracer_interfaces_pkg/srv/SetLedCtrlSrv` | Set LED state (silent implementation) |

### Message Examples

**Servo Control Message**:
```yaml
# Move forward with slight right turn
angle: 0.3          # -1.0 (left) to 1.0 (right)
throttle: 0.5       # -1.0 (reverse) to 1.0 (forward)
```

**Calibration Service Call**:
```bash
# Get current motor calibration
ros2 service call /get_calibration deepracer_interfaces_pkg/srv/GetCalibrationSrv "{cal_type: 1}"

# Set steering calibration
ros2 service call /set_calibration deepracer_interfaces_pkg/srv/SetCalibrationSrv \
  "{cal_type: 0, min: -30, mid: 0, max: 40, polarity: 1}"
```

## Configuration & Calibration

### Configuration Methods

**1. Launch Parameters** (recommended for testing):
```bash
ros2 launch diffdrive_motor_pkg diffdrive_motor_pkg_launch.py \
  max_forward_speed:=0.8 \
  max_turn_differential:=0.4
```

**2. ROS2 Parameter Server** (runtime updates):
```bash
ros2 param set /diffdrive_motor_node max_forward_speed 0.7
ros2 param set /diffdrive_motor_node max_left_differential 0.3
```

**3. Calibration Services** (persistent storage):
```bash
# Motor calibration (cal_type: 1)
ros2 service call /set_calibration deepracer_interfaces_pkg/srv/SetCalibrationSrv \
  "{cal_type: 1, min: -80, mid: 0, max: 90, polarity: 1}"

# Steering calibration (cal_type: 0)  
ros2 service call /set_calibration deepracer_interfaces_pkg/srv/SetCalibrationSrv \
  "{cal_type: 0, min: -50, mid: 5, max: 45, polarity: 1}"
```

### Calibration Data Persistence

- **File Location**: `~/.deepracer/calibration.json`
- **Format**: JSON with differential drive parameters
- **Backward Compatibility**: Converts to/from traditional servo calibration format
- **Auto-loading**: Calibration restored on node startup

### Configuration Parameters Deep Dive

| Category | Parameters | Effect |
|----------|------------|--------|
| **Speed Control** | `max_forward_speed`, `max_backward_speed` | Limits maximum motor speeds |
| **Turning Control** | `max_left_differential`, `max_right_differential` | Controls turning responsiveness |
| **Alignment** | `center_offset` | Compensates for mechanical misalignment |
| **Motor Setup** | `motor_polarity`, `invert_left_motor`, `invert_right_motor` | Handles wiring variations |

## Calibration Workflow

### Web Console Integration
The package maintains full compatibility with the DeepRacer web console calibration interface:

1. **Access calibration** via DeepRacer device console
2. **Traditional calibration values** are automatically converted to differential drive parameters
3. **Real-time preview** shows motor response during calibration
4. **Persistent storage** maintains settings across reboots

### Manual Calibration Process

**Step 1: Basic Motor Test**
```bash
# Test forward motion
ros2 topic pub /ctrl_pkg/servo_msg deepracer_interfaces_pkg/msg/ServoCtrlMsg \
  "{angle: 0.0, throttle: 0.3}" --once

# Test turning (right)
ros2 topic pub /ctrl_pkg/servo_msg deepracer_interfaces_pkg/msg/ServoCtrlMsg \
  "{angle: 0.5, throttle: 0.3}" --once
```

**Step 2: Fine-tune Parameters**
```bash
# Adjust turn sensitivity if turning too aggressive
ros2 param set /diffdrive_motor_node max_right_differential 0.3

# Adjust if vehicle pulls to one side
ros2 param set /diffdrive_motor_node center_offset 0.05
```

**Step 3: Save Calibration**
```bash
# Save current parameters to persistent storage
ros2 service call /set_calibration deepracer_interfaces_pkg/srv/SetCalibrationSrv \
  "{cal_type: 1, min: -100, mid: 0, max: 100, polarity: 1}"
```

## Testing & Validation

### Running Unit Tests

**Execute all tests**:
```bash
# Build and run tests
colcon build --packages-select diffdrive_motor_pkg
colcon test --packages-select diffdrive_motor_pkg

# View detailed results
colcon test-result --verbose --test-result-base build/diffdrive_motor_pkg
```

**Run specific test suites**:
```bash
# Test differential drive controller logic
./build/diffdrive_motor_pkg/test_differential_drive_controller

# Test motor manager hardware abstraction
./build/diffdrive_motor_pkg/test_motor_manager

# Test calibration system
./build/diffdrive_motor_pkg/test_calibration_manager

# Test basic PWM integration
./build/diffdrive_motor_pkg/test_motor_pwm_basic
```

### Test Coverage

| Component | Test File | Coverage |
|-----------|-----------|----------|
| **Differential Drive Controller** | `test_differential_drive_controller.cpp` | Algorithm validation, edge cases, input validation |
| **Motor Manager** | `test_motor_manager.cpp` | Hardware abstraction, state management |
| **Calibration Manager** | `test_calibration_manager.cpp` | Service compatibility, data persistence |
| **PWM Integration** | `test_motor_pwm_basic.cpp` | Basic PWM functionality, TB6612FNG control |

### Integration Testing

**Manual hardware test**:
```bash
# Start the node
ros2 launch diffdrive_motor_pkg diffdrive_motor_pkg_launch.py

# Test basic movement
ros2 topic pub /ctrl_pkg/servo_msg deepracer_interfaces_pkg/msg/ServoCtrlMsg \
  "{angle: 0.0, throttle: 0.2}" --rate 10

# Monitor system state
ros2 topic echo /diffdrive_motor_pkg/latency
```

### Performance Monitoring

**Real-time diagnostics**:
```bash
# Monitor control latency
ros2 topic echo /diffdrive_motor_pkg/latency

# Check parameter values
ros2 param dump /diffdrive_motor_node

# View system logs
ros2 run diffdrive_motor_pkg diffdrive_motor_node --ros-args --log-level debug
```

## Troubleshooting

### Common Issues & Solutions

#### I2C Permission Errors
**Symptoms**: `Permission denied` when accessing `/dev/i2c-*`
```bash
# Solution: Add user to i2c group
sudo usermod -a -G i2c $USER
sudo reboot
```

#### Motors Not Responding
**Symptoms**: No motor movement despite commands
```bash
# Check hardware initialization
ros2 topic echo /rosout | grep -i motor

# Verify I2C devices
i2cdetect -y 1  # Raspberry Pi
i2cdetect -y 0  # DeepRacer

# Test PWM export
ls /sys/class/pwm/
```

#### Inverted Motor Direction
**Symptoms**: Vehicle moves backward when commanded forward, or turns opposite direction
```bash
# Solution: Invert motor polarity
ros2 param set /diffdrive_motor_node motor_polarity -1

# Or invert individual motors
ros2 param set /diffdrive_motor_node invert_left_motor true
ros2 param set /diffdrive_motor_node invert_right_motor true
```

#### Vehicle Pulls to One Side
**Symptoms**: Straight line commands cause curved motion
```bash
# Solution: Adjust center offset
ros2 param set /diffdrive_motor_node center_offset 0.05  # Pulls right, compensate left
ros2 param set /diffdrive_motor_node center_offset -0.05 # Pulls left, compensate right
```

#### Excessive Turn Sensitivity
**Symptoms**: Small steering inputs cause sharp turns
```bash
# Solution: Reduce differential limits
ros2 param set /diffdrive_motor_node max_left_differential 0.3
ros2 param set /diffdrive_motor_node max_right_differential 0.3
```

#### Calibration Service Failures
**Symptoms**: Calibration calls return error codes
```bash
# Solution: Reset to defaults and verify service availability
ros2 service call /set_calibration deepracer_interfaces_pkg/srv/SetCalibrationSrv \
  "{cal_type: 1, min: -100, mid: 0, max: 100, polarity: 1}"

# Check service is running
ros2 service list | grep calibration
```

### Debug Tools

#### Enable Debug Logging
```bash
ros2 run diffdrive_motor_pkg diffdrive_motor_node --ros-args --log-level debug
```

#### Real-time Parameter Monitoring
```bash
# Watch parameter changes
watch -n 1 'ros2 param dump /diffdrive_motor_node'

# Monitor topics
ros2 topic hz /ctrl_pkg/servo_msg
ros2 topic hz /diffdrive_motor_pkg/latency
```

#### Hardware Diagnostics
```bash
# Check PWM system
ls -la /sys/class/pwm/pwmchip*/

# Monitor I2C traffic (requires i2c-tools)
sudo i2cdump -y 1 0x60  # Typical Waveshare HAT address

# Check system resources
htop  # CPU usage
iostat -x 1  # I/O statistics
```

### Performance Optimization

#### Low Latency Configuration
```bash
# Reduce control loop overhead
ros2 param set /diffdrive_motor_node use_sim_time false

# Optimize system scheduling
sudo renice -10 $(pgrep diffdrive_motor_node)
```

#### Power Management
```bash
# Monitor power consumption
vcgencmd measure_volts  # Raspberry Pi voltage
vcgencmd get_throttled   # Throttling status
```

## Architecture & Design

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    DifferentialDriveNode                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │  ROS2 Interface │  │ Service Handlers │  │ Publishers  │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│                DifferentialDriveController                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ Servo to Motor  │  │ Input Validation│  │ Kinematics  │ │
│  │   Conversion    │  │  & Clamping     │  │ Algorithms  │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│                      MotorManager                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ Hardware Init   │  │  TB6612FNG      │  │ PWM Control │ │
│  │ & Platform      │  │  Direction      │  │ & Speed     │ │
│  │ Detection       │  │  Control        │  │ Management  │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│                       PWM Layer                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │  Linux PWM      │  │   I2C Device    │  │ Sysfs File  │ │
│  │  Subsystem      │  │   Discovery     │  │ Interface   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Design Principles

- **Backward Compatibility**: Maintains servo package interfaces
- **Modular Architecture**: Separate concerns with clear interfaces  
- **Hardware Abstraction**: Platform-independent motor control
- **Testability**: Comprehensive unit test coverage
- **Observability**: Latency monitoring and debug logging
- **Configurability**: Runtime parameter adjustment

### Differential Drive Algorithm

The core algorithm converts servo-style inputs to differential motor speeds:

1. **Input Processing**: Validate and clamp angle/throttle inputs
2. **Speed Calculation**: Determine base speed from throttle and direction
3. **Differential Application**: 
   - **Outer wheel**: Maintains commanded speed  
   - **Inner wheel**: Reduced speed based on turn radius
4. **Motor Mapping**: Apply motor polarity and inversion settings
5. **Hardware Output**: Convert to PWM signals for TB6612FNG control

**Algorithm Example**:
```cpp
// Right turn: left wheel outer, right wheel inner
if (angle > 0) {
    left_speed = throttle * max_speed;  // Outer wheel
    right_speed = throttle * max_speed * (1.0 - angle * max_right_differential);
}
```
