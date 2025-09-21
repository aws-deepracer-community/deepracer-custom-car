#ifndef DIFFDRIVE_MOTOR_PKG__DIFFERENTIAL_DRIVE_CONTROLLER_HPP_
#define DIFFDRIVE_MOTOR_PKG__DIFFERENTIAL_DRIVE_CONTROLLER_HPP_

#include <cmath>
#include <algorithm>
#include "diffdrive_motor_pkg/motor_constants.hpp"

namespace aws_deepracer_community_diffdrive_motor_pkg
{

  /**
   * @brief Configuration parameters for differential drive control
   */
struct DifferentialDriveConfig
{
  float max_forward_speed;
  float max_backward_speed;
  float max_left_differential;
  float max_right_differential;
  float center_offset;
  int motor_polarity;             // Motor polarity (-1 or 1) applied to both motors

  // Default constructor using constants from MotorConstants
  DifferentialDriveConfig()
  : max_forward_speed(MotorConstants::DEFAULT_MAX_FORWARD_SPEED),
    max_backward_speed(MotorConstants::DEFAULT_MAX_BACKWARD_SPEED),
    max_left_differential(MotorConstants::DEFAULT_MAX_LEFT_DIFFERENTIAL),
    max_right_differential(MotorConstants::DEFAULT_MAX_RIGHT_DIFFERENTIAL),
    center_offset(MotorConstants::DEFAULT_CENTER_OFFSET),
    motor_polarity(MotorConstants::DEFAULT_MOTOR_POLARITY)
  {
  }
};

  /**
   * @brief Motor speeds for left and right wheels
   */
struct MotorSpeeds
{
  float left_speed;    // Normalized speed [-1.0, 1.0]
  float right_speed;   // Normalized speed [-1.0, 1.0]
};

  /**
   * @brief Core differential drive controller
   *
   * Converts servo-style commands (angle + throttle) to differential drive
   * motor speeds (left + right) using differential drive kinematics.
   */
class DifferentialDriveController
{
public:
    /**
     * @brief Constructor with custom configuration
     * @param config Configuration parameters
     */
  explicit DifferentialDriveController(const DifferentialDriveConfig & config);

    /**
     * @brief Convert servo commands to motor speeds
     * @param angle Steering angle [-1.0, 1.0] (negative = left, positive = right)
     * @param throttle Throttle value [-1.0, 1.0] (negative = reverse, positive = forward)
     * @return Motor speeds for left and right wheels
     */
  MotorSpeeds convertServoToMotorSpeeds(float angle, float throttle);

    /**
     * @brief Validate input values are within acceptable ranges
     * @param angle Steering angle to validate
     * @param throttle Throttle value to validate
     * @return true if inputs are valid, false otherwise
     */
  bool validateInputs(float angle, float throttle) const;

    /**
     * @brief Update configuration parameters
     * @param config New configuration
     */
  void updateConfig(const DifferentialDriveConfig & config);

    /**
     * @brief Get current configuration
     * @return Current configuration
     */
  const DifferentialDriveConfig & getConfig() const;

private:
    /**
     * @brief Clamp value to specified range
     * @param value Value to clamp
     * @param min_val Minimum value
     * @param max_val Maximum value
     * @return Clamped value
     */
  float clamp(float value, float min_val, float max_val) const;

    /**
     * @brief Apply motor polarity adjustment if configured
     * @param speeds Motor speeds to adjust
     * @return Motor speeds with polarity applied
     */
  MotorSpeeds applyMotorInversion(const MotorSpeeds & speeds) const;

  DifferentialDriveConfig config_;
};

} // namespace aws_deepracer_community_diffdrive_motor_pkg

#endif // DIFFDRIVE_MOTOR_PKG__DIFFERENTIAL_DRIVE_CONTROLLER_HPP_
