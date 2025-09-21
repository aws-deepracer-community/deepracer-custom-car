#include "diffdrive_motor_pkg/differential_drive_controller.hpp"

namespace aws_deepracer_community_diffdrive_motor_pkg
{

DifferentialDriveController::DifferentialDriveController(const DifferentialDriveConfig & config)
: config_(config)
{
  // Validate configuration parameters
  config_.max_forward_speed = clamp(config_.max_forward_speed, 0.0f, 1.0f);
  config_.max_backward_speed = clamp(config_.max_backward_speed, 0.0f, 1.0f);
  config_.max_left_differential = clamp(config_.max_left_differential, 0.0f, 1.0f);
  config_.max_right_differential = clamp(config_.max_right_differential, 0.0f, 1.0f);
  config_.center_offset = clamp(config_.center_offset, -1.0f, 1.0f);
  config_.motor_polarity = (config_.motor_polarity == -1) ? -1 : 1;   // Ensure valid polarity
}

MotorSpeeds DifferentialDriveController::convertServoToMotorSpeeds(float angle, float throttle)
{
  // Validate inputs
  if (!validateInputs(angle, throttle)) {
    return MotorSpeeds{0.0f, 0.0f};
  }

  // Clamp inputs to valid range
  angle = clamp(angle, -1.0f, 1.0f);
  throttle = clamp(throttle, -1.0f, 1.0f);

  // If throttle is zero, both motors should stop regardless of steering
  if (std::abs(throttle) < 1e-6f) {
    return MotorSpeeds{0.0f, 0.0f};
  }

  // Determine maximum speed based on direction
  float max_speed = (throttle > 0) ? config_.max_forward_speed : config_.max_backward_speed;

  // Determine which wheel is outer/inner based on steering direction
  // angle > 0 means turn left (right wheel is outer, left wheel is inner)
  // angle < 0 means turn right (left wheel is outer, right wheel is inner)

  float left_speed, right_speed, max_differential;

  if (angle > 0) {
    max_differential = config_.max_left_differential;
  } else if (angle < 0) {
    max_differential = config_.max_right_differential;
  } else {
    max_differential = 0.0f;
  }

  right_speed = throttle * max_speed * (1.0f - config_.center_offset) *
    (1.0f + max_differential * angle / 2.0f);
  left_speed = throttle * max_speed * (1.0f + config_.center_offset) *
    (1.0f - max_differential * angle / 2.0f);

  // Apply motor inversion and return
  MotorSpeeds speeds{left_speed, right_speed};
  return applyMotorInversion(speeds);
}

bool DifferentialDriveController::validateInputs(float angle, float throttle) const
{
  // Check for NaN or infinite values
  if (std::isnan(angle) || std::isnan(throttle) ||
    std::isinf(angle) || std::isinf(throttle))
  {
    return false;
  }

  // Check if values are within reasonable range (allow some tolerance)
  const float max_range = 1.01f;   // Allow slightly beyond [-1,1] for tolerance
  if (std::abs(angle) > max_range || std::abs(throttle) > max_range) {
    return false;
  }

  return true;
}

void DifferentialDriveController::updateConfig(const DifferentialDriveConfig & config)
{
  // Update configuration with validation
  config_.max_forward_speed = clamp(config.max_forward_speed, 0.0f, 1.0f);
  config_.max_backward_speed = clamp(config.max_backward_speed, 0.0f, 1.0f);
  config_.max_left_differential = clamp(config.max_left_differential, 0.0f, 1.0f);
  config_.max_right_differential = clamp(config.max_right_differential, 0.0f, 1.0f);
  config_.center_offset = clamp(config.center_offset, -1.0f, 1.0f);
  config_.motor_polarity = (config.motor_polarity == -1) ? -1 : 1;   // Ensure valid polarity
}

const DifferentialDriveConfig & DifferentialDriveController::getConfig() const
{
  return config_;
}

float DifferentialDriveController::clamp(float value, float min_val, float max_val) const
{
  return std::max(min_val, std::min(value, max_val));
}

MotorSpeeds DifferentialDriveController::applyMotorInversion(const MotorSpeeds & speeds) const
{
  MotorSpeeds adjusted_speeds;
  // Apply motor polarity to both motors (-1 inverts both, 1 keeps normal)
  adjusted_speeds.left_speed = speeds.left_speed * config_.motor_polarity;
  adjusted_speeds.right_speed = speeds.right_speed * config_.motor_polarity;
  return adjusted_speeds;
}

} // namespace aws_deepracer_community_diffdrive_motor_pkg
