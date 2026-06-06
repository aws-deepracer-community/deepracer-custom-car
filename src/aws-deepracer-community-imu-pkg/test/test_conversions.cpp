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

#include <gtest/gtest.h>
#include <cmath>
#include <cstdint>
#include <limits>

#include "imu_pkg/conversions.hpp"
#include "imu_pkg/bmi160.hpp"   // for Bmi160Reg constants

using namespace imu_pkg::conversions;
using namespace imu_pkg;

// =========================================================================
// Scale factor computation
// =========================================================================

class AccelScaleTest : public ::testing::Test {};

/// Known good values derived from the BMI160 datasheet:
///   ±4G range → sensitivity = 8192 LSB/G → scale = 9.80665 / 8192
TEST_F(AccelScaleTest, FourGRange)
{
  const float scale = computeAccelScale(4);
  // 9.80665 / 8192 ≈ 0.001197 m/s²/LSB
  EXPECT_NEAR(scale, 9.80665f / 8192.0f, 1e-6f);
}

TEST_F(AccelScaleTest, TwoGRange)
{
  const float scale = computeAccelScale(2);
  EXPECT_NEAR(scale, 9.80665f / 16384.0f, 1e-6f);
}

TEST_F(AccelScaleTest, EightGRange)
{
  const float scale = computeAccelScale(8);
  EXPECT_NEAR(scale, 9.80665f / 4096.0f, 1e-6f);
}

TEST_F(AccelScaleTest, SixteenGRange)
{
  const float scale = computeAccelScale(16);
  EXPECT_NEAR(scale, 9.80665f / 2048.0f, 1e-6f);
}

/// Verify that at ±4G, a raw value of 8192 converts to ≈ 1G (9.80665 m/s²)
TEST_F(AccelScaleTest, OneGEquivalence)
{
  const float scale = computeAccelScale(4);
  const float one_g = 8192.0f * scale;
  EXPECT_NEAR(one_g, 9.80665f, 1e-4f);
}

// -------------------------------------------------------------------------

class GyroScaleTest : public ::testing::Test {};

/// Known good: ±250 dps → sensitivity = 131.072 LSB/(°/s)
///   scale = (π/180) / 131.072
TEST_F(GyroScaleTest, TwoFiftyDps)
{
  const float scale = computeGyroScale(250);
  EXPECT_NEAR(scale, (static_cast<float>(M_PI) / 180.0f) / (32768.0f / 250.0f), 1e-9f);
}

TEST_F(GyroScaleTest, OneTwentyFiveDps)
{
  const float scale = computeGyroScale(125);
  EXPECT_NEAR(scale, (static_cast<float>(M_PI) / 180.0f) / (32768.0f / 125.0f), 1e-9f);
}

TEST_F(GyroScaleTest, FiveHundredDps)
{
  const float scale = computeGyroScale(500);
  EXPECT_NEAR(scale, (static_cast<float>(M_PI) / 180.0f) / (32768.0f / 500.0f), 1e-9f);
}

/// 32768 LSB at ±250dps should equal 250 deg/s = 250×π/180 rad/s
TEST_F(GyroScaleTest, FullScaleEquivalence)
{
  const float scale = computeGyroScale(250);
  const float full_scale_rads = 32768.0f * scale;
  EXPECT_NEAR(full_scale_rads, 250.0f * static_cast<float>(M_PI) / 180.0f, 1e-3f);
}

// =========================================================================
// High-G threshold register encoding
// =========================================================================

class HighGThreshTest : public ::testing::Test {};

/// 3G → 3 / 0.00781 ≈ 384, but register is uint8 so must be clamped
TEST_F(HighGThreshTest, ThreeG)
{
  const uint8_t reg = encodeHighGThreshold(3.0f);
  // 3.0 / 0.00781 ≈ 384.2 → clamped to 255
  EXPECT_EQ(reg, 255u);
}

/// 1G → 1 / 0.00781 ≈ 128
TEST_F(HighGThreshTest, OneG)
{
  const uint8_t reg = encodeHighGThreshold(1.0f);
  EXPECT_EQ(reg, static_cast<uint8_t>(std::min(255.0f, 1.0f / 0.00781f)));
}

/// 0.5G → 0.5 / 0.00781 ≈ 64
TEST_F(HighGThreshTest, HalfG)
{
  const uint8_t reg = encodeHighGThreshold(0.5f);
  const uint8_t expected = static_cast<uint8_t>(std::min(255.0f, 0.5f / 0.00781f));
  EXPECT_EQ(reg, expected);
}

/// 0G should encode as register 0
TEST_F(HighGThreshTest, ZeroG)
{
  EXPECT_EQ(encodeHighGThreshold(0.0f), 0u);
}

/// Negative input should clamp to 0
TEST_F(HighGThreshTest, NegativeClampedToZero)
{
  EXPECT_EQ(encodeHighGThreshold(-1.0f), 0u);
}

/// Very large input clamps to 255
TEST_F(HighGThreshTest, LargeValueClampedTo255)
{
  EXPECT_EQ(encodeHighGThreshold(100.0f), 255u);
}

// =========================================================================
// Axis mapping
// =========================================================================

class AxisMappingTest : public ::testing::Test
{
protected:
  // Use ±4G accel and ±250dps gyro for all axis tests
  const float as = computeAccelScale(4);
  const float gs = computeGyroScale(250);
};

/// With raw_gy=X and all others zero, published gyro_x should be non-zero
/// and gyro_y/gyro_z should be zero (sensor Y → published X)
TEST_F(AxisMappingTest, GyroAxisSwapXY)
{
  const int16_t raw_val = 1000;
  auto d = applyAxisMapping(0, raw_val, 0, 0, 0, 0, as, gs);
  EXPECT_NEAR(d.gyro_x, raw_val * gs, 1e-7f);
  EXPECT_NEAR(d.gyro_y, 0.0f, 1e-7f);
  EXPECT_NEAR(d.gyro_z, 0.0f, 1e-7f);
}

TEST_F(AxisMappingTest, GyroAxisSwapYX)
{
  const int16_t raw_val = 1000;
  auto d = applyAxisMapping(raw_val, 0, 0, 0, 0, 0, as, gs);
  EXPECT_NEAR(d.gyro_x, 0.0f, 1e-7f);
  EXPECT_NEAR(d.gyro_y, -raw_val * gs, 1e-7f);  // sensor X → -gyro_y (negated)
  EXPECT_NEAR(d.gyro_z, 0.0f, 1e-7f);
}

/// Sensor Z is negated: raw_gz positive → gyro_z negative
TEST_F(AxisMappingTest, GyroZInverted)
{
  const int16_t raw_val = 500;
  auto d = applyAxisMapping(0, 0, raw_val, 0, 0, 0, as, gs);
  EXPECT_NEAR(d.gyro_z, -raw_val * gs, 1e-7f);
}

/// Sensor accel_Y (raw_ay) → published accel_x
TEST_F(AxisMappingTest, AccelAxisSwapXY)
{
  const int16_t raw_val = 2000;
  auto d = applyAxisMapping(0, 0, 0, 0, raw_val, 0, as, gs);
  EXPECT_NEAR(d.accel_x, raw_val * as, 1e-6f);
  EXPECT_NEAR(d.accel_y, 0.0f, 1e-6f);
  EXPECT_NEAR(d.accel_z, 0.0f, 1e-6f);
}

/// Sensor accel_X (raw_ax) → published accel_y
TEST_F(AxisMappingTest, AccelAxisSwapYX)
{
  const int16_t raw_val = 2000;
  auto d = applyAxisMapping(0, 0, 0, raw_val, 0, 0, as, gs);
  EXPECT_NEAR(d.accel_x, 0.0f, 1e-6f);
  EXPECT_NEAR(d.accel_y, raw_val * as, 1e-6f);
  EXPECT_NEAR(d.accel_z, 0.0f, 1e-6f);
}

/// Sensor accel_Z is negated
TEST_F(AxisMappingTest, AccelZInverted)
{
  const int16_t raw_val = 8192;  // ~1G at ±4G
  auto d = applyAxisMapping(0, 0, 0, 0, 0, raw_val, as, gs);
  EXPECT_NEAR(d.accel_z, -raw_val * as, 1e-6f);
}

/// At ±4G range, raw value of ±8192 on accel_y (→ published accel_y) ≈ ±1G
TEST_F(AxisMappingTest, AccelOneGEquivalence)
{
  const int16_t raw_val = 8192;
  auto d = applyAxisMapping(0, 0, 0, raw_val, 0, 0, as, gs);
  EXPECT_NEAR(std::abs(d.accel_y), 9.80665f, 0.01f);
}

/// At ±250dps, raw value of 32767 on gyro_y (→ published gyro_x) ≈ 250 dps in rad/s
TEST_F(AxisMappingTest, GyroFullScaleEquivalence)
{
  const int16_t raw_val = 32767;
  auto d = applyAxisMapping(0, raw_val, 0, 0, 0, 0, as, gs);
  const float expected_rads = 250.0f * static_cast<float>(M_PI) / 180.0f;
  EXPECT_NEAR(d.gyro_x, expected_rads, 0.01f);
}

/// All zeros → all zeros
TEST_F(AxisMappingTest, AllZeroInput)
{
  auto d = applyAxisMapping(0, 0, 0, 0, 0, 0, as, gs);
  EXPECT_FLOAT_EQ(d.gyro_x, 0.0f);
  EXPECT_FLOAT_EQ(d.gyro_y, 0.0f);
  EXPECT_FLOAT_EQ(d.gyro_z, 0.0f);
  EXPECT_FLOAT_EQ(d.accel_x, 0.0f);
  EXPECT_FLOAT_EQ(d.accel_y, 0.0f);
  EXPECT_FLOAT_EQ(d.accel_z, 0.0f);
}

// =========================================================================
// Pickup detection
// =========================================================================

class PickupDetectionTest : public ::testing::Test {};

/// Normal-mount car resting flat: Z ≈ -9.8 m/s², z_target=-1, threshold=0.5G
/// → NOT a pickup (deviation is zero)
TEST_F(PickupDetectionTest, FlatGroundNormalMount_NotPickup)
{
  EXPECT_FALSE(isPickupDetected(-9.80665, -1, 0.5));
}

/// Upside-down mount car resting flat: Z ≈ +9.8 m/s², z_target=+1
TEST_F(PickupDetectionTest, FlatGroundInvertedMount_NotPickup)
{
  EXPECT_FALSE(isPickupDetected(9.80665, 1, 0.5));
}

/// Car picked up, IMU measuring ~0 on Z (gravity gone): normal mount, z_target=-1
/// Deviation = |0 - (-9.80665)| = 9.80665 > 0.1 × 9.80665 = 0.98 → True
TEST_F(PickupDetectionTest, CarLifted_ZeroAccel_NormalMount_SmallThreshold)
{
  // threshold_g = 0.1 → threshold_ms2 = 0.1 × 9.80665 = 0.98
  // |0 - (-9.80665)| = 9.80665 > 0.98 → PICKUP triggered
  EXPECT_TRUE(isPickupDetected(0.0, -1, 0.1));
}

/// Car tilted sideways: accel_z ≈ 0 with larger threshold so detection triggers.
/// expected_z = -9.80665, deviation = 9.80665, limit = 9.80665 + threshold_ms2
/// Triggers when threshold_ms2 < 0, i.e. threshold_g < 0 — not valid.
/// Correct pickup scenario: car held at 90°, Z reads e.g. +5 m/s² (gravity on side)
/// deviation = |5 - (-9.8)| = 14.8, limit = 9.8 + threshold.
/// With threshold_g=0.5 → limit=9.8+4.9=14.7, 14.8 > 14.7 → PICKUP
TEST_F(PickupDetectionTest, CarTilted90Deg_NormalMount_Triggered)
{
  // accel_z = +5 m/s² (tilted, gravity now on side)
  EXPECT_TRUE(isPickupDetected(5.0, -1, 0.5));
}

/// Flipped upside-down from normal mount: accel_z goes from -9.8 to +9.8
/// deviation = |9.8 - (-9.8)| = 19.6, limit = 9.8 + 4.9 = 14.7 → PICKUP
TEST_F(PickupDetectionTest, CarFlippedUpsideDown_NormalMount_Triggered)
{
  EXPECT_TRUE(isPickupDetected(9.80665, -1, 0.5));
}

/// Inverted mount car, tilted severely: accel_z goes from +9.8 to -5
/// deviation = |-5 - 9.8| = 14.8, limit = 9.8 + 4.9 = 14.7 → PICKUP
TEST_F(PickupDetectionTest, CarTilted_InvertedMount_Triggered)
{
  EXPECT_TRUE(isPickupDetected(-5.0, 1, 0.5));
}

/// Small vibration on normal mount should NOT trigger
TEST_F(PickupDetectionTest, SmallVibration_NotPickup)
{
  // Z deviates only 0.3G from expected -1G
  EXPECT_FALSE(isPickupDetected(-9.80665 + 0.3 * 9.80665, -1, 0.5));
}

/// Threshold of zero: any deviation at all triggers
TEST_F(PickupDetectionTest, ZeroThreshold_SlightDeviationTriggers)
{
  // accel_z = -5 (moved from -9.8), deviation=4.8, threshold=0 → triggered
  EXPECT_TRUE(isPickupDetected(-5.0, -1, 0.0));
  // accel_z = +1.0, deviation=|1-(-9.8)|=10.8, threshold=0 → triggered
  EXPECT_TRUE(isPickupDetected(1.0, -1, 0.0));
}

// =========================================================================
// Register address constants (sanity checks against BMI160 datasheet)
// =========================================================================

class RegisterAddressTest : public ::testing::Test {};

TEST_F(RegisterAddressTest, ChipIdAddress) {
                                                    EXPECT_EQ(Bmi160Reg::CHIP_ID, 0x00u);
}
TEST_F(RegisterAddressTest, DataStartAddress) {
                                                     EXPECT_EQ(Bmi160Reg::DATA_GYR_X_L, 0x0Cu);
}
TEST_F(RegisterAddressTest, IntStatus1Address) {
                                                     EXPECT_EQ(Bmi160Reg::INT_STATUS_1, 0x1Du);
}
TEST_F(RegisterAddressTest, AccConfAddress) {
                                                     EXPECT_EQ(Bmi160Reg::ACC_CONF, 0x40u);
}
TEST_F(RegisterAddressTest, AccRangeAddress) {
                                                     EXPECT_EQ(Bmi160Reg::ACC_RANGE, 0x41u);
}
TEST_F(RegisterAddressTest, GyrConfAddress) {
                                                     EXPECT_EQ(Bmi160Reg::GYR_CONF, 0x42u);
}
TEST_F(RegisterAddressTest, GyrRangeAddress) {
                                                     EXPECT_EQ(Bmi160Reg::GYR_RANGE, 0x43u);
}
TEST_F(RegisterAddressTest, FocConfAddress) {
                                                     EXPECT_EQ(Bmi160Reg::FOC_CONF, 0x69u);
}
TEST_F(RegisterAddressTest, Offset6Address) {
                                                     EXPECT_EQ(Bmi160Reg::OFFSET_6, 0x77u);
}
TEST_F(RegisterAddressTest, CmdAddress) {
                                                     EXPECT_EQ(Bmi160Reg::CMD, 0x7Eu);
}
TEST_F(RegisterAddressTest, IntLowHigh2Address) {
                                                     EXPECT_EQ(Bmi160Reg::INT_LOWHIGH_2, 0x5Eu);
}
TEST_F(RegisterAddressTest, IntLowHigh3Address) {
                                                     EXPECT_EQ(Bmi160Reg::INT_LOWHIGH_3, 0x5Fu);
}

// =========================================================================
// EMA filter
// =========================================================================

class EmaFilterTest : public ::testing::Test {};

/// alpha=1.0 is pass-through
TEST_F(EmaFilterTest, AlphaOneIsPassThrough)
{
  EXPECT_FLOAT_EQ(conversions::ema(5.0f, 100.0f, 1.0f), 5.0f);
}

/// alpha=0.0 holds previous value
TEST_F(EmaFilterTest, AlphaZeroHoldsPrevious)
{
  EXPECT_FLOAT_EQ(conversions::ema(5.0f, 100.0f, 0.0f), 100.0f);
}

/// alpha=0.5: output is midpoint of current and previous
TEST_F(EmaFilterTest, AlphaHalfIsMidpoint)
{
  EXPECT_FLOAT_EQ(conversions::ema(0.0f, 10.0f, 0.5f), 5.0f);
}

/// Starting from 0, a constant input of 1.0 converges toward 1.0
TEST_F(EmaFilterTest, ConvergesOverTime)
{
  float val = 0.0f;
  for (int i = 0; i < 100; ++i) {
    val = conversions::ema(1.0f, val, 0.3f);
  }
  EXPECT_NEAR(val, 1.0f, 0.001f);
}

/// Filter output is always bounded by current and previous values
TEST_F(EmaFilterTest, OutputBoundedByInputs)
{
  const float result = conversions::ema(3.0f, 7.0f, 0.4f);
  EXPECT_GE(result, 3.0f);
  EXPECT_LE(result, 7.0f);
}
