#include <gtest/gtest.h>
#include <limits>
#include "diffdrive_motor_pkg/differential_drive_controller.hpp"

using namespace aws_deepracer_community_diffdrive_motor_pkg;

/**
 * @brief Test fixture for DifferentialDriveController tests
 */
class DifferentialDriveControllerTest : public ::testing::Test
{
protected:
  void SetUp() override
  {
    // Create default configuration
    DifferentialDriveConfig config;
    config.max_forward_speed = 1.0;
    config.max_backward_speed = 1.0;
    config.max_left_differential = 0.5;
    config.max_right_differential = 0.5;
    config.center_offset = 0.0;
    config.motor_polarity = 1;

    controller_ = std::make_unique<DifferentialDriveController>(config);
  }

  void TearDown() override
  {
    controller_.reset();
  }

  std::unique_ptr<DifferentialDriveController> controller_;
};

/**
 * @brief Test basic construction and initialization
 */
TEST_F(DifferentialDriveControllerTest, Construction)
{
  EXPECT_NE(controller_, nullptr);
}

/**
 * @brief Test input validation
 */
TEST_F(DifferentialDriveControllerTest, InputValidation)
{
  // Valid inputs
  EXPECT_TRUE(controller_->validateInputs(0.0f, 0.0f));
  EXPECT_TRUE(controller_->validateInputs(-1.0f, 1.0f));
  EXPECT_TRUE(controller_->validateInputs(1.0f, -1.0f));

  // Invalid inputs (out of range)
  EXPECT_FALSE(controller_->validateInputs(-2.1f, 0.0f));
  EXPECT_FALSE(controller_->validateInputs(2.1f, 0.0f));
  EXPECT_FALSE(controller_->validateInputs(0.0f, -2.1f));
  EXPECT_FALSE(controller_->validateInputs(0.0f, 2.1f));

  // Invalid inputs (NaN and infinity)
  EXPECT_FALSE(controller_->validateInputs(std::numeric_limits<float>::quiet_NaN(), 0.0f));
  EXPECT_FALSE(controller_->validateInputs(0.0f, std::numeric_limits<float>::quiet_NaN()));
  EXPECT_FALSE(controller_->validateInputs(std::numeric_limits<float>::infinity(), 0.0f));
  EXPECT_FALSE(controller_->validateInputs(0.0f, std::numeric_limits<float>::infinity()));
}

/**
 * @brief Test straight line driving (angle = 0)
 */
TEST_F(DifferentialDriveControllerTest, StraightLineDriving)
{
  auto speeds = controller_->convertServoToMotorSpeeds(0.0f, 0.5f);

  // Both motors should have same speed for straight driving
  EXPECT_FLOAT_EQ(speeds.left_speed, speeds.right_speed);
  EXPECT_FLOAT_EQ(speeds.left_speed, 0.5f);
}

/**
 * @brief Test stopping (throttle = 0)
 */
TEST_F(DifferentialDriveControllerTest, Stopping)
{
  auto speeds = controller_->convertServoToMotorSpeeds(0.5f, 0.0f);

  // Both motors should be stopped regardless of angle
  EXPECT_FLOAT_EQ(speeds.left_speed, 0.0f);
  EXPECT_FLOAT_EQ(speeds.right_speed, 0.0f);
}

/**
 * @brief Test right turn (positive angle)
 */
TEST_F(DifferentialDriveControllerTest, RightTurn)
{
  auto speeds = controller_->convertServoToMotorSpeeds(0.5f, 0.5f);

  // Left motor should be faster than right for right turn
  EXPECT_GT(speeds.left_speed, speeds.right_speed);
}

/**
 * @brief Test left turn (negative angle)
 */
TEST_F(DifferentialDriveControllerTest, LeftTurn)
{
  auto speeds = controller_->convertServoToMotorSpeeds(-0.5f, 0.5f);

  // Right motor should be faster than left for left turn
  EXPECT_GT(speeds.right_speed, speeds.left_speed);
}

/**
 * @brief Test new algorithm: outer wheel at commanded speed, inner wheel reduced
 */
TEST_F(DifferentialDriveControllerTest, NewAlgorithmRightTurn)
{
  // Test with custom config to verify algorithm
  DifferentialDriveConfig config;
  config.max_forward_speed = 1.0f;
  config.max_backward_speed = 0.7f;
  config.max_left_differential = 1.0f;
  config.max_right_differential = 0.5f;
  config.center_offset = 0.0f;
  config.motor_polarity = 1;
  auto custom_controller = std::make_unique<DifferentialDriveController>(config);

  // Right turn: left wheel is outer (full speed), right wheel is inner (reduced)
  auto speeds = custom_controller->convertServoToMotorSpeeds(0.5f, 0.8f);

  // Left wheel (outer) should be at commanded speed * max_forward_speed
  EXPECT_FLOAT_EQ(speeds.left_speed, 0.8f * 1.0f);

  // Right wheel (inner) should be reduced by differential factor
  // inner_speed = commanded * max_speed * (1 - max_differential * steering)
  // = 0.8 * 1.0 * (1 - 0.5 * 0.5) = 0.8 * 0.75 = 0.6
  EXPECT_FLOAT_EQ(speeds.right_speed, 0.6f);
}

/**
 * @brief Test new algorithm with left turn
 */
TEST_F(DifferentialDriveControllerTest, NewAlgorithmLeftTurn)
{
  DifferentialDriveConfig config;
  config.max_forward_speed = 1.0f;
  config.max_backward_speed = 0.7f;
  config.max_left_differential = 0.4f;
  config.max_right_differential = 1.0f;
  config.center_offset = 0.0f;
  config.motor_polarity = 1;
  auto custom_controller = std::make_unique<DifferentialDriveController>(config);

  // Left turn: right wheel is outer (full speed), left wheel is inner (reduced)
  auto speeds = custom_controller->convertServoToMotorSpeeds(-0.6f, 0.7f);

  // Right wheel (outer) should be at commanded speed * max_forward_speed
  EXPECT_FLOAT_EQ(speeds.right_speed, 0.7f * 1.0f);

  // Left wheel (inner) should be reduced by differential factor
  // inner_speed = commanded * max_speed * (1 - max_differential * abs(steering))
  // = 0.7 * 1.0 * (1 - 0.4 * 0.6) = 0.7 * 0.76 = 0.532
  EXPECT_NEAR(speeds.left_speed, 0.532f, 0.001f);
}

/**
 * @brief Test center offset functionality
 */
TEST_F(DifferentialDriveControllerTest, CenterOffset)
{
  DifferentialDriveConfig config;
  config.max_forward_speed = 1.0f;
  config.max_backward_speed = 0.7f;
  config.max_left_differential = 1.0f;
  config.max_right_differential = 1.0f;
  config.center_offset = 0.2f;  // Offset to the right
  config.motor_polarity = 1;
  auto custom_controller = std::make_unique<DifferentialDriveController>(config);

  // Test straight line driving with center offset
  auto speeds = custom_controller->convertServoToMotorSpeeds(0.0f, 1.0f);

  // With positive center offset, right wheel should be faster (causing left bias)
  EXPECT_GT(speeds.right_speed, speeds.left_speed);
}

/**
 * @brief Test backward motion with different max speeds
 */
TEST_F(DifferentialDriveControllerTest, BackwardMotionDifferentSpeeds)
{
  DifferentialDriveConfig config;
  config.max_forward_speed = 1.0f;
  config.max_backward_speed = 0.7f;  // Slower backward speed
  config.max_left_differential = 1.0f;
  config.max_right_differential = 1.0f;
  config.center_offset = 0.0f;
  config.motor_polarity = 1;
  auto custom_controller = std::make_unique<DifferentialDriveController>(config);

  // Forward motion
  auto forward_speeds = custom_controller->convertServoToMotorSpeeds(0.0f, 0.8f);
  EXPECT_FLOAT_EQ(forward_speeds.left_speed, 0.8f);  // 0.8 * 1.0

  // Backward motion
  auto backward_speeds = custom_controller->convertServoToMotorSpeeds(0.0f, -0.8f);
  EXPECT_FLOAT_EQ(backward_speeds.left_speed, -0.56f);  // -0.8 * 0.7
}

int main(int argc, char **argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
