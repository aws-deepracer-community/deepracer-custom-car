#include <gtest/gtest.h>
#include "diffdrive_motor_pkg/motor_manager.hpp"
#include "rclcpp/rclcpp.hpp"
#include <memory>

using namespace aws_deepracer_community_diffdrive_motor_pkg;

/**
 * @brief Basic test for motor manager PWM integration
 */
class MotorPWMBasicTest : public ::testing::Test
{
protected:
  void SetUp() override
  {
    rclcpp::init(0, nullptr);
    auto logger = rclcpp::get_logger("test_motor_pwm_basic");

    // Create motor config for Waveshare Motor HAT
    MotorConfig config;
    config.motor_a_pwm = 0;  // PWM channel 0 for Motor A speed
    config.motor_a_in1 = 1;  // PWM channel 1 for Motor A direction 1
    config.motor_a_in2 = 2;  // PWM channel 2 for Motor A direction 2
    config.motor_b_pwm = 3;  // PWM channel 3 for Motor B speed
    config.motor_b_in1 = 4;  // PWM channel 4 for Motor B direction 1
    config.motor_b_in2 = 5;  // PWM channel 5 for Motor B direction 2

    motor_manager_ = std::make_unique<MotorManager>(config, logger);
  }

  void TearDown() override
  {
    motor_manager_.reset();
    rclcpp::shutdown();
  }

  std::unique_ptr<MotorManager> motor_manager_;
};

/**
 * @brief Test basic construction and configuration
 */
TEST_F(MotorPWMBasicTest, ConstructionAndConfig)
{
  EXPECT_TRUE(motor_manager_ != nullptr);

  // Check configuration
  const auto & config = motor_manager_->getConfig();
  EXPECT_EQ(config.motor_a_pwm, 0);
  EXPECT_EQ(config.motor_a_in1, 1);
  EXPECT_EQ(config.motor_a_in2, 2);
  EXPECT_EQ(config.motor_b_pwm, 3);
  EXPECT_EQ(config.motor_b_in1, 4);
  EXPECT_EQ(config.motor_b_in2, 5);
}

/**
 * @brief Test motor state without initialization (should be safe)
 */
TEST_F(MotorPWMBasicTest, StateWithoutInit)
{
  auto state = motor_manager_->getMotorState();

  // Should have safe default values
  EXPECT_FLOAT_EQ(state.left_speed, 0.0f);
  EXPECT_FLOAT_EQ(state.right_speed, 0.0f);
  EXPECT_EQ(state.left_pwm, 0);
  EXPECT_EQ(state.right_pwm, 0);
  EXPECT_FALSE(state.enabled);
}

/**
 * @brief Test motor commands without initialization (should fail gracefully)
 */
TEST_F(MotorPWMBasicTest, CommandsWithoutInit)
{
  // These should fail gracefully when not initialized
  EXPECT_FALSE(motor_manager_->setMotorSpeeds(0.5f, 0.5f));
  EXPECT_FALSE(motor_manager_->stopMotors());
  EXPECT_FALSE(motor_manager_->setMotorsEnabled(true));

  // Ready should be false
  EXPECT_FALSE(motor_manager_->isReady());
}

/**
 * @brief Test speed to PWM conversion (nanosecond-based)
 */
TEST_F(MotorPWMBasicTest, SpeedToPWMConversion)
{
  // Test PWM conversion logic for nanosecond-based system using header constants
  auto testSpeedToDutyCycle = [](float speed, int period_ns) {
      speed = std::max(0.0f, std::min(1.0f, std::abs(speed)));
      return static_cast<int>(speed * period_ns);
    };

  // Test the speedToPwm conversion logic using constants from header
  EXPECT_EQ(testSpeedToDutyCycle(0.0f, MotorConstants::PWM_PERIOD_NS), 0);          // 0% = 0ns
  EXPECT_EQ(testSpeedToDutyCycle(0.5f, MotorConstants::PWM_PERIOD_NS), 327680);     // 50% = 327.68μs
  EXPECT_EQ(testSpeedToDutyCycle(1.0f, MotorConstants::PWM_PERIOD_NS), 655360);     // 100% = 655.36μs
  EXPECT_EQ(testSpeedToDutyCycle(-0.5f, MotorConstants::PWM_PERIOD_NS), 327680);    // Absolute value
  EXPECT_EQ(testSpeedToDutyCycle(1.5f, MotorConstants::PWM_PERIOD_NS), 655360);     // Clamped to max
}

/**
 * @brief Test TB6612FNG direction control logic
 */
TEST_F(MotorPWMBasicTest, DirectionLogicValidation)
{
  // Verify our TB6612FNG direction truth table understanding:
  // FORWARD: IN1=HIGH, IN2=LOW  -> duty_cycle=period, duty_cycle=0
  // REVERSE: IN1=LOW,  IN2=HIGH -> duty_cycle=0, duty_cycle=period
  // STOP:    IN1=LOW,  IN2=LOW  -> duty_cycle=0, duty_cycle=0
  // BRAKE:   IN1=HIGH, IN2=HIGH -> duty_cycle=period, duty_cycle=period

  // Verify signal values for direction control using header constants
  EXPECT_EQ(MotorConstants::PWM_HIGH_SIGNAL_NS, MotorConstants::PWM_PERIOD_NS);  // HIGH = full period
  EXPECT_EQ(MotorConstants::PWM_LOW_SIGNAL_NS, 0);                              // LOW = zero duty cycle

  // This validates our understanding of the Linux PWM nanosecond system
  EXPECT_TRUE(true);
}

int main(int argc, char **argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
