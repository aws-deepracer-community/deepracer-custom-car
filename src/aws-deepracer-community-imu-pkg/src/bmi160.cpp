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

#include "imu_pkg/bmi160.hpp"
#include "imu_pkg/conversions.hpp"

#include <fcntl.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include <linux/i2c.h>
#include <linux/i2c-dev.h>

#include <cerrno>
#include <cmath>
#include <cstring>
#include <stdexcept>
#include <thread>
#include <chrono>

namespace imu_pkg
{

// ----- Physical constants -----------------------------------------------

static constexpr float GRAVITY_MS2 = 9.80665f;
static constexpr float FULL_SCALE_16BIT = 32768.0f;  // 2^15

// Accelerometer: register value → full-scale G mapping (datasheet table 16)
static const AccelRangeEntry ACCEL_RANGES[] = {
  {2, 0x03, FULL_SCALE_16BIT / 2.0f},
  {4, 0x05, FULL_SCALE_16BIT / 4.0f},
  {8, 0x08, FULL_SCALE_16BIT / 8.0f},
  {16, 0x0C, FULL_SCALE_16BIT / 16.0f},
};

// Gyroscope: register value → full-scale dps mapping (datasheet table 17)
static const GyroRangeEntry GYRO_RANGES[] = {
  {125, 0x04, FULL_SCALE_16BIT / 125.0f},
  {250, 0x03, FULL_SCALE_16BIT / 250.0f},
  {500, 0x02, FULL_SCALE_16BIT / 500.0f},
  {1000, 0x01, FULL_SCALE_16BIT / 1000.0f},
  {2000, 0x00, FULL_SCALE_16BIT / 2000.0f},
};

// High-G threshold register: 1 LSB = 7.81 mg for all accel ranges (datasheet table 22)
static constexpr float HIGH_G_THRESH_LSB_PER_G = 1.0f / 0.00781f;

// ----- Constructor / Destructor -----------------------------------------

BMI160::BMI160(rclcpp::Logger logger)
: logger_(logger) {}

BMI160::~BMI160() {}

// ----- I2C helpers -------------------------------------------------------

int BMI160::openDevice(int bus_id, int address)
{
  char path[32];
  snprintf(path, sizeof(path), "/dev/i2c-%d", bus_id);

  int fd = open(path, O_RDWR);
  if (fd < 0) {
    RCLCPP_ERROR(logger_, "BMI160: cannot open %s: %s", path, strerror(errno));
    return -1;
  }
  if (ioctl(fd, I2C_SLAVE, address) < 0) {
    RCLCPP_ERROR(
      logger_, "BMI160: cannot set I2C slave 0x%02X on %s: %s",
      address, path, strerror(errno));
    close(fd);
    return -1;
  }
  return fd;
}

bool BMI160::writeRegister(int fd, uint8_t reg, uint8_t val)
{
  uint8_t buf[2] = {reg, val};
  if (write(fd, buf, 2) != 2) {
    RCLCPP_ERROR(
      logger_, "BMI160: write failed reg=0x%02X val=0x%02X: %s",
      reg, val, strerror(errno));
    return false;
  }
  return true;
}

int BMI160::readRegister(int fd, uint8_t reg)
{
  uint8_t buf = reg;
  if (write(fd, &buf, 1) != 1) {
    RCLCPP_ERROR(logger_, "BMI160: write (set reg 0x%02X) failed: %s", reg, strerror(errno));
    return -1;
  }
  uint8_t val = 0;
  if (read(fd, &val, 1) != 1) {
    RCLCPP_ERROR(logger_, "BMI160: read failed reg=0x%02X: %s", reg, strerror(errno));
    return -1;
  }
  return static_cast<int>(val);
}

bool BMI160::readRegisters(int fd, uint8_t reg, int len, uint8_t * buf)
{
  uint8_t r = reg;
  if (write(fd, &r, 1) != 1) {
    RCLCPP_ERROR(logger_, "BMI160: write (set reg 0x%02X) failed: %s", reg, strerror(errno));
    return false;
  }
  if (read(fd, buf, len) != len) {
    RCLCPP_ERROR(logger_, "BMI160: burst-read %d bytes from reg=0x%02X failed: %s",
      len, reg, strerror(errno));
    return false;
  }
  return true;
}

// ----- Public API --------------------------------------------------------

bool BMI160::init(int bus_id, int address)
{
  bus_id_ = bus_id;
  address_ = address;

  int fd = openDevice(bus_id_, address_);
  if (fd < 0) {
    return false;
  }

  // Verify chip ID
  int chip_id = readRegister(fd, Bmi160Reg::CHIP_ID);
  if (chip_id != 0xD1) {
    RCLCPP_ERROR(
      logger_, "BMI160: unexpected chip ID 0x%02X (expected 0xD1). "
      "Check wiring and I2C address.", chip_id);
    close(fd);
    return false;
  }

  // Power up accelerometer and gyroscope (each takes ~50 ms to settle)
  writeRegister(fd, Bmi160Reg::CMD, Bmi160Cmd::ACCEL_NORMAL);
  std::this_thread::sleep_for(std::chrono::milliseconds(80));
  writeRegister(fd, Bmi160Reg::CMD, Bmi160Cmd::GYRO_NORMAL);
  std::this_thread::sleep_for(std::chrono::milliseconds(80));

  close(fd);
  RCLCPP_INFO(logger_, "BMI160: chip ID verified (0xD1), powered up on bus %d addr 0x%02X",
    bus_id_, address_);
  return true;
}

void BMI160::configure(int accel_range_g, int gyro_range_dps)
{
  int fd = openDevice(bus_id_, address_);
  if (fd < 0) {return;}

  // --- Accelerometer ---
  uint8_t accel_range_reg = 0x05;  // default: ±4G
  for (const auto & entry : ACCEL_RANGES) {
    if (entry.g == accel_range_g) {
      accel_range_reg = entry.reg_val;
      break;
    }
  }
  // ACC_CONF: ODR 100 Hz (0x08) + normal bandwidth filter (0x20)
  writeRegister(fd, Bmi160Reg::ACC_CONF, 0x28);   // odr=100Hz, bwp=normal
  writeRegister(fd, Bmi160Reg::ACC_RANGE, accel_range_reg);
  accel_scale_ = conversions::computeAccelScale(accel_range_g);

  // --- Gyroscope ---
  uint8_t gyro_range_reg = 0x03;  // default: ±250 dps
  for (const auto & entry : GYRO_RANGES) {
    if (entry.dps == gyro_range_dps) {
      gyro_range_reg = entry.reg_val;
      break;
    }
  }
  // GYR_CONF: ODR 100 Hz + normal bandwidth
  writeRegister(fd, Bmi160Reg::GYR_CONF, 0x28);
  writeRegister(fd, Bmi160Reg::GYR_RANGE, gyro_range_reg);
  gyro_scale_ = conversions::computeGyroScale(gyro_range_dps);

  close(fd);
  RCLCPP_INFO(
    logger_, "BMI160: configured accel ±%dG (scale=%.6f m/s²/LSB), "
    "gyro ±%ddps (scale=%.8f rad/s/LSB)",
    accel_range_g, accel_scale_, gyro_range_dps, gyro_scale_);
}

void BMI160::calibrate(int z_gravity_target)
{
  int fd = openDevice(bus_id_, address_);
  if (fd < 0) {return;}

  // FOC_CONF register layout (datasheet section 2.12.3):
  //   bits [7:6] foc_acc_z  : 0b01 = calibrate to +1g, 0b10 = calibrate to -1g
  //   bits [5:4] foc_acc_y  : 0b00 = disabled (offset to 0g)
  //   bits [3:2] foc_acc_x  : 0b00 = disabled (offset to 0g)
  //   bit  [1]   foc_gyr_en : 1 = enable gyro FOC
  //
  // For X and Y: 0b01 = +0g target (same encoding), for Z: 0b01=+1g, 0b10=-1g
  // X offset to 0g = 0b01, Y offset to 0g = 0b01
  // Encoding for z: target=+1 → 0b01, target=-1 → 0b10

  uint8_t foc_acc_z = (z_gravity_target >= 0) ? 0x01 : 0x02;
  // foc_acc_x = 0b01 (0g), foc_acc_y = 0b01 (0g), foc_gyr_en = 1
  uint8_t foc_conf = static_cast<uint8_t>(
    (foc_acc_z << 6) | (0x01 << 4) | (0x01 << 2) | 0x02);

  writeRegister(fd, Bmi160Reg::FOC_CONF, foc_conf);
  // Trigger FOC
  writeRegister(fd, Bmi160Reg::CMD, Bmi160Cmd::START_FOC);
  // FOC completes in ~250 ms (datasheet)
  std::this_thread::sleep_for(std::chrono::milliseconds(300));

  // Enable offset compensation (OFFSET_6 bit 6 = acc_off_en, bit 7 = gyr_off_en)
  int cur = readRegister(fd, Bmi160Reg::OFFSET_6);
  if (cur >= 0) {
    writeRegister(fd, Bmi160Reg::OFFSET_6, static_cast<uint8_t>(cur) | 0xC0);
  }

  close(fd);
  RCLCPP_INFO(logger_, "BMI160: FOC calibration done (z target: %+dg)", z_gravity_target);
}

void BMI160::configureHighGInterrupt(float threshold_g)
{
  int fd = openDevice(bus_id_, address_);
  if (fd < 0) {return;}

  // INT_EN_1: bits [5:3] = high_g_en_x/y/z — enable for all three axes
  writeRegister(fd, Bmi160Reg::INT_EN_1, 0x38);

  // INT_LOWHIGH_2 (0x5E): high_g_dur — duration = 0 means 1 sample (immediate)
  writeRegister(fd, Bmi160Reg::INT_LOWHIGH_2, 0x00);

  // INT_LOWHIGH_3 (0x5F): high_g_thres — 1 LSB = 7.81 mg
  uint8_t thresh_reg = conversions::encodeHighGThreshold(threshold_g);
  writeRegister(fd, Bmi160Reg::INT_LOWHIGH_3, thresh_reg);

  // INT_LOWHIGH_4 (0x60): high_g_hyst — set to small value (1 LSB = 15.63 mg)
  writeRegister(fd, Bmi160Reg::INT_LOWHIGH_4, 0x03);

  close(fd);
  RCLCPP_INFO(
    logger_, "BMI160: high-G interrupt enabled, threshold=%.2fG (reg=0x%02X)",
    threshold_g, thresh_reg);
}

bool BMI160::readMotion6(
  int16_t & gx, int16_t & gy, int16_t & gz,
  int16_t & ax, int16_t & ay, int16_t & az)
{
  int fd = openDevice(bus_id_, address_);
  if (fd < 0) {return false;}

  // 12 bytes starting at DATA_GYR_X_L (0x0C):
  //   [0..1] GX, [2..3] GY, [4..5] GZ, [6..7] AX, [8..9] AY, [10..11] AZ
  uint8_t buf[12];
  bool ok = readRegisters(fd, Bmi160Reg::DATA_GYR_X_L, 12, buf);
  close(fd);

  if (!ok) {return false;}

  gx = static_cast<int16_t>((buf[1] << 8) | buf[0]);
  gy = static_cast<int16_t>((buf[3] << 8) | buf[2]);
  gz = static_cast<int16_t>((buf[5] << 8) | buf[4]);
  ax = static_cast<int16_t>((buf[7] << 8) | buf[6]);
  ay = static_cast<int16_t>((buf[9] << 8) | buf[8]);
  az = static_cast<int16_t>((buf[11] << 8) | buf[10]);
  return true;
}

bool BMI160::isHighGTriggered()
{
  int fd = openDevice(bus_id_, address_);
  if (fd < 0) {return false;}

  // INT_STATUS_1 (0x1D): bit 2 = high_g_int
  int status = readRegister(fd, Bmi160Reg::INT_STATUS_1);
  close(fd);

  if (status < 0) {return false;}
  return (static_cast<uint8_t>(status) & 0x04) != 0;
}

}  // namespace imu_pkg
