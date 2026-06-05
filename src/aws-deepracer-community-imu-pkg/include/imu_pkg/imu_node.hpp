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

#ifndef IMU_PKG__IMU_NODE_HPP_
#define IMU_PKG__IMU_NODE_HPP_

#include <memory>
#include <string>

#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/imu.hpp"
#include "deepracer_interfaces_pkg/srv/enable_state_srv.hpp"
#include "imu_pkg/bmi160.hpp"

namespace imu_pkg
{

/// IMU node for AWS DeepRacer / DeepRacer Community
///
/// Reads the Bosch BMI160 6-DOF IMU via Linux I2C and:
///   - Publishes sensor_msgs/Imu on /imu_pkg/imu_msg/data_raw
///     (only when at least one subscriber is present)
///   - Optionally calls the ctrl_pkg vehicle_state service with
///     is_active=false when a crash (high-G) or pickup is detected.
class ImuNode : public rclcpp::Node
{
public:
  explicit ImuNode();
  ~ImuNode() = default;

private:
  // Callbacks
  void timerCallback();
  void heartbeatCallback();

  // Safety actions
  void triggerStop(const std::string & reason);

  // Sensor initialisation (called once after construction)
  bool initSensor();

  // ---------- Publishers / Clients ----------
  rclcpp::Publisher<sensor_msgs::msg::Imu>::SharedPtr imu_publisher_;
  rclcpp::Client<deepracer_interfaces_pkg::srv::EnableStateSrv>::SharedPtr
    vehicle_state_client_;

  // ---------- Timers ----------
  rclcpp::TimerBase::SharedPtr publish_timer_;
  rclcpp::TimerBase::SharedPtr heartbeat_timer_;
  int heartbeat_count_{0};

  // ---------- IMU driver ----------
  std::unique_ptr<BMI160> imu_;

  // ---------- Parameters (cached after construction) ----------
  int    bus_id_;
  int    address_;
  int    publish_rate_;
  int    accel_range_g_;
  int    gyro_range_dps_;
  int    accel_z_gravity_target_;
  bool   stop_on_pickup_;
  bool   stop_on_crash_;
  double crash_accel_threshold_g_;
  double pickup_threshold_g_;
};

}  // namespace imu_pkg

#endif  // IMU_PKG__IMU_NODE_HPP_
