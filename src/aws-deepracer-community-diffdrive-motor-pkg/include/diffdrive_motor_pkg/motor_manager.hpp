#ifndef DIFFDRIVE_MOTOR_PKG__MOTOR_MANAGER_HPP_
#define DIFFDRIVE_MOTOR_PKG__MOTOR_MANAGER_HPP_

#include <memory>
#include <string>

#include "rclcpp/rclcpp.hpp"
#include "diffdrive_motor_pkg/pwm.hpp"
#include "diffdrive_motor_pkg/motor_constants.hpp"

namespace aws_deepracer_community_diffdrive_motor_pkg
{

  /**
   * @brief Motor configuration for hardware mapping
   */
struct MotorConfig
{
    // Motor A (Left) configuration
  int motor_a_pwm;   // Motor A speed PWM channel
  int motor_a_in1;   // Motor A direction control 1
  int motor_a_in2;   // Motor A direction control 2

    // Motor B (Right) configuration
  int motor_b_pwm;   // Motor B speed PWM channel
  int motor_b_in1;   // Motor B direction control 1
  int motor_b_in2;   // Motor B direction control 2

    // Default constructor using constants
  MotorConfig()
  : motor_a_pwm(MotorConstants::DEFAULT_MOTOR_A_PWM),
    motor_a_in1(MotorConstants::DEFAULT_MOTOR_A_IN1),
    motor_a_in2(MotorConstants::DEFAULT_MOTOR_A_IN2),
    motor_b_pwm(MotorConstants::DEFAULT_MOTOR_B_PWM),
    motor_b_in1(MotorConstants::DEFAULT_MOTOR_B_IN1),
    motor_b_in2(MotorConstants::DEFAULT_MOTOR_B_IN2)
  {
  }
};

  /**
   * @brief Motor direction enumeration
   */
enum class MotorDirection
{
  STOP = 0,   // IN1=0, IN2=0 (coast/stop)
  FORWARD,    // IN1=1, IN2=0
  REVERSE,    // IN1=0, IN2=1
  BRAKE       // IN1=1, IN2=1 (brake)
};

/**
 * @brief Motor state information
 */
struct MotorState
{
  float left_speed;    // Normalized speed [-1.0, 1.0]
  float right_speed;   // Normalized speed [-1.0, 1.0]
  int left_pwm;        // PWM value for left motor
  int right_pwm;       // PWM value for right motor
};

  /**
   * @brief Hardware abstraction layer for motor control
   *
   * Manages left and right motors via Linux PWM subsystem and TB6612FNG
   * H-bridge motor driver. Supports both Raspberry Pi and DeepRacer platforms.
   */
class MotorManager
{
public:
    /**
     * @brief Constructor with default configuration
     * @param logger ROS logger for debugging and error reporting
     */
  MotorManager(rclcpp::Logger logger);

    /**
     * @brief Constructor with custom configuration
     * @param config Motor configuration
     * @param logger ROS logger for debugging and error reporting
     */
  MotorManager(const MotorConfig & config, rclcpp::Logger logger);

    /**
     * @brief Destructor
     */
  ~MotorManager();

    /**
     * @brief Initialize hardware and detect platform
     * @return true if initialization successful, false otherwise
     */
  bool initialize();

    /**
     * @brief Set motor speeds
     * @param left_speed Left motor speed [-1.0, 1.0]
     * @param right_speed Right motor speed [-1.0, 1.0]
     * @return true if successful, false otherwise
     */
  bool setMotorSpeeds(float left_speed, float right_speed);

  /**
   * @brief Stop all motors immediately
   * @return true if successful, false otherwise
   */
  bool stopMotors();

  /**
   * @brief Get current motor state
   * @return Current motor state
   */
  MotorState getMotorState() const;
  
  /**
   * @brief Update motor configuration
   * @param config New configuration
   * @return true if successful, false otherwise
   */
  bool updateConfig(const MotorConfig & config);

    /**
     * @brief Get current configuration
     * @return Current configuration
     */
  const MotorConfig & getConfig() const;

    /**
     * @brief Check if hardware is initialized and ready
     * @return true if ready, false otherwise
     */
  bool isReady() const;

private:
    /**
     * @brief Set individual motor speed and direction
     * @param motor Motor index (0 = left, 1 = right)
     * @param speed Motor speed [-1.0, 1.0]
     * @return true if successful, false otherwise
     */
  bool setMotorSpeed(int motor, float speed);

    /**
     * @brief Set motor direction via TB6612FNG H-bridge
     * @param motor Motor index (0 = left, 1 = right)
     * @param direction Motor direction
     * @return true if successful, false otherwise
     */
  bool setMotorDirection(int motor, MotorDirection direction);

    /**
     * @brief Convert normalized speed to PWM value
     * @param speed Normalized speed [-1.0, 1.0]
     * @return PWM value [0, max_pwm]
     */
  int speedToPwm(float speed) const;

  MotorConfig config_;

    // Motor A (Left) - 3 PWM channels for TB6612FNG control
  std::unique_ptr<PWM::Servo> motor_a_pwm_;   // Speed control
  std::unique_ptr<PWM::Servo> motor_a_in1_;   // Direction control 1
  std::unique_ptr<PWM::Servo> motor_a_in2_;   // Direction control 2

    // Motor B (Right) - 3 PWM channels for TB6612FNG control
  std::unique_ptr<PWM::Servo> motor_b_pwm_;   // Speed control
  std::unique_ptr<PWM::Servo> motor_b_in1_;   // Direction control 1
  std::unique_ptr<PWM::Servo> motor_b_in2_;   // Direction control 2

  MotorState current_state_;
  rclcpp::Logger logger_;
  bool initialized_;
  bool hardware_ready_;
};

} // namespace aws_deepracer_community_diffdrive_motor_pkg

#endif // DIFFDRIVE_MOTOR_PKG__MOTOR_MANAGER_HPP_
