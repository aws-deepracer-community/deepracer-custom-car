#include <gtest/gtest.h>
#include "diffdrive_motor_pkg/motor_manager.hpp"
#include "rclcpp/rclcpp.hpp"

using namespace aws_deepracer_community_diffdrive_motor_pkg;

/**
 * @brief Test fixture for MotorManager tests
 */
class MotorManagerTest : public ::testing::Test
{
protected:
  void SetUp() override
  {
    rclcpp::init(0, nullptr);
    auto logger = rclcpp::get_logger("test_motor_manager");
    motor_manager_ = std::make_unique<MotorManager>(logger);
  }

  void TearDown() override
  {
    motor_manager_.reset();
    rclcpp::shutdown();
  }

  std::unique_ptr<MotorManager> motor_manager_;
};

/**
 * @brief Test basic construction
 */
TEST_F(MotorManagerTest, Construction)
{
  EXPECT_NE(motor_manager_, nullptr);
}

/**
 * @brief Test configuration management
 */
TEST_F(MotorManagerTest, ConfigurationManagement)
{
  MotorConfig config;
  config.motor_a_pwm = 10;
  config.motor_b_pwm = 15;

  EXPECT_TRUE(motor_manager_->updateConfig(config));

  const auto & retrieved_config = motor_manager_->getConfig();
  EXPECT_EQ(retrieved_config.motor_a_pwm, 10);
  EXPECT_EQ(retrieved_config.motor_b_pwm, 15);
}

/**
 * @brief Test motor state management
 */
TEST_F(MotorManagerTest, MotorStateManagement)
{
  auto state = motor_manager_->getMotorState();

  // Initial state should be stopped
  EXPECT_FLOAT_EQ(state.left_speed, 0.0f);
  EXPECT_FLOAT_EQ(state.right_speed, 0.0f);
  EXPECT_FALSE(state.enabled);
}

int main(int argc, char **argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
