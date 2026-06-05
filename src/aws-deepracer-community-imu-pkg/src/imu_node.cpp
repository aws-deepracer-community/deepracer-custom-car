///////////////////////////////////////////////////////////////////////////////////
//   Copyright AWS DeepRacer Community. All Rights Reserved.                    //
//                                                                               //
//   Licensed under the Apache License, Version 2.0 (the "License").             //
//   You may not use this file except in compliance with the License.            //
//   You may obtain a copy of the License at                                     //
//                                                                               //
//       http://www.apache.org/licenses/LICENSE-2.0                              //
//                                                                               //
//   Unless required by applicable law or agreed to in writing, software         //
//   distributed under the License is distributed on an "AS IS" BASIS,           //
//   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.    //
//   See the License for the specific language governing permissions and         //
//   limitations under the License.                                              //
///////////////////////////////////////////////////////////////////////////////////

#include "imu_pkg/imu_node.hpp"
#include "imu_pkg/conversions.hpp"

#include <cmath>
#include <functional>
#include <memory>
#include <string>

namespace imu_pkg
{

// -------------------------------------------------------------------------
// Topic / service names
// -------------------------------------------------------------------------
static constexpr char IMU_TOPIC[] = "imu_msg/data_raw";
static constexpr char VEHICLE_STATE_SRV[] = "/ctrl_pkg/enable_state";

// Default I2C bus per hardware platform
#if defined(HW_PLATFORM_DR)
static constexpr int DEFAULT_BUS_ID = 7;
#else
static constexpr int DEFAULT_BUS_ID = 1;  // RPI or unknown
#endif

// -------------------------------------------------------------------------
// Constructor
// -------------------------------------------------------------------------
ImuNode::ImuNode()
: Node("imu_node")
{
  RCLCPP_INFO(get_logger(), "IMU node starting...");

  // --- Declare parameters ---
  declare_parameter<int>("bus_id", DEFAULT_BUS_ID);
  declare_parameter<int>("address", 0x68);
  declare_parameter<int>("publish_rate", 25);
  declare_parameter<int>("accel_range_g", 4);
  declare_parameter<int>("gyro_range_dps", 250);
  declare_parameter<int>("accel_z_gravity_target", -1);
  declare_parameter<bool>("stop_on_pickup", false);
  declare_parameter<bool>("stop_on_crash", false);
  declare_parameter<double>("crash_accel_threshold_g", 3.0);
  declare_parameter<double>("pickup_threshold_g", 0.5);

  // --- Cache parameters ---
  bus_id_ = get_parameter("bus_id").as_int();
  address_ = get_parameter("address").as_int();
  publish_rate_ = get_parameter("publish_rate").as_int();
  accel_range_g_ = get_parameter("accel_range_g").as_int();
  gyro_range_dps_ = get_parameter("gyro_range_dps").as_int();
  accel_z_gravity_target_ = get_parameter("accel_z_gravity_target").as_int();
  stop_on_pickup_ = get_parameter("stop_on_pickup").as_bool();
  stop_on_crash_ = get_parameter("stop_on_crash").as_bool();
  crash_accel_threshold_g_ = get_parameter("crash_accel_threshold_g").as_double();
  pickup_threshold_g_ = get_parameter("pickup_threshold_g").as_double();

  RCLCPP_INFO(
    get_logger(),
    "Parameters: bus=%d addr=0x%02X rate=%dHz accel=±%dG gyro=±%ddps "
    "z_target=%+d stop_on_pickup=%s stop_on_crash=%s",
    bus_id_, address_, publish_rate_, accel_range_g_, gyro_range_dps_,
    accel_z_gravity_target_,
    stop_on_pickup_ ? "true" : "false",
    stop_on_crash_ ? "true" : "false");

  // --- Publisher ---
  auto qos = rclcpp::QoS(rclcpp::KeepLast(1)).best_effort();
  imu_publisher_ = create_publisher<sensor_msgs::msg::Imu>(IMU_TOPIC, qos);

  // --- Vehicle-state service client (only if stop features enabled) ---
  if (stop_on_pickup_ || stop_on_crash_) {
    auto cb_group = create_callback_group(rclcpp::CallbackGroupType::MutuallyExclusive);
    vehicle_state_client_ =
      create_client<deepracer_interfaces_pkg::srv::EnableStateSrv>(
        VEHICLE_STATE_SRV, rclcpp::SystemDefaultsQoS(), cb_group);
    RCLCPP_INFO(get_logger(), "Safety stop features enabled; waiting for %s ...",
      VEHICLE_STATE_SRV);
  }

  // --- Initialise sensor ---
  if (!initSensor()) {
    RCLCPP_ERROR(get_logger(), "IMU sensor initialisation failed — node will not publish");
    return;
  }

  // --- Publish timer ---
  auto period_ms = std::chrono::milliseconds(1000 / publish_rate_);
  publish_timer_ = create_timer(
    period_ms, std::bind(&ImuNode::timerCallback, this));

  // --- Heartbeat timer (5 s) ---
  heartbeat_timer_ = create_timer(
    std::chrono::seconds(5), std::bind(&ImuNode::heartbeatCallback, this));

  RCLCPP_INFO(get_logger(), "IMU node started, publishing at %d Hz", publish_rate_);
}

// -------------------------------------------------------------------------
// Sensor initialisation
// -------------------------------------------------------------------------
bool ImuNode::initSensor()
{
  imu_ = std::make_unique<BMI160>(get_logger());

  if (!imu_->init(bus_id_, address_)) {
    return false;
  }

  imu_->configure(accel_range_g_, gyro_range_dps_);
  imu_->calibrate(accel_z_gravity_target_);

  if (stop_on_crash_) {
    imu_->configureHighGInterrupt(static_cast<float>(crash_accel_threshold_g_));
  }

  return true;
}

// -------------------------------------------------------------------------
// Timer callback — runs at publish_rate_ Hz
// -------------------------------------------------------------------------
void ImuNode::timerCallback()
{
  int16_t raw_gx, raw_gy, raw_gz, raw_ax, raw_ay, raw_az;
  if (!imu_->readMotion6(raw_gx, raw_gy, raw_gz, raw_ax, raw_ay, raw_az)) {
    RCLCPP_WARN_THROTTLE(get_logger(), *get_clock(), 5000,
      "IMU read failed, skipping frame");
    return;
  }

  const auto data = conversions::applyAxisMapping(
    raw_gx, raw_gy, raw_gz, raw_ax, raw_ay, raw_az,
    imu_->accel_scale(), imu_->gyro_scale());

  const float gyro_x = data.gyro_x;
  const float gyro_y = data.gyro_y;
  const float gyro_z = data.gyro_z;
  const float accel_x = data.accel_x;
  const float accel_y = data.accel_y;
  const float accel_z = data.accel_z;

  // --- Safety checks (before publishing) ---
  if (stop_on_crash_ && imu_->isHighGTriggered()) {
    triggerStop("crash");
  }

  if (stop_on_pickup_) {
    if (conversions::isPickupDetected(
        static_cast<double>(accel_z), accel_z_gravity_target_, pickup_threshold_g_))
    {
      triggerStop("pickup");
    }
  }

  // --- Publish only when there are active subscribers ---
  if (imu_publisher_->get_subscription_count() == 0) {
    return;
  }

  sensor_msgs::msg::Imu msg;
  msg.header.stamp = now();
  msg.header.frame_id = "base_link";

  msg.angular_velocity.x = gyro_x;
  msg.angular_velocity.y = gyro_y;
  msg.angular_velocity.z = gyro_z;
  // Diagonal covariance 0.01; off-diagonals 0
  msg.angular_velocity_covariance = {
    0.01, 0.0, 0.0,
    0.0, 0.01, 0.0,
    0.0, 0.0, 0.01};

  msg.linear_acceleration.x = accel_x;
  msg.linear_acceleration.y = accel_y;
  msg.linear_acceleration.z = accel_z;
  msg.linear_acceleration_covariance = {
    0.01, 0.0, 0.0,
    0.0, 0.01, 0.0,
    0.0, 0.0, 0.01};

  // Orientation unknown — signal this with covariance[0] = -1
  msg.orientation_covariance[0] = -1.0;

  RCLCPP_DEBUG(get_logger(), "gyro(%.2f, %.2f, %.2f) accel(%.2f, %.2f, %.2f)",
    gyro_x, gyro_y, gyro_z, accel_x, accel_y, accel_z);

  imu_publisher_->publish(msg);
}

// -------------------------------------------------------------------------
// Safety stop
// -------------------------------------------------------------------------
void ImuNode::triggerStop(const std::string & reason)
{
  RCLCPP_WARN(get_logger(), "IMU safety stop triggered: %s", reason.c_str());

  if (!vehicle_state_client_) {
    RCLCPP_ERROR(get_logger(),
      "triggerStop called but vehicle_state client is not initialised");
    return;
  }

  if (!vehicle_state_client_->service_is_ready()) {
    RCLCPP_ERROR(get_logger(),
      "vehicle_state service not available — cannot stop vehicle");
    return;
  }

  auto request = std::make_shared<deepracer_interfaces_pkg::srv::EnableStateSrv::Request>();
  request->is_active = false;

  // Fire-and-forget async call; we do not need the response.
  vehicle_state_client_->async_send_request(request);
}

// -------------------------------------------------------------------------
// Heartbeat
// -------------------------------------------------------------------------
void ImuNode::heartbeatCallback()
{
  RCLCPP_DEBUG(get_logger(), "IMU heartbeat #%d", ++heartbeat_count_);
}

}  // namespace imu_pkg

// -------------------------------------------------------------------------
// main
// -------------------------------------------------------------------------
int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);

  auto node = std::make_shared<imu_pkg::ImuNode>();

  rclcpp::executors::MultiThreadedExecutor executor;
  executor.add_node(node);
  executor.spin();

  rclcpp::shutdown();
  return 0;
}
