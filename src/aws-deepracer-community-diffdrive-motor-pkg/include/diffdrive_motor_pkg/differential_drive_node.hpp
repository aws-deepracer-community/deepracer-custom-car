#ifndef DIFFDRIVE_MOTOR_PKG__DIFFERENTIAL_DRIVE_NODE_HPP_
#define DIFFDRIVE_MOTOR_PKG__DIFFERENTIAL_DRIVE_NODE_HPP_

#include <memory>
#include <chrono>

#include "rclcpp/rclcpp.hpp"
#include "deepracer_interfaces_pkg/msg/servo_ctrl_msg.hpp"
#include "deepracer_interfaces_pkg/msg/latency_measure_msg.hpp"
#include "deepracer_interfaces_pkg/srv/get_calibration_srv.hpp"
#include "deepracer_interfaces_pkg/srv/set_calibration_srv.hpp"
#include "deepracer_interfaces_pkg/srv/servo_gpio_srv.hpp"
#include "deepracer_interfaces_pkg/srv/get_led_ctrl_srv.hpp"
#include "deepracer_interfaces_pkg/srv/set_led_ctrl_srv.hpp"

#include "diffdrive_motor_pkg/differential_drive_controller.hpp"
#include "diffdrive_motor_pkg/motor_manager.hpp"
#include "diffdrive_motor_pkg/calibration_manager.hpp"
#include "diffdrive_motor_pkg/silent_led_handler.hpp"

namespace aws_deepracer_community_diffdrive_motor_pkg
{

/**
 * @brief Main ROS2 node for differential drive motor control
 *
 * This node replaces the servo package functionality by converting servo-style
 * commands (angle + throttle) to differential drive motor speeds (left + right).
 * It maintains full compatibility with existing DeepRacer applications.
 */
class DifferentialDriveNode : public rclcpp::Node
{
public:
  /**
   * @brief Constructor
   */
  explicit DifferentialDriveNode();

  /**
   * @brief Destructor
   */
  ~DifferentialDriveNode();

private:
  /**
   * @brief Callback for servo control messages
   * @param msg Servo control message containing angle and throttle
   */
  void servoMsgCallback(const deepracer_interfaces_pkg::msg::ServoCtrlMsg::SharedPtr msg);

  /**
   * @brief Callback for raw PWM messages
   * @param msg Raw PWM message for direct motor control
   */
  void rawPwmCallback(const deepracer_interfaces_pkg::msg::ServoCtrlMsg::SharedPtr msg);

  /**
   * @brief Service handler for getting calibration values
   * @param request Service request
   * @param response Service response
   */
  void getCalibrationService(
    const std::shared_ptr<deepracer_interfaces_pkg::srv::GetCalibrationSrv::Request> request,
    std::shared_ptr<deepracer_interfaces_pkg::srv::GetCalibrationSrv::Response> response);

  /**
   * @brief Service handler for setting calibration values
   * @param request Service request
   * @param response Service response
   */
  void setCalibrationService(
    const std::shared_ptr<deepracer_interfaces_pkg::srv::SetCalibrationSrv::Request> request,
    std::shared_ptr<deepracer_interfaces_pkg::srv::SetCalibrationSrv::Response> response);

  /**
   * @brief Service handler for GPIO control
   * @param request Service request
   * @param response Service response
   */
  void servoGpioService(
    const std::shared_ptr<deepracer_interfaces_pkg::srv::ServoGPIOSrv::Request> request,
    std::shared_ptr<deepracer_interfaces_pkg::srv::ServoGPIOSrv::Response> response);

  /**
   * @brief Service handler for getting LED control state
   * @param request Service request
   * @param response Service response
   */
  void getLedCtrlService(
    const std::shared_ptr<deepracer_interfaces_pkg::srv::GetLedCtrlSrv::Request> request,
    std::shared_ptr<deepracer_interfaces_pkg::srv::GetLedCtrlSrv::Response> response);

  /**
   * @brief Service handler for setting LED control state
   * @param request Service request
   * @param response Service response
   */
  void setLedCtrlService(
    const std::shared_ptr<deepracer_interfaces_pkg::srv::SetLedCtrlSrv::Request> request,
    std::shared_ptr<deepracer_interfaces_pkg::srv::SetLedCtrlSrv::Response> response);

  /**
   * @brief Sync calibration data from CalibrationManager to DifferentialDriveController
   */
  void syncCalibrationToController();

  // ROS2 subscribers
  rclcpp::Subscription<deepracer_interfaces_pkg::msg::ServoCtrlMsg>::SharedPtr servo_msg_sub_;
  rclcpp::Subscription<deepracer_interfaces_pkg::msg::ServoCtrlMsg>::SharedPtr raw_pwm_sub_;

  // ROS2 services
  rclcpp::Service<deepracer_interfaces_pkg::srv::GetCalibrationSrv>::SharedPtr
    get_calibration_service_;
  rclcpp::Service<deepracer_interfaces_pkg::srv::SetCalibrationSrv>::SharedPtr
    set_calibration_service_;
  rclcpp::Service<deepracer_interfaces_pkg::srv::ServoGPIOSrv>::SharedPtr servo_gpio_service_;
  rclcpp::Service<deepracer_interfaces_pkg::srv::GetLedCtrlSrv>::SharedPtr get_led_ctrl_service_;
  rclcpp::Service<deepracer_interfaces_pkg::srv::SetLedCtrlSrv>::SharedPtr set_led_ctrl_service_;

  // ROS2 publishers
  rclcpp::Publisher<deepracer_interfaces_pkg::msg::LatencyMeasureMsg>::SharedPtr latency_pub_;

  // Core components
  std::unique_ptr<DifferentialDriveController> drive_controller_;
  std::unique_ptr<MotorManager> motor_manager_;
  std::unique_ptr<CalibrationManager> calibration_manager_;
  std::unique_ptr<SilentLEDHandler> led_handler_;

  // Latency measurement constants and tracking
  static constexpr int LATENCY_MEASURE_FREQ = 5;
  int latency_msg_count_;
};

}  // namespace aws_deepracer_community_diffdrive_motor_pkg

#endif  // DIFFDRIVE_MOTOR_PKG__DIFFERENTIAL_DRIVE_NODE_HPP_
