///////////////////////////////////////////////////////////////////////////////////
//   Copyright AWS DeepRacer Community. All Rights Reserved.                    //
//                                                                               //
//   Licensed under the Apache License, Version 2.0 (the "License").             //
//   You may not use this file except in compliance with the License.            //
//   You may obtain a copy of the License at                                     //
//                                                                               //
//       http://www.apache.org/licenses/LICENSE-2.0                              //
//                                                                               //
//   Unless required by applicable law or agreed to in writing, software         //
//   distributed under the License is distributed on an "AS IS" BASIS,           //
//   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.    //
//   See the License for the specific language governing permissions and         //
//   limitations under the License.                                              //
///////////////////////////////////////////////////////////////////////////////////

#ifndef IMU_PKG__CONVERSIONS_HPP_
#define IMU_PKG__CONVERSIONS_HPP_

/// @file conversions.hpp
/// Pure-math helpers for BMI160 data conversion.
/// No ROS2 or I2C dependencies — fully unit-testable in isolation.

#include <algorithm>
#include <cmath>
#include <cstdint>

namespace imu_pkg
{
namespace conversions
{

// -------------------------------------------------------------------------
// Physical constants
// -------------------------------------------------------------------------

/// Standard gravity (m/s²)
static constexpr double GRAVITY_MS2 = 9.80665;
/// Half the 16-bit signed range (2^15)
static constexpr float  FULL_SCALE_16BIT = 32768.0f;
/// BMI160 high-G threshold: 1 register LSB = 7.81 mg (datasheet table 22)
static constexpr float  HIGH_G_THRESH_LSB_PER_G = 1.0f / 0.00781f;

// -------------------------------------------------------------------------
// Scale factor computation
// -------------------------------------------------------------------------

/// Compute the accelerometer scale factor in m/s² per raw LSB.
/// @param accel_range_g  Full-scale range in G (2, 4, 8, or 16).
///                       Falls back to ±4G for unrecognised values.
inline float computeAccelScale(int accel_range_g)
{
  const float lsb_per_g = FULL_SCALE_16BIT / static_cast<float>(accel_range_g);
  return static_cast<float>(GRAVITY_MS2) / lsb_per_g;
}

/// Compute the gyroscope scale factor in rad/s per raw LSB.
/// @param gyro_range_dps  Full-scale range in dps (125, 250, 500, 1000, or 2000).
///                        Falls back to ±250 dps for unrecognised values.
inline float computeGyroScale(int gyro_range_dps)
{
  const float lsb_per_dps = FULL_SCALE_16BIT / static_cast<float>(gyro_range_dps);
  return (static_cast<float>(M_PI) / 180.0f) / lsb_per_dps;
}

// -------------------------------------------------------------------------
// Register encoding
// -------------------------------------------------------------------------

/// Encode a crash threshold in G as the BMI160 INT_LOWHIGH_3 register byte.
/// 1 LSB ≈ 7.81 mg; clamped to [0, 255].
inline uint8_t encodeHighGThreshold(float threshold_g)
{
  const float raw = threshold_g * HIGH_G_THRESH_LSB_PER_G;
  return static_cast<uint8_t>(std::min(255.0f, std::max(0.0f, raw)));
}

// -------------------------------------------------------------------------
// Axis mapping & scaling
// -------------------------------------------------------------------------

/// Result of applying the BMI160→vehicle-frame axis mapping.
struct MotionData
{
  float gyro_x;   ///< rad/s, vehicle frame
  float gyro_y;   ///< rad/s, vehicle frame
  float gyro_z;   ///< rad/s, vehicle frame
  float accel_x;  ///< m/s², vehicle frame
  float accel_y;  ///< m/s², vehicle frame
  float accel_z;  ///< m/s², vehicle frame
};

/// Convert raw BMI160 sensor readings to vehicle-frame physical units.
///
/// Axis mapping (mirrors reference Python node):
///   published X  ←  sensor Y
///   published Y  ←  sensor X
///   published Z  ←  -(sensor Z)   (Z inverted regardless of mount orientation;
///                                   calibration already corrects the bias offset)
///
/// @param raw_gx..raw_az  Raw int16 values from the BMI160 data registers.
/// @param accel_scale     m/s² per LSB (from computeAccelScale)
/// @param gyro_scale      rad/s per LSB (from computeGyroScale)
inline MotionData applyAxisMapping(
  int16_t raw_gx, int16_t raw_gy, int16_t raw_gz,
  int16_t raw_ax, int16_t raw_ay, int16_t raw_az,
  float accel_scale, float gyro_scale)
{
  MotionData out;
  out.gyro_x = static_cast<float>(raw_gy) * gyro_scale;
  out.gyro_y = -static_cast<float>(raw_gx) * gyro_scale;
  out.gyro_z = -static_cast<float>(raw_gz) * gyro_scale;

  out.accel_x = static_cast<float>(raw_ay) * accel_scale;
  out.accel_y = static_cast<float>(raw_ax) * accel_scale;
  out.accel_z = -static_cast<float>(raw_az) * accel_scale;
  return out;
}

// -------------------------------------------------------------------------
// Crash detection
// -------------------------------------------------------------------------

/// Return true when the total acceleration magnitude indicates a crash.
///
/// Uses the Euclidean magnitude of all three axes, so it is orientation-agnostic.
///   sqrt(x² + y² + z²) > threshold_ms2
///
/// @param accel_x/y/z_ms2    Measured accelerations in m/s² (vehicle frame)
/// @param crash_threshold_g  Threshold in G (converted internally to m/s²)
inline bool isCrashDetected(
  double accel_x_ms2,
  double accel_y_ms2,
  double accel_z_ms2,
  double crash_threshold_g)
{
  const double magnitude = std::sqrt(
    accel_x_ms2 * accel_x_ms2 +
    accel_y_ms2 * accel_y_ms2 +
    accel_z_ms2 * accel_z_ms2);
  return magnitude > crash_threshold_g * GRAVITY_MS2;
}

// -------------------------------------------------------------------------
// Pickup detection
// -------------------------------------------------------------------------

/// Return true when the IMU Z-axis reading suggests the car has been picked up.
///
/// A pickup is detected when the measured accel_z deviates from the expected
/// gravity value by more than threshold:
///   |accel_z - expected_z|  >  threshold_ms2
///
/// @param accel_z_ms2        Measured Z acceleration in m/s²
/// @param z_gravity_target   +1 for upside-down mount, -1 for normal mount
/// @param pickup_threshold_g Threshold in G (converted internally to m/s²)
inline bool isPickupDetected(
  double accel_z_ms2,
  int z_gravity_target,
  double pickup_threshold_g)
{
  const double expected_z = z_gravity_target * GRAVITY_MS2;
  const double threshold_ms2 = pickup_threshold_g * GRAVITY_MS2;
  return std::abs(accel_z_ms2 - expected_z) > threshold_ms2;
}

// -------------------------------------------------------------------------
// Software exponential moving average (EMA) filter
// -------------------------------------------------------------------------

/// Apply one step of an exponential moving average filter.
///
/// filtered = alpha * current + (1 - alpha) * previous
///
/// @param current   New raw sample.
/// @param previous  Previous filtered value.
/// @param alpha     Smoothing factor in (0, 1]. 1.0 = no filtering (pass-through);
///                  lower values give heavier smoothing but more lag.
inline float ema(float current, float previous, float alpha)
{
  return alpha * current + (1.0f - alpha) * previous;
}

}  // namespace conversions
}  // namespace imu_pkg

#endif  // IMU_PKG__CONVERSIONS_HPP_
