#ifndef DIFFDRIVE_MOTOR_PKG__MOTOR_CONSTANTS_HPP_
#define DIFFDRIVE_MOTOR_PKG__MOTOR_CONSTANTS_HPP_

namespace aws_deepracer_community_diffdrive_motor_pkg
{

  // Default motor configuration constants
namespace MotorConstants
{
    // Differential drive parameters
constexpr double DEFAULT_MAX_FORWARD_SPEED = 1.0;
constexpr double DEFAULT_MAX_BACKWARD_SPEED = 1.0;
constexpr double DEFAULT_MAX_LEFT_DIFFERENTIAL = 0.5;
constexpr double DEFAULT_MAX_RIGHT_DIFFERENTIAL = 0.5;
constexpr double DEFAULT_CENTER_OFFSET = 0.0;
constexpr int DEFAULT_MOTOR_POLARITY = 1;      // Default to normal polarity

    // TB6612FNG Motor Driver A (Left Motor) - PWM channels
constexpr int DEFAULT_MOTOR_A_PWM = 0;     // PWM speed control
constexpr int DEFAULT_MOTOR_A_IN1 = 2;     // Direction control 1
constexpr int DEFAULT_MOTOR_A_IN2 = 1;     // Direction control 2

    // TB6612FNG Motor Driver B (Right Motor) - PWM channels
constexpr int DEFAULT_MOTOR_B_PWM = 5;     // PWM speed control
constexpr int DEFAULT_MOTOR_B_IN1 = 3;     // Direction control 1
constexpr int DEFAULT_MOTOR_B_IN2 = 4;     // Direction control 2

    // PWM timing configuration (nanoseconds)
constexpr int PWM_PERIOD_NS = 655360;         // 16 kHz period in nanoseconds
constexpr int PWM_HIGH_SIGNAL_NS = PWM_PERIOD_NS;      // 100% duty cycle for HIGH
constexpr int PWM_LOW_SIGNAL_NS = 0;         // 0% duty cycle for LOW

}

} // namespace aws_deepracer_community_diffdrive_motor_pkg

#endif // DIFFDRIVE_MOTOR_PKG__MOTOR_CONSTANTS_HPP_
