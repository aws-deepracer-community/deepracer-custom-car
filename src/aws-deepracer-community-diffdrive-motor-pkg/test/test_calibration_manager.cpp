#include <gtest/gtest.h>
#include "diffdrive_motor_pkg/calibration_manager.hpp"
#include "deepracer_interfaces_pkg/srv/get_calibration_srv.hpp"
#include "deepracer_interfaces_pkg/srv/set_calibration_srv.hpp"

using namespace aws_deepracer_community_diffdrive_motor_pkg;

/**
 * @brief Test fixture for CalibrationManager tests
 */
class CalibrationManagerTest : public ::testing::Test
{
protected:
  void SetUp() override
  {
    // Create a default configuration for testing
    DifferentialDriveConfig test_config;
    test_config.max_forward_speed = 1.0f;
    test_config.max_backward_speed = 1.0f;
    test_config.max_left_differential = 0.5f;
    test_config.max_right_differential = 0.5f;
    test_config.center_offset = 0.0f;
    test_config.motor_polarity = 1;

    calibration_manager_ = std::make_unique<CalibrationManager>("", test_config);
  }

  void TearDown() override
  {
    calibration_manager_.reset();
  }

  std::unique_ptr<CalibrationManager> calibration_manager_;
};

/**
 * @brief Test basic construction
 */
TEST_F(CalibrationManagerTest, Construction)
{
  EXPECT_NE(calibration_manager_, nullptr);
}

/**
 * @brief Test default calibration values
 */
TEST_F(CalibrationManagerTest, DefaultCalibrationValues)
{
  const auto & calibration_data = calibration_manager_->getCalibrationData();

  // Check that default differential drive values are reasonable
  EXPECT_GT(calibration_data.max_forward_speed, 0.0f);
  EXPECT_LE(calibration_data.max_forward_speed, 1.0f);
  EXPECT_GT(calibration_data.max_backward_speed, 0.0f);
  EXPECT_LE(calibration_data.max_backward_speed, 1.0f);
  EXPECT_GE(calibration_data.max_left_differential, 0.0f);
  EXPECT_LE(calibration_data.max_left_differential, 1.0f);
  EXPECT_GE(calibration_data.max_right_differential, 0.0f);
  EXPECT_LE(calibration_data.max_right_differential, 1.0f);
  EXPECT_GE(calibration_data.center_offset, -1.0f);
  EXPECT_LE(calibration_data.center_offset, 1.0f);
}

/**
 * @brief Test calibration service operations with cal_type support
 */
TEST_F(CalibrationManagerTest, CalibrationServiceHandlers)
{
  // Test motor (throttle) calibration - cal_type = 1
  auto set_motor_request = std::make_shared<deepracer_interfaces_pkg::srv::SetCalibrationSrv::Request>();
  auto set_motor_response = std::make_shared<deepracer_interfaces_pkg::srv::SetCalibrationSrv::Response>();

  set_motor_request->cal_type = 1; // Motor/throttle
  set_motor_request->min = -50;    // max_backward_speed = -50 / -100.0f = 0.5
  set_motor_request->mid = 0;      // Standard mid value for motor
  set_motor_request->max = 80;     // max_forward_speed = 80 / 100.0f = 0.8
  set_motor_request->polarity = -1; // Inverted motor polarity

  EXPECT_TRUE(calibration_manager_->handleSetCalibrationService(set_motor_request,
    set_motor_response));
  EXPECT_EQ(set_motor_response->error, 0);

  // Test servo (steering) calibration - cal_type = 0
  auto set_servo_request = std::make_shared<deepracer_interfaces_pkg::srv::SetCalibrationSrv::Request>();
  auto set_servo_response = std::make_shared<deepracer_interfaces_pkg::srv::SetCalibrationSrv::Response>();

  set_servo_request->cal_type = 0; // Servo/steering
  set_servo_request->min = -30;    // max_left_differential = -30 / -100.0f = 0.3
  set_servo_request->mid = 20;     // center_offset = 20 / 100.0f = 0.2
  set_servo_request->max = 60;     // max_right_differential = 60 / 100.0f = 0.6
  set_servo_request->polarity = 1; // Standard polarity

  EXPECT_TRUE(calibration_manager_->handleSetCalibrationService(set_servo_request,
    set_servo_response));
  EXPECT_EQ(set_servo_response->error, 0);

  // Test getting motor calibration back - should match exactly
  auto get_motor_request = std::make_shared<deepracer_interfaces_pkg::srv::GetCalibrationSrv::Request>();
  auto get_motor_response = std::make_shared<deepracer_interfaces_pkg::srv::GetCalibrationSrv::Response>();

  get_motor_request->cal_type = 1; // Motor/throttle
  EXPECT_TRUE(calibration_manager_->handleGetCalibrationService(get_motor_request,
    get_motor_response));
  EXPECT_EQ(get_motor_response->error, 0);
  EXPECT_EQ(get_motor_response->min, -50);    // Should match exactly
  EXPECT_EQ(get_motor_response->mid, 0);      // Standard mid value
  EXPECT_EQ(get_motor_response->max, 80);     // Should match exactly
  EXPECT_EQ(get_motor_response->polarity, -1); // Should match set polarity

  // Test getting servo calibration back - should match exactly
  auto get_servo_request = std::make_shared<deepracer_interfaces_pkg::srv::GetCalibrationSrv::Request>();
  auto get_servo_response = std::make_shared<deepracer_interfaces_pkg::srv::GetCalibrationSrv::Response>();

  get_servo_request->cal_type = 0; // Servo/steering
  EXPECT_TRUE(calibration_manager_->handleGetCalibrationService(get_servo_request,
    get_servo_response));
  EXPECT_EQ(get_servo_response->error, 0);
  EXPECT_EQ(get_servo_response->min, -30);    // Should match exactly
  EXPECT_EQ(get_servo_response->mid, 20);     // Should match exactly
  EXPECT_EQ(get_servo_response->max, 60);     // Should match exactly
  EXPECT_EQ(get_servo_response->polarity, 1); // Standard servo polarity

  // Verify that the actual DifferentialDriveConfig was updated correctly
  const DifferentialDriveConfig & cal_data = calibration_manager_->getCalibrationData();
  EXPECT_FLOAT_EQ(cal_data.max_forward_speed, 0.8f);
  EXPECT_FLOAT_EQ(cal_data.max_backward_speed, 0.5f);
  EXPECT_FLOAT_EQ(cal_data.center_offset, 0.2f);
  EXPECT_FLOAT_EQ(cal_data.max_left_differential, 0.3f);
  EXPECT_FLOAT_EQ(cal_data.max_right_differential, 0.6f);
  EXPECT_EQ(cal_data.motor_polarity, -1);

  // Test invalid cal_type
  auto invalid_request =
    std::make_shared<deepracer_interfaces_pkg::srv::GetCalibrationSrv::Request>();
  auto invalid_response = std::make_shared<deepracer_interfaces_pkg::srv::GetCalibrationSrv::Response>();

  invalid_request->cal_type = 99; // Invalid type
  EXPECT_FALSE(calibration_manager_->handleGetCalibrationService(invalid_request,
    invalid_response));
  EXPECT_EQ(invalid_response->error, 1);
}

int main(int argc, char **argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
