# IMU Package (`imu_pkg`)

**AWS DeepRacer Community** — ROS 2 package for the Bosch BMI160 6-DOF IMU.

Reads the BMI160 via Linux I2C userspace (no kernel module required), publishes
`sensor_msgs/Imu`, and provides two optional safety features: **stop on crash**
and **stop on pickup**.

---

## Table of Contents

1. [Hardware](#hardware)
2. [Architecture](#architecture)
3. [Topics and Services](#topics-and-services)
4. [Parameters](#parameters)
5. [Launch](#launch)
6. [Safety Features](#safety-features)
7. [Signal Processing](#signal-processing)
8. [Calibration](#calibration)
9. [Integration with deepracer\_launcher](#integration-with-deepracer_launcher)
10. [Building and Testing](#building-and-testing)
11. [Package Structure](#package-structure)

---

## Hardware

| Item | Value |
|---|---|
| Sensor | Bosch BMI160 6-DOF IMU (accelerometer + gyroscope) |
| Interface | Linux I2C userspace (`/dev/i2c-N`) via `ioctl` |
| Default I2C bus | 7 (original DeepRacer), 1 (Raspberry Pi) |
| Default I2C address | 0x68 |
| ODR | 100 Hz (hardware), published at configurable rate (default 25 Hz) |
| Hardware filter | OSR4 (4× oversampling) — halves noise floor vs. normal mode |

The BMI160 on the DeepRacer community board is mounted **upside-down** relative
to the vehicle frame. The driver applies axis remapping so the published data
follows REP-103 conventions (X = forward, Y = left, Z = up) regardless of
physical orientation.

---

## Architecture

```
Linux I2C (/dev/i2c-N)
        │
        ▼
   BMI160 driver              (bmi160.cpp)
   - init / configure
   - FOC calibration
   - readMotion6()
   - isHighGTriggered()
        │
        ▼
   conversions.hpp             (pure math, fully unit-tested)
   - applyAxisMapping()
   - ema()
   - isPickupDetected()
        │
        ▼
   ImuNode (imu_node.cpp)      (ROS 2 node)
   - timerCallback @ publish_rate Hz
   - safety checks
   - publisher: /imu_pkg/imu_msg/data_raw
   - client:    /ctrl_pkg/enable_state
```

---

## Topics and Services

### Published

| Topic | Type | QoS | Notes |
|---|---|---|---|
| `/imu_pkg/imu_msg/data_raw` | `sensor_msgs/Imu` | Best-effort, keep-last 1 | Published only when at least one subscriber is present |

The `orientation` field is always zero with `covariance[0] = -1` (unknown).
Diagonal covariances for angular velocity and linear acceleration are set to
`0.01` (rad/s)² and `0.01` (m/s²)² respectively as approximate defaults.

### Service Clients

| Service | Type | When used |
|---|---|---|
| `/ctrl_pkg/enable_state` | `deepracer_interfaces_pkg/EnableStateSrv` | Called with `is_active=false` on crash or pickup |

---

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `bus_id` | int | `7` (DR) / `1` (RPI) | I2C bus number |
| `address` | int | `0x68` (104) | BMI160 I2C slave address |
| `publish_rate` | int | `30` | Publish rate in Hz (matches camera frame rate). Also determines crash-detection polling latency (e.g. 30 Hz → up to 33 ms) |
| `accel_range_g` | int | `8` | Accelerometer full-scale range: `2`, `4`, `8`, or `16` G. `8` G covers ~4 G lateral at racing speeds |
| `gyro_range_dps` | int | `1000` | Gyroscope full-scale range: `125`, `250`, `500`, `1000`, or `2000` dps. `1000` dps = 17.5 rad/s, covers tight turns at racing speed without saturation |
| `accel_z_gravity_target` | int | `+1` | Expected sign of `accel_z` when car is flat. `+1` = upside-down mount (DeepRacer default), `-1` = normal mount |
| `stop_on_pickup` | bool | `false` | Enable pickup detection |
| `stop_on_crash` | bool | `false` | Enable crash detection |
| `crash_accel_threshold_g` | double | `3.0` | High-G crash threshold in G |
| `pickup_threshold_g` | double | `0.5` | Pickup detection sensitivity in G. Increase to reduce false positives during hard cornering |
| `filter_alpha` | double | `0.5` | EMA smoothing factor `(0, 1]`. `1.0` = no filtering; lower values give more smoothing at the cost of lag |

---

## Launch

### Standalone

```bash
ros2 launch imu_pkg imu_pkg_launch.py
```

All parameters are exposed as launch arguments:

```bash
ros2 launch imu_pkg imu_pkg_launch.py \
    bus_id:=7 \
    publish_rate:=50 \
    stop_on_crash:=true \
    crash_accel_threshold_g:=3.0 \
    stop_on_pickup:=true \
    pickup_threshold_g:=0.5 \
    filter_alpha:=0.5
```

### Monitor output

```bash
ros2 topic echo /imu_pkg/imu_msg/data_raw
```

---

## Safety Features

### Crash Detection (`stop_on_crash`)

Uses the BMI160 hardware high-G interrupt engine — no software polling of
acceleration values is involved.

**How it works:**

1. At startup, `configureHighGInterrupt()` programs the BMI160:
   - Enables high-G monitoring on all three axes simultaneously
   - Sets the threshold register (`INT_LOWHIGH_3`): 1 LSB = 7.81 mg, so
     `crash_accel_threshold_g / 0.00781` → register byte
   - Sets duration (`INT_LOWHIGH_2`) to `0x00` (1 sample = 10 ms trigger)
   - Sets hysteresis (`INT_LOWHIGH_4`) to `0x03` (~47 mg, prevents rapid re-triggers)

2. Every timer tick, `isHighGTriggered()` reads `INT_STATUS_1` (register 0x1D)
   and checks bit 2 (`high_g_int`). The BMI160 latches this bit in hardware —
   a brief impact won't be missed between polls. Reading the register clears it.

3. When triggered, `triggerStop("crash")` calls `/ctrl_pkg/enable_state` with
   `is_active=false` (fire-and-forget async). The car halts and **latches**
   inactive until a human re-enables it via the web console.

**Crash detection does not use the EMA filter** — it reads the raw hardware
register, so it reacts to impacts at the sensor's full bandwidth.

**Polling latency:** up to `1000 / publish_rate` ms (default ~33 ms at 30 Hz).
Raise `publish_rate` to reduce latency (e.g. `50` → 20 ms).

**Threshold guidance:**

| Scenario | Typical peak G | Recommended threshold |
|---|---|---|
| Normal cornering/bumps | 0.5–1.5 G | — |
| Light collision | 5–15 G | `3.0` (default) |
| Hard wall impact at 2 m/s | ~20–40 G | `3.0` is fine |
| Rough track surface vibration | 1–3 G | Raise to `4.0`+ if false-triggering |

### Pickup Detection (`stop_on_pickup`)

Uses the **EMA-filtered** `accel_z` value in software.

When the car sits flat, `accel_z ≈ ±9.81 m/s²` (gravity). When picked up or
tilted, `accel_z` shifts toward 0 (free-fall) or swings wildly.

**Trigger condition:**

```
|accel_z - expected_z|  >  |expected_z| + (pickup_threshold_g × 9.81)
```

With defaults (`accel_z_gravity_target=+1`, `pickup_threshold_g=0.5`):
- `expected_z` = +9.81 m/s²
- Fires when `accel_z` falls below **−4.9 m/s²** or exceeds **+24.5 m/s²**

This means the car must deviate more than 1.5× gravity from its resting value,
which normal driving does not produce.

**EMA lag** is intentional here — pickup is a sustained event (someone lifting
the car) lasting hundreds of milliseconds, not a brief spike. The filter
suppresses vibration while still catching a genuine pickup.

**Tip:** If you get false positives during hard cornering, raise
`pickup_threshold_g` to `0.8` or `1.0`.

---

## Signal Processing

### Hardware: OSR4 Filter

`ACC_CONF` and `GYR_CONF` are set to `0x08` (OSR4 oversampling mode, 100 Hz ODR).
The BMI160 averages 4 raw samples internally before each output sample, halving
the noise floor with no latency penalty.

### Software: EMA Filter

An Exponential Moving Average filter is applied to all 6 axes before publishing
and before pickup detection:

```
filtered = alpha × current + (1 − alpha) × previous
```

| `filter_alpha` | Effect |
|---|---|
| `1.0` | Pass-through (no filtering) |
| `0.5` (default) | Moderate smoothing, ~6 samples to settle |
| `0.2` | Heavy smoothing, good for slow-changing data |
| `0.0` | Holds previous value (fully frozen) |

The crash detection check (`isHighGTriggered`) always bypasses the EMA filter
and reads the raw hardware interrupt register.

---

## Calibration

The node runs **Fast Offset Compensation (FOC)** at startup via the BMI160's
built-in hardware calibration engine. FOC measures bias offsets and stores them
in the sensor's internal offset registers — no software bias subtraction is
needed at runtime.

**Prerequisite:** The car must be **stationary and flat** when the node starts.
Moving the car during startup will produce incorrect calibration offsets.

**What FOC corrects:**
- Accelerometer X and Y bias (target: 0 g)
- Accelerometer Z bias (target: +1 g or −1 g, matching `accel_z_gravity_target`)
- Gyroscope X, Y, Z bias (target: 0 dps)

**Note on Z target:** The FOC hardware command operates in the raw sensor frame.
Because the BMI160 is mounted upside-down and the driver negates the Z axis,
the FOC Z target is the opposite of `accel_z_gravity_target`:
- `accel_z_gravity_target=+1` (upside-down, DeepRacer default) → FOC target = −1 g in sensor frame
- `accel_z_gravity_target=-1` (normal mount) → FOC target = +1 g in sensor frame

---

## Integration with deepracer\_launcher

Enable the IMU node from the system-level launcher:

```bash
ros2 launch deepracer_launcher deepracer_launcher.py \
    enable_imu:=true \
    imu_stop_on_pickup:=true \
    imu_stop_on_crash:=true \
    imu_crash_accel_threshold_g:=3.0 \
    imu_accel_z_gravity_target:=1 \
    imu_filter_alpha:=0.5
```

The `deepracer_launcher` passes these as parameters to the same `imu_node`
executable. `package.xml` for `deepracer_launcher` declares `<depend>imu_pkg</depend>`.

---

## Building and Testing

```bash
cd /workspaces/deepracer-custom-car

# Build
colcon build --packages-select imu_pkg --cmake-args -DCMAKE_BUILD_TYPE=Release

# Run tests (49 unit tests + 6 linter suites)
source install/setup.bash
colcon test --packages-select imu_pkg --event-handlers console_direct+
colcon test-result --packages-select imu_pkg --verbose
```

The `HW_PLATFORM` environment variable controls the default I2C bus:

| `HW_PLATFORM` | Default `bus_id` |
|---|---|
| `DR` | 7 |
| anything else | 1 |

---

## Package Structure

```
aws-deepracer-community-imu-pkg/
├── CMakeLists.txt
├── package.xml
├── README.md
├── include/
│   └── imu_pkg/
│       ├── bmi160.hpp          # BMI160 register map, commands, driver class declaration
│       ├── conversions.hpp     # Pure-math helpers (axis mapping, EMA, pickup detection)
│       └── imu_node.hpp        # ROS 2 node class declaration
├── src/
│   ├── bmi160.cpp              # BMI160 I2C driver implementation
│   └── imu_node.cpp            # ROS 2 node implementation
├── launch/
│   └── imu_pkg_launch.py       # Standalone launch file
└── test/
    └── test_conversions.cpp    # GTest unit tests for conversions.hpp (49 tests)
```
