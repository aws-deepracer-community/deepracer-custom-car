#include "diffdrive_motor_pkg/motor_manager.hpp"
#include "diffdrive_motor_pkg/motor_constants.hpp"
#include <rclcpp/rclcpp.hpp>
#include <algorithm>
#include <cmath>

namespace aws_deepracer_community_diffdrive_motor_pkg
{

MotorManager::MotorManager(rclcpp::Logger logger)
: logger_(logger), initialized_(false), hardware_ready_(false)
{
    // Initialize motor state
  current_state_.left_speed = 0.0f;
  current_state_.right_speed = 0.0f;
  current_state_.left_pwm = 0;    // 0% duty cycle (stopped)
  current_state_.right_pwm = 0;   // 0% duty cycle (stopped)
  current_state_.enabled = false;
}

MotorManager::MotorManager(const MotorConfig & config, rclcpp::Logger logger)
: config_(config), logger_(logger), initialized_(false), hardware_ready_(false)
{
    // Initialize motor state
  current_state_.left_speed = 0.0f;
  current_state_.right_speed = 0.0f;
  current_state_.left_pwm = 0;    // 0% duty cycle (stopped)
  current_state_.right_pwm = 0;   // 0% duty cycle (stopped)
  current_state_.enabled = false;
}

MotorManager::~MotorManager()
{
  if (initialized_ && hardware_ready_) {
    stopMotors();
  }
}

bool MotorManager::initialize()
{
  if (initialized_) {
    return hardware_ready_;
  }

    // Create 6 Servo objects for complete TB6612FNG motor control
  try {
      // Motor A (Left) PWM channels
    motor_a_pwm_ = std::make_unique<PWM::Servo>(config_.motor_a_pwm, logger_);
    motor_a_pwm_->setPeriod(MotorConstants::PWM_PERIOD_NS);
    motor_a_in1_ = std::make_unique<PWM::Servo>(config_.motor_a_in1, logger_);
    motor_a_in1_->setPeriod(MotorConstants::PWM_PERIOD_NS);
    motor_a_in2_ = std::make_unique<PWM::Servo>(config_.motor_a_in2, logger_);
    motor_a_in2_->setPeriod(MotorConstants::PWM_PERIOD_NS);

      // Motor B (Right) PWM channels
    motor_b_pwm_ = std::make_unique<PWM::Servo>(config_.motor_b_pwm, logger_);
    motor_b_pwm_->setPeriod(MotorConstants::PWM_PERIOD_NS);
    motor_b_in1_ = std::make_unique<PWM::Servo>(config_.motor_b_in1, logger_);
    motor_b_in1_->setPeriod(MotorConstants::PWM_PERIOD_NS);
    motor_b_in2_ = std::make_unique<PWM::Servo>(config_.motor_b_in2, logger_);
    motor_b_in2_->setPeriod(MotorConstants::PWM_PERIOD_NS);

    RCLCPP_INFO(logger_, "Successfully created 6 servo objects for TB6612FNG motor control");
  } catch (const std::exception & e) {
    RCLCPP_ERROR(logger_, "Failed to create servo objects: %s", e.what());
    return false;
  }

    // Initialize motor state
  current_state_ = MotorState{};
  current_state_.left_speed = 0.0f;
  current_state_.right_speed = 0.0f;
  current_state_.left_pwm = 0;    // 0% duty cycle (stopped)
  current_state_.right_pwm = 0;   // 0% duty cycle (stopped)
  current_state_.enabled = false;

    // Set initial motor directions to stop
  if (!setMotorDirection(0, MotorDirection::STOP) ||
    !setMotorDirection(1, MotorDirection::STOP))
  {
    RCLCPP_ERROR(logger_, "Failed to set initial motor directions");
    return false;
  }

  initialized_ = true;
  hardware_ready_ = true;

  RCLCPP_INFO(logger_, "Motor manager initialized successfully");
  return true;
}

bool MotorManager::setMotorSpeeds(float left_speed, float right_speed)
{
  if (!initialized_ || !hardware_ready_) {
    RCLCPP_WARN(logger_, "Motor manager not initialized or hardware not ready");
    return false;
  }

  if (!current_state_.enabled) {
    RCLCPP_WARN(rclcpp::get_logger("motor_manager"), "Motors are disabled");
    return false;
  }

    // Clamp speeds to valid range
  left_speed = std::max(-1.0f, std::min(1.0f, left_speed));
  right_speed = std::max(-1.0f, std::min(1.0f, right_speed));

    // Set individual motor speeds
  bool success = setMotorSpeed(0, left_speed) && setMotorSpeed(1, right_speed);

  if (success) {
    current_state_.left_speed = left_speed;
    current_state_.right_speed = right_speed;
    current_state_.left_pwm = speedToPwm(std::abs(left_speed));
    current_state_.right_pwm = speedToPwm(std::abs(right_speed));
  }

  return success;
}

bool MotorManager::stopMotors()
{
  if (!initialized_ || !hardware_ready_) {
    return false;
  }

    // Set both motors to stop using TB6612FNG control logic
  bool success = setMotorDirection(0, MotorDirection::STOP) &&
    setMotorDirection(1, MotorDirection::STOP);

  if (success) {
      // Set PWM duty cycle to 0 (stopped) and direction pins to LOW/LOW (stop)
    motor_a_pwm_->setDuty(0);
    motor_b_pwm_->setDuty(0);

    current_state_.left_speed = 0.0f;
    current_state_.right_speed = 0.0f;
    current_state_.left_pwm = 0;
    current_state_.right_pwm = 0;
  }

  return success;
}

bool MotorManager::setMotorsEnabled(bool enabled)
{
  if (!initialized_ || !hardware_ready_) {
    return false;
  }

  if (!enabled) {
      // Disable motors by stopping them
    stopMotors();
  }

  current_state_.enabled = enabled;
  RCLCPP_INFO(logger_, "Motors %s", enabled ? "enabled" : "disabled");
  return true;
}

MotorState MotorManager::getMotorState() const
{
  return current_state_;
}

bool MotorManager::updateConfig(const MotorConfig & config)
{
  config_ = config;

    // If already initialized, reinitialize with new config
  if (initialized_) {
    initialized_ = false;
    hardware_ready_ = false;
    return initialize();
  }

  return true;
}

const MotorConfig & MotorManager::getConfig() const
{
  return config_;
}

bool MotorManager::isReady() const
{
  return hardware_ready_;
}

bool MotorManager::setMotorSpeed(int motor, float speed)
{
  if (motor < 0 || motor > 1) {
    return false;
  }

    // Determine direction based on speed sign
  MotorDirection direction;
  if (speed > 0.0f) {
    direction = MotorDirection::FORWARD;
  } else if (speed < 0.0f) {
    direction = MotorDirection::REVERSE;
  } else {
    direction = MotorDirection::STOP;
  }

    // Set direction first
  if (!setMotorDirection(motor, direction)) {
    return false;
  }

    // Convert speed to PWM duty cycle (0-4095 for 12-bit PWM)
  int pwm_value = speedToPwm(std::abs(speed));

    // Select the appropriate motor PWM channel
  auto *motor_pwm = (motor == 0) ? motor_a_pwm_.get() : motor_b_pwm_.get();
  motor_pwm->setDuty(pwm_value);

  return true;
}

bool MotorManager::setMotorDirection(int motor, MotorDirection direction)
{
  if (motor < 0 || motor > 1) {
    return false;
  }

    // Select the appropriate direction control pins
  auto *motor_in1 = (motor == 0) ? motor_a_in1_.get() : motor_b_in1_.get();
  auto *motor_in2 = (motor == 0) ? motor_a_in2_.get() : motor_b_in2_.get();

    // TB6612FNG Truth Table (using nanosecond duty cycles):
    // IN1=H, IN2=L: Clockwise (CW)     -> duty=period, duty=0
    // IN1=L, IN2=H: Counter-clockwise (CCW) -> duty=0, duty=period
    // IN1=L, IN2=L: Stop               -> duty=0, duty=0
    // IN1=H, IN2=H: Short brake        -> duty=period, duty=period

  switch (direction) {
    case MotorDirection::FORWARD:
      motor_in1->setDuty(MotorConstants::PWM_HIGH_SIGNAL_NS); // HIGH
      motor_in2->setDuty(MotorConstants::PWM_LOW_SIGNAL_NS);  // LOW
      break;

    case MotorDirection::REVERSE:
      motor_in1->setDuty(MotorConstants::PWM_LOW_SIGNAL_NS);  // LOW
      motor_in2->setDuty(MotorConstants::PWM_HIGH_SIGNAL_NS); // HIGH
      break;

    case MotorDirection::STOP:
      motor_in1->setDuty(MotorConstants::PWM_LOW_SIGNAL_NS); // LOW
      motor_in2->setDuty(MotorConstants::PWM_LOW_SIGNAL_NS); // LOW
      break;

    case MotorDirection::BRAKE:
      motor_in1->setDuty(MotorConstants::PWM_HIGH_SIGNAL_NS); // HIGH
      motor_in2->setDuty(MotorConstants::PWM_HIGH_SIGNAL_NS); // HIGH
      break;

    default:
      return false;
  }

    // Log the direction change for debugging
  const char *direction_str = "UNKNOWN";
  switch (direction) {
    case MotorDirection::STOP:
      direction_str = "STOP";
      break;
    case MotorDirection::FORWARD:
      direction_str = "FORWARD";
      break;
    case MotorDirection::REVERSE:
      direction_str = "REVERSE";
      break;
    case MotorDirection::BRAKE:
      direction_str = "BRAKE";
      break;
  }

  RCLCPP_DEBUG(logger_, "Motor %d direction set to %s", motor, direction_str);
  return true;
}

int MotorManager::speedToPwm(float speed) const
{
    // Clamp speed to [0.0, 1.0] range
  speed = std::max(0.0f, std::min(1.0f, std::abs(speed)));

    // Convert normalized speed to nanosecond duty cycle
    // Using the PWM period constant from header
  int duty_cycle_ns = static_cast<int>(speed * MotorConstants::PWM_PERIOD_NS);

  return std::max(0, std::min(MotorConstants::PWM_PERIOD_NS, duty_cycle_ns));
}

} // namespace aws_deepracer_community_diffdrive_motor_pkg
