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

#ifndef IMU_PKG__BMI160_HPP_
#define IMU_PKG__BMI160_HPP_

#include <cstdint>
#include "rclcpp/rclcpp.hpp"

namespace imu_pkg
{

/// BMI160 register addresses (from datasheet BST-BMI160-DS000)
namespace Bmi160Reg
{
constexpr uint8_t CHIP_ID = 0x00;  ///< Expected value: 0xD1
constexpr uint8_t ERR_REG = 0x02;
constexpr uint8_t DATA_GYR_X_L = 0x0C;  ///< First of 12-byte motion data block
constexpr uint8_t INT_STATUS_1 = 0x1D;  ///< bit 2 = high_g_int (note: datasheet pg.46, reg 0x1D)
constexpr uint8_t ACC_CONF = 0x40;  ///< ODR and bandwidth
constexpr uint8_t ACC_RANGE = 0x41;  ///< +/-2/4/8/16 G
constexpr uint8_t GYR_CONF = 0x42;  ///< ODR and bandwidth
constexpr uint8_t GYR_RANGE = 0x43;  ///< +/-125..2000 dps
constexpr uint8_t INT_EN_1 = 0x51;  ///< Interrupt enable 1 (high-G)
constexpr uint8_t INT_MAP_1 = 0x56;  ///< Interrupt map (not used - polling only)
constexpr uint8_t INT_LOWHIGH_2 = 0x5E;  ///< High-G duration
constexpr uint8_t INT_LOWHIGH_3 = 0x5F;  ///< High-G threshold
constexpr uint8_t INT_LOWHIGH_4 = 0x60;  ///< High-G hysteresis
constexpr uint8_t FOC_CONF = 0x69;  ///< Fast Offset Compensation config
constexpr uint8_t OFFSET_6 = 0x77;  ///< Offset enable bits
constexpr uint8_t CMD = 0x7E;  ///< Command register
}

/// BMI160 commands
namespace Bmi160Cmd
{
constexpr uint8_t ACCEL_NORMAL = 0x11;  ///< Set accelerometer to normal power mode
constexpr uint8_t GYRO_NORMAL = 0x15;  ///< Set gyroscope to normal power mode
constexpr uint8_t START_FOC = 0x03;  ///< Start Fast Offset Compensation
}

/// BMI160 accelerometer range register values and corresponding full-scale G values
struct AccelRangeEntry
{
  int g;
  uint8_t reg_val;
  float lsb_per_g;  ///< LSB counts per 1 G at 16-bit full scale
};

/// BMI160 gyroscope range register values and corresponding full-scale dps values
struct GyroRangeEntry
{
  int dps;
  uint8_t reg_val;
  float lsb_per_dps;  ///< LSB counts per 1 deg/s at 16-bit full scale
};

/// Low-level BMI160 driver communicating via Linux I2C userspace (/dev/i2c-N).
///
/// Usage:
///   BMI160 imu(logger);
///   imu.init(bus_id, address);
///   imu.configure(4, 250);
///   imu.calibrate(-1);
///   int16_t gx, gy, gz, ax, ay, az;
///   imu.readMotion6(gx, gy, gz, ax, ay, az);
class BMI160
{
public:
  explicit BMI160(rclcpp::Logger logger);
  ~BMI160();

  /// Open the I2C device and verify chip ID (0xD1).
  /// @param bus_id  I2C bus number (e.g. 1 for /dev/i2c-1, 7 for /dev/i2c-7)
  /// @param address Slave address (default 0x68)
  /// @return true on success
  bool init(int bus_id, int address);

  /// Configure accelerometer and gyroscope ranges and ODR.
  /// @param accel_range_g  Full-scale accel range in G (2, 4, 8, or 16)
  /// @param gyro_range_dps Full-scale gyro range in dps (125, 250, 500, 1000, or 2000)
  void configure(int accel_range_g, int gyro_range_dps);

  /// Run Fast Offset Compensation to null out accel bias.
  /// Assumes the car is stationary on flat ground.
  /// @param z_gravity_target +1 for upside-down mounting, -1 for normal mounting
  void calibrate(int z_gravity_target);

  /// Enable the BMI160 hardware high-G interrupt detection circuitry.
  /// The node polls INT_STATUS_1 rather than reading the INT1 pin.
  /// @param threshold_g  Acceleration magnitude that triggers the interrupt (in G)
  void configureHighGInterrupt(float threshold_g);

  /// Burst-read all 6-DOF raw data from the BMI160.
  /// Register layout 0x0C–0x17: GX_L GX_H GY_L GY_H GZ_L GZ_H AX_L AX_H AY_L AY_H AZ_L AZ_H
  /// @return true on success
  bool readMotion6(
    int16_t & gx, int16_t & gy, int16_t & gz,
    int16_t & ax, int16_t & ay, int16_t & az);

  /// Check whether the hardware high-G interrupt is currently asserted.
  /// Reads INT_STATUS_1 (0x1D); bit 2 = high_g_int.
  bool isHighGTriggered();

  /// Physical scale factors (set by configure())
  float accel_scale() const {return accel_scale_;}     ///< m/s² per LSB
  float gyro_scale() const {return gyro_scale_;}       ///< rad/s per LSB

private:
  // I2C helpers
  int  openDevice(int bus_id, int address);
  bool writeRegister(int fd, uint8_t reg, uint8_t val);
  int  readRegister(int fd, uint8_t reg);
  bool readRegisters(int fd, uint8_t reg, int len, uint8_t * buf);

  rclcpp::Logger logger_;
  int bus_id_{1};
  int address_{0x68};
  float accel_scale_{0.0f};
  float gyro_scale_{0.0f};
};

}  // namespace imu_pkg

#endif  // IMU_PKG__BMI160_HPP_
