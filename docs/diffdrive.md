# Differential Drive Motor Package

The `diffdrive_motor_pkg` replaces the traditional servo-based steering system with two independent DC motors (left and right) that control both speed and direction through differential speeds. This is a drop-in replacement: it exposes identical ROS2 topics and services as the servo package, so the rest of the software stack requires no changes.

## Hardware

### Raspberry Pi (Recommended)

| Component | Details |
|-----------|---------|
| Motor driver | [Waveshare Motor Driver HAT](https://www.waveshare.com/product/raspberry-pi/hats/motors-relays/servo-driver-hat.htm) (TB6612FNG H-bridge) |
| Motors | Two DC motors, 6–12 V, compatible with TB6612FNG |
| I2C bus | `i2c-1` (auto-detected) |

Enable I2C before use:
```bash
sudo raspi-config   # → Interface Options → I2C → Enable
```

**PWM channel mapping (TB6612FNG)**:

| Channel | Motor | Function |
|---------|-------|----------|
| PWM0 | Left (Motor A) | Speed |
| PWM1 | Left (Motor A) | Direction IN1 |
| PWM2 | Left (Motor A) | Direction IN2 |
| PWM5 | Right (Motor B) | Speed |
| PWM3 | Right (Motor B) | Direction IN1 |
| PWM4 | Right (Motor B) | Direction IN2 |

### Original DeepRacer Hardware

The package also supports the original DeepRacer board via its PWM channels (`i2c-0`). Same channel mapping applies.

## Enabling Differential Drive

Steering mode is selected through the vehicle configuration system and takes effect on the next service restart.

**Option A — Web console** (recommended):
1. Open the DeepRacer web console → **Settings → Car Settings**
2. Under **Steering Mode** select **Differential Drive**
3. Click **Save**, then restart the `deepracer-core` service

**Option B — Config file**:
```bash
sudo jq '.steering.mode = "diffdrive"' /opt/aws/deepracer/config.json \
  | sudo tee /opt/aws/deepracer/config.json
sudo systemctl restart deepracer-core
```

**Option C — Direct launch** (testing only, bypasses config):
```bash
ros2 launch diffdrive_motor_pkg diffdrive_motor_pkg_launch.py \
  max_left_differential:=0.3 \
  max_right_differential:=0.3 \
  motor_polarity:=-1
```

The default steering mode is `servo`. If `config.json` does not contain a `steering.mode` entry, or if `deepracer-core` starts without a config file, the servo package is used.

## How It Works

`start_ros.sh` reads `steering.mode` from `/opt/aws/deepracer/config.json` and passes it as a `ros2 launch` argument to `deepracer_launcher.py`, which starts either the servo package or `diffdrive_motor_pkg`.

Inside `diffdrive_motor_pkg`, incoming `ServoCtrlMsg` messages carry a normalised `angle` (−1.0 … 1.0) and `throttle` (−1.0 … 1.0). The `DifferentialDriveController` converts these to left/right motor speeds using the following logic:

- Both wheels start at the commanded throttle speed.
- The inner wheel (the one on the turning side) is slowed by a fraction proportional to `angle` and bounded by `max_left_differential` / `max_right_differential`.
- The outer wheel speed is increased by the same fraction, so it can exceed the commanded base speed.
- `center_offset` shifts the zero-angle point to compensate for mechanical misalignment.
- `motor_polarity` flips direction for both wheels when wiring requires it.

## Configuration Parameters

These can be set as launch arguments or via the ROS2 parameter server at runtime.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_forward_speed` | 1.0 | Cap on forward motor speed (0.0–1.0) |
| `max_backward_speed` | 1.0 | Cap on reverse motor speed (0.0–1.0) |
| `max_left_differential` | 0.5 | Maximum speed reduction on the left wheel during a left turn (0.0–1.0) |
| `max_right_differential` | 0.5 | Maximum speed reduction on the right wheel during a right turn (0.0–1.0) |
| `center_offset` | 0.0 | Steering zero-point offset (−1.0–1.0) |
| `motor_polarity` | 1 | Reverses both motors when set to −1 |

Update at runtime without restarting:
```bash
ros2 param set /diffdrive_motor_node max_left_differential 0.3
ros2 param set /diffdrive_motor_node center_offset 0.05
```

## Calibration Particularities

The DeepRacer calibration system was designed for a servo (steering) and ESC (throttle). `diffdrive_motor_pkg` exposes the same `/servo_pkg/get_calibration` and `/servo_pkg/set_calibration` ROS2 services for drop-in compatibility, but the mapping is different.

### What the calibration values mean in diffdrive

The `SetCalibrationSrv` request has fields `cal_type`, `min`, `mid`, `max`, and `polarity`. Their meaning in the diffdrive context:

| `cal_type` | Conventional meaning | Diffdrive mapping |
|------------|---------------------|-------------------|
| `0` (steering) | Servo angle limits | Maps `min`/`max` to `max_left_differential` / `max_right_differential`; `mid` becomes `center_offset` |
| `1` (throttle) | ESC speed limits | Maps `min`/`max` to `max_backward_speed` / `max_forward_speed` |

`polarity` maps directly to `motor_polarity`.

> **Note**: The web console calibration page was built for servo/ESC hardware. If you use the console calibration sliders with diffdrive, the "angle" slider adjusts turning aggressiveness and the "throttle" slider adjusts speed limits — not raw servo PWM values. The visual preview in the console reflects this remapping.

### Calibration file

Calibration is stored in `/opt/aws/deepracer/calibration.json` (same location as servo calibration). The file format is JSON with the differential drive parameters. On node startup, `CalibrationManager` loads this file and applies the values. If the file is absent or malformed, defaults from `motor_constants.hpp` are used.

Inspect or reset the file:
```bash
# View current calibration
cat /opt/aws/deepracer/calibration.json

# Reset to defaults by deleting the file (node will recreate it)
sudo rm /opt/aws/deepracer/calibration.json && sudo systemctl restart deepracer-core
```

### Recommended calibration procedure

1. **Test straight-line motion** — send zero-angle, moderate throttle and observe whether the vehicle tracks straight:
   ```bash
   ros2 topic pub /ctrl_pkg/servo_msg deepracer_interfaces_pkg/msg/ServoCtrlMsg \
     "{angle: 0.0, throttle: 0.3}" --once
   ```
   If it curves, adjust `center_offset` (positive → compensates a right pull, negative → compensates a left pull).

2. **Test turning** — send a full-angle command and observe sharpness:
   ```bash
   ros2 topic pub /ctrl_pkg/servo_msg deepracer_interfaces_pkg/msg/ServoCtrlMsg \
     "{angle: 1.0, throttle: 0.3}" --once
   ```
   If turns are too sharp, reduce `max_right_differential` (or `max_left_differential`).

3. **Fix inverted direction** — if the vehicle moves backwards when commanded forward, set `motor_polarity` to `-1`.

4. **Persist** the final values via the calibration service:
   ```bash
   # Save throttle limits
   ros2 service call /servo_pkg/set_calibration deepracer_interfaces_pkg/srv/SetCalibrationSrv \
     "{cal_type: 1, min: -80, mid: 0, max: 80, polarity: 1}"

   # Save steering limits and center
   ros2 service call /servo_pkg/set_calibration deepracer_interfaces_pkg/srv/SetCalibrationSrv \
     "{cal_type: 0, min: -40, mid: 5, max: 40, polarity: 1}"
   ```

## ROS2 Interface

### Subscribed Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/ctrl_pkg/servo_msg` | `ServoCtrlMsg` | Normalised angle + throttle commands |
| `/ctrl_pkg/raw_pwm` | `ServoCtrlMsg` | Direct PWM commands (bypass controller) |

### Published Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/servo_pkg/latency` | `LatencyMeasureMsg` | Control loop latency measurements (same topic as servo package) |

### Services

| Service | Type | Description |
|---------|------|-------------|
| `/servo_pkg/get_calibration` | `GetCalibrationSrv` | Read current calibration values |
| `/servo_pkg/set_calibration` | `SetCalibrationSrv` | Write calibration values (persisted to file) |
| `/servo_pkg/servo_gpio` | `ServoGPIOSrv` | GPIO compatibility stub |
| `/servo_pkg/get_led_state` | `GetLedCtrlSrv` | LED state (silent — HAT has no RGB LED) |
| `/servo_pkg/set_led_state` | `SetLedCtrlSrv` | LED state (silent — commands accepted, ignored) |

## Troubleshooting

**Vehicle curves on a straight command**  
Adjust `center_offset` incrementally (±0.05 steps) until straight-line motion is achieved.

**Turns too sharp / not sharp enough**  
Decrease or increase `max_left_differential` and `max_right_differential`. Values above 0.6 result in very tight turns.

**One or both motors run in the wrong direction**  
Set `motor_polarity: -1` to invert both motors.

**I2C permission denied**  
```bash
sudo usermod -a -G i2c $USER && sudo reboot
```

**Motors do not respond**  
```bash
# Check I2C devices are visible
i2cdetect -y 1   # Raspberry Pi
i2cdetect -y 0   # Original DeepRacer

# Check PWM sysfs entries
ls /sys/class/pwm/
```

**Calibration service errors**  
Verify the node is running and the service is advertised:
```bash
ros2 service list | grep calibration
```
If absent, the node failed to start — check `ros2 topic echo /rosout` for error messages.

## Known Limitations

**No RGB LED support**  
The diff-drive HAT (Adafruit Motor HAT / compatible) has no RGB LED. The `/servo_pkg/get_led_state` and `/servo_pkg/set_led_state` services are present for drop-in compatibility, but LED commands are silently ignored. The status LED indicator in the DeepRacer web console will not reflect the vehicle's actual state when using diff-drive mode.
