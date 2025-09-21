#include "diffdrive_motor_pkg/differential_drive_node.hpp"
#include "diffdrive_motor_pkg/motor_constants.hpp"

namespace aws_deepracer_community_diffdrive_motor_pkg
{

DifferentialDriveNode::DifferentialDriveNode()
: Node("diffdrive_motor_node"), latency_msg_count_(0)
{
    // Declare parameters with named constants
  this->declare_parameter("max_forward_speed", MotorConstants::DEFAULT_MAX_FORWARD_SPEED);
  this->declare_parameter("max_backward_speed", MotorConstants::DEFAULT_MAX_BACKWARD_SPEED);
  this->declare_parameter("max_left_differential", MotorConstants::DEFAULT_MAX_LEFT_DIFFERENTIAL);
  this->declare_parameter("max_right_differential", MotorConstants::DEFAULT_MAX_RIGHT_DIFFERENTIAL);
  this->declare_parameter("center_offset", MotorConstants::DEFAULT_CENTER_OFFSET);
  this->declare_parameter("motor_polarity", MotorConstants::DEFAULT_MOTOR_POLARITY);
  this->declare_parameter("motor_a_pwm", MotorConstants::DEFAULT_MOTOR_A_PWM);
  this->declare_parameter("motor_a_in1", MotorConstants::DEFAULT_MOTOR_A_IN1);
  this->declare_parameter("motor_a_in2", MotorConstants::DEFAULT_MOTOR_A_IN2);
  this->declare_parameter("motor_b_pwm", MotorConstants::DEFAULT_MOTOR_B_PWM);
  this->declare_parameter("motor_b_in1", MotorConstants::DEFAULT_MOTOR_B_IN1);
  this->declare_parameter("motor_b_in2", MotorConstants::DEFAULT_MOTOR_B_IN2);

    // Initialize differential drive controller
  DifferentialDriveConfig drive_config;
  drive_config.max_forward_speed = this->get_parameter("max_forward_speed").as_double();
  drive_config.max_backward_speed = this->get_parameter("max_backward_speed").as_double();
  drive_config.max_left_differential = this->get_parameter("max_left_differential").as_double();
  drive_config.max_right_differential = this->get_parameter("max_right_differential").as_double();
  drive_config.center_offset = this->get_parameter("center_offset").as_double();
  drive_config.motor_polarity = this->get_parameter("motor_polarity").as_int();

  drive_controller_ = std::make_unique<DifferentialDriveController>(drive_config);

    // Initialize motor manager
  MotorConfig motor_config;
  motor_config.motor_a_pwm = this->get_parameter("motor_a_pwm").as_int();
  motor_config.motor_a_in1 = this->get_parameter("motor_a_in1").as_int();
  motor_config.motor_a_in2 = this->get_parameter("motor_a_in2").as_int();
  motor_config.motor_b_pwm = this->get_parameter("motor_b_pwm").as_int();
  motor_config.motor_b_in1 = this->get_parameter("motor_b_in1").as_int();
  motor_config.motor_b_in2 = this->get_parameter("motor_b_in2").as_int();

  motor_manager_ = std::make_unique<MotorManager>(motor_config, this->get_logger());

    // Initialize motor hardware
  if (!motor_manager_->initialize()) {
    RCLCPP_ERROR(this->get_logger(), "Failed to initialize motor manager");
  } else {
    // Motors start disabled by default for safety - must be explicitly enabled via GPIO service
    motor_manager_->setMotorsEnabled(false);
  }

    // Initialize calibration manager with ROS parameters as defaults
  calibration_manager_ = std::make_unique<CalibrationManager>("", drive_config);
  led_handler_ = std::make_unique<SilentLEDHandler>();

    // Sync calibration data to drive controller
  syncCalibrationToController();

    // Create subscribers
  servo_msg_sub_ = this->create_subscription<deepracer_interfaces_pkg::msg::ServoCtrlMsg>(
        "/servo_pkg/servo_msg", 10,
        std::bind(&DifferentialDriveNode::servoMsgCallback, this, std::placeholders::_1));

  raw_pwm_sub_ = this->create_subscription<deepracer_interfaces_pkg::msg::ServoCtrlMsg>(
        "/servo_pkg/raw_pwm", 10,
        std::bind(&DifferentialDriveNode::rawPwmCallback, this, std::placeholders::_1));

    // Create services
  get_calibration_service_ = this->create_service<deepracer_interfaces_pkg::srv::GetCalibrationSrv>(
        "/servo_pkg/get_calibration",
        std::bind(&DifferentialDriveNode::getCalibrationService, this, std::placeholders::_1,
      std::placeholders::_2));

  set_calibration_service_ = this->create_service<deepracer_interfaces_pkg::srv::SetCalibrationSrv>(
        "/servo_pkg/set_calibration",
        std::bind(&DifferentialDriveNode::setCalibrationService, this, std::placeholders::_1,
      std::placeholders::_2));

  servo_gpio_service_ = this->create_service<deepracer_interfaces_pkg::srv::ServoGPIOSrv>(
        "/servo_pkg/servo_gpio",
        std::bind(&DifferentialDriveNode::servoGpioService, this, std::placeholders::_1,
      std::placeholders::_2));

  get_led_ctrl_service_ = this->create_service<deepracer_interfaces_pkg::srv::GetLedCtrlSrv>(
        "/servo_pkg/get_led_state",
        std::bind(&DifferentialDriveNode::getLedCtrlService, this, std::placeholders::_1,
      std::placeholders::_2));

  set_led_ctrl_service_ = this->create_service<deepracer_interfaces_pkg::srv::SetLedCtrlSrv>(
        "/servo_pkg/set_led_state",
        std::bind(&DifferentialDriveNode::setLedCtrlService, this, std::placeholders::_1,
      std::placeholders::_2));

    // Create publisher for latency measurement
  latency_pub_ = this->create_publisher<deepracer_interfaces_pkg::msg::LatencyMeasureMsg>(
        "/servo_pkg/latency_measure", 10);

  RCLCPP_INFO(this->get_logger(), "DifferentialDriveNode initialized successfully");
}

DifferentialDriveNode::~DifferentialDriveNode()
{
  if (motor_manager_) {
    motor_manager_->stopMotors();
    motor_manager_->setMotorsEnabled(false);
  }
  RCLCPP_INFO(this->get_logger(), "DifferentialDriveNode shutting down");
}

void DifferentialDriveNode::servoMsgCallback(
  const deepracer_interfaces_pkg::msg::ServoCtrlMsg::SharedPtr msg)
{
  if (!motor_manager_ || !drive_controller_) {
    RCLCPP_WARN(this->get_logger(), "Components not initialized");
    return;
  }

  if (!motor_manager_->isReady()) {
    RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 1000, "Motor manager not ready");
    return;
  }

  // Check if motors are enabled before processing commands
  if (!motor_manager_->getMotorState().enabled) {
    RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 2000,
        "Motors are disabled - ignoring servo command");
    return;
  }

    // Convert servo commands to motor speeds
  auto motor_speeds = drive_controller_->convertServoToMotorSpeeds(msg->angle, msg->throttle);

    // Apply motor speeds
  if (!motor_manager_->setMotorSpeeds(motor_speeds.left_speed, motor_speeds.right_speed)) {
    RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 1000,
        "Failed to set motor speeds");
  }

  // Latency measurement (matching servo_mgr implementation)
  auto now = this->get_clock()->now();
  latency_msg_count_ = (latency_msg_count_ + 1) % LATENCY_MEASURE_FREQ;

  // If there is a source_stamp and subscribers, publish the latency message
  if (msg->source_stamp.sec != 0 && latency_pub_->get_subscription_count() > 0 &&
    latency_msg_count_ == 0)
  {
    auto latency_msg = deepracer_interfaces_pkg::msg::LatencyMeasureMsg();
    int64_t latency_ns = now.nanoseconds() -
      (msg->source_stamp.sec * 1000000000LL + msg->source_stamp.nanosec);
    latency_msg.latency_ms = static_cast<float>(latency_ns) / 1.0e6;
    latency_pub_->publish(latency_msg);
  }

  RCLCPP_DEBUG(this->get_logger(),
      "Servo command: angle=%.3f, throttle=%.3f -> left=%.3f, right=%.3f",
                 msg->angle, msg->throttle, motor_speeds.left_speed, motor_speeds.right_speed);
}

void DifferentialDriveNode::rawPwmCallback(
  const deepracer_interfaces_pkg::msg::ServoCtrlMsg::SharedPtr msg)
{
    // For raw PWM control, bypass the differential drive controller and directly control motors
  if (!motor_manager_) {
    RCLCPP_WARN(this->get_logger(), "Motor manager not initialized");
    return;
  }

  if (!motor_manager_->isReady()) {
    RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 1000, "Motor manager not ready");
    return;
  }

  // Check if motors are enabled before processing commands
  if (!motor_manager_->getMotorState().enabled) {
    RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 2000,
        "Motors are disabled - ignoring raw PWM command");
    return;
  }

    // Direct motor speed setting (assuming angle controls differential and throttle controls speed)
  float base_speed = msg->throttle;
  float turn_differential = msg->angle * 0.5f;   // Scale turn factor

  float left_speed = base_speed + turn_differential;
  float right_speed = base_speed - turn_differential;

  if (!motor_manager_->setMotorSpeeds(left_speed, right_speed)) {
    RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 1000,
        "Failed to set raw PWM speeds");
  }

  RCLCPP_DEBUG(this->get_logger(), "Raw PWM: angle=%.3f, throttle=%.3f -> left=%.3f, right=%.3f",
                 msg->angle, msg->throttle, left_speed, right_speed);
}

void DifferentialDriveNode::getCalibrationService(
  const std::shared_ptr<deepracer_interfaces_pkg::srv::GetCalibrationSrv::Request> request,
  std::shared_ptr<deepracer_interfaces_pkg::srv::GetCalibrationSrv::Response> response)
{
  if (calibration_manager_) {
    calibration_manager_->handleGetCalibrationService(request, response);
  } else {
    RCLCPP_ERROR(this->get_logger(), "Calibration manager not initialized");
    response->error = 1;
  }
}

void DifferentialDriveNode::setCalibrationService(
  const std::shared_ptr<deepracer_interfaces_pkg::srv::SetCalibrationSrv::Request> request,
  std::shared_ptr<deepracer_interfaces_pkg::srv::SetCalibrationSrv::Response> response)
{
  if (calibration_manager_) {
    calibration_manager_->handleSetCalibrationService(request, response);

      // Sync new calibration values to the drive controller
    syncCalibrationToController();
  } else {
    RCLCPP_ERROR(this->get_logger(), "Calibration manager not initialized");
    response->error = 1;
  }
}
void DifferentialDriveNode::servoGpioService(
  const std::shared_ptr<deepracer_interfaces_pkg::srv::ServoGPIOSrv::Request> request,
  std::shared_ptr<deepracer_interfaces_pkg::srv::ServoGPIOSrv::Response> response)
{
  if (!motor_manager_) {
    RCLCPP_ERROR(this->get_logger(), "Motor manager not initialized");
    response->error = 1;
    return;
  }

  // Enable/disable motor control based on request
  // Note: request->enable = 0 means enable, request->enable = 1 means disable
  bool enable_motors = (request->enable == 0);

  if (enable_motors) {
    // Enable motors
    motor_manager_->setMotorsEnabled(true);
  } else {
    // Disable motors - stop them first, then disable
    motor_manager_->stopMotors();
    motor_manager_->setMotorsEnabled(false);
  }

  response->error = 0;  // Success
}

void DifferentialDriveNode::getLedCtrlService(
  const std::shared_ptr<deepracer_interfaces_pkg::srv::GetLedCtrlSrv::Request> request,
  std::shared_ptr<deepracer_interfaces_pkg::srv::GetLedCtrlSrv::Response> response)
{
  if (led_handler_) {
    *response = led_handler_->getLedState(*request);
  } else {
    RCLCPP_ERROR(this->get_logger(), "LED handler not initialized");
      // Note: GetLedCtrlSrv response has no error field, setting defaults
    response->red = 0;
    response->green = 0;
    response->blue = 0;
  }
}

void DifferentialDriveNode::setLedCtrlService(
  const std::shared_ptr<deepracer_interfaces_pkg::srv::SetLedCtrlSrv::Request> request,
  std::shared_ptr<deepracer_interfaces_pkg::srv::SetLedCtrlSrv::Response> response)
{
  if (led_handler_) {
    *response = led_handler_->setLedState(*request);
  } else {
    RCLCPP_ERROR(this->get_logger(), "LED handler not initialized");
    response->error = 1;
  }
}

void DifferentialDriveNode::syncCalibrationToController()
{
  if (!calibration_manager_ || !drive_controller_) {
    return;
  }

  const DifferentialDriveConfig & cal_data = calibration_manager_->getCalibrationData();
  drive_controller_->updateConfig(cal_data);
}

} // namespace aws_deepracer_community_diffdrive_motor_pkg

/**
 * @brief Main entry point for differential drive motor node
 */
int main(int argc, char *argv[])
{
  rclcpp::init(argc, argv);

  auto node =
    std::make_shared<aws_deepracer_community_diffdrive_motor_pkg::DifferentialDriveNode>();

  rclcpp::spin(node);

  rclcpp::shutdown();
  return 0;
}
