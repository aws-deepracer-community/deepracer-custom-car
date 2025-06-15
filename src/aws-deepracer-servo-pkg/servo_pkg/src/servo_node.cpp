///////////////////////////////////////////////////////////////////////////////////
//   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.          //
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

#include "rclcpp/rclcpp.hpp"
#include "servo_pkg/servo_mgr.hpp"
#include "servo_pkg/led_mgr.hpp"
#include "deepracer_interfaces_pkg/msg/servo_ctrl_msg.hpp"
#include "deepracer_interfaces_pkg/srv/get_calibration_srv.hpp"
#include "deepracer_interfaces_pkg/srv/set_calibration_srv.hpp"
#include "deepracer_interfaces_pkg/srv/set_led_ctrl_srv.hpp"
#include "deepracer_interfaces_pkg/srv/get_led_ctrl_srv.hpp"
#include "deepracer_interfaces_pkg/srv/servo_gpio_srv.hpp"


/// Node entry point
int main(int argc, char **argv) {

    rclcpp::init(argc, argv);

    const char* SERVO_GPIO_SERVICE_NAME = "servo_gpio";
    const char* SET_CAL_SERVICE_NAME = "set_calibration";
    const char* GET_CAL_SERVICE_NAME = "get_calibration";
    const char* SET_LED_STATE_SERVICE_NAME = "set_led_state";
    const char* GET_LED_STATE_SERVICE_NAME = "get_led_state";
    const char* SERVO_TOPIC = "/ctrl_pkg/servo_msg";
    const char* RAW_PWM_TOPIC = "/ctrl_pkg/raw_pwm";
    const char* LATENCY_TOPIC = "/servo_pkg/latency";
    
    std::shared_ptr<rclcpp::Node> node = rclcpp::Node::make_shared("servo_node");

    auto pub_ = node->create_publisher<deepracer_interfaces_pkg::msg::LatencyMeasureMsg>(LATENCY_TOPIC, rclcpp::SystemDefaultsQoS());

    auto servoMgr = std::make_unique<PWM::ServoMgr>(node->get_logger(), node->get_clock(), pub_);
    auto ledMgr = std::make_unique<PWM::LedMgr>(node->get_logger());
    auto qos = rclcpp::QoS(rclcpp::KeepLast(1));
    qos.best_effort();
    auto qos_default = rclcpp::QoS(rclcpp::SystemDefaultsQoS()).get_rmw_qos_profile();

    // Create a callback group for the servo subscription
    auto servoSubscriberCbGrp_ = node->create_callback_group(rclcpp::CallbackGroupType::MutuallyExclusive);
    
    // Create subscription options and set the callback group
    rclcpp::SubscriptionOptions servoOptions;
    servoOptions.callback_group = servoSubscriberCbGrp_;

    auto sub_ = node->create_subscription<deepracer_interfaces_pkg::msg::ServoCtrlMsg>(SERVO_TOPIC,
                                                                                       qos,
                                                                                       std::bind(&PWM::ServoMgr::servoSubscriber,
                                                                                                 servoMgr.get(),
                                                                                                 std::placeholders::_1),
                                                                                       servoOptions
                                                                                       );
    auto rawPWMsub_ = node->create_subscription<deepracer_interfaces_pkg::msg::ServoCtrlMsg>(RAW_PWM_TOPIC,
                                                                                       qos,
                                                                                       std::bind(&PWM::ServoMgr::rawPWMSubscriber,
                                                                                                 servoMgr.get(),
                                                                                                 std::placeholders::_1),
                                                                                        rclcpp::SubscriptionOptions()
                                                                                        );
    auto servoCalServiceCbGrp_ = node->create_callback_group(rclcpp::CallbackGroupType::Reentrant);
    rclcpp::Service<deepracer_interfaces_pkg::srv::SetCalibrationSrv>::SharedPtr servoCalService =
        node->create_service<deepracer_interfaces_pkg::srv::SetCalibrationSrv>(SET_CAL_SERVICE_NAME,
                                                                               std::bind(&PWM::ServoMgr::setCalHdl,
                                                                               servoMgr.get(),
                                                                               std::placeholders::_1,
                                                                               std::placeholders::_2,
                                                                               std::placeholders::_3),
                                                                               qos_default,
                                                                               servoCalServiceCbGrp_);

    auto setGPIOServiceCbGrp_ = node->create_callback_group(rclcpp::CallbackGroupType::MutuallyExclusive);
    rclcpp::Service<deepracer_interfaces_pkg::srv::ServoGPIOSrv>::SharedPtr setGPIOService =
        node->create_service<deepracer_interfaces_pkg::srv::ServoGPIOSrv>(SERVO_GPIO_SERVICE_NAME,
                                                                          std::bind(&PWM::ServoMgr::setGPIOHdl,
                                                                          servoMgr.get(),
                                                                          std::placeholders::_1,
                                                                          std::placeholders::_2,
                                                                          std::placeholders::_3),
                                                                          qos_default,
                                                                          setGPIOServiceCbGrp_);

    auto getCalServiceCbGrp_ = node->create_callback_group(rclcpp::CallbackGroupType::Reentrant);
    rclcpp::Service<deepracer_interfaces_pkg::srv::GetCalibrationSrv>::SharedPtr getCalService =
        node->create_service<deepracer_interfaces_pkg::srv::GetCalibrationSrv>(GET_CAL_SERVICE_NAME,
                                                                       std::bind(&PWM::ServoMgr::getCalHdl,
                                                                       servoMgr.get(),
                                                                       std::placeholders::_1,
                                                                       std::placeholders::_2,
                                                                       std::placeholders::_3),
                                                                       qos_default,
                                                                       getCalServiceCbGrp_);

    auto setLedCtrlCbGrp_ = node->create_callback_group(rclcpp::CallbackGroupType::Reentrant);
    rclcpp::Service<deepracer_interfaces_pkg::srv::SetLedCtrlSrv>::SharedPtr setLedCtrlService =
        node->create_service<deepracer_interfaces_pkg::srv::SetLedCtrlSrv>(SET_LED_STATE_SERVICE_NAME,
                                                                           std::bind(&PWM::LedMgr::setLedCtrlHdl,
                                                                           ledMgr.get(),
                                                                           std::placeholders::_1,
                                                                           std::placeholders::_2,
                                                                           std::placeholders::_3),
                                                                           qos_default,
                                                                           setLedCtrlCbGrp_);

    auto getLedCtrlCbGrp_ = node->create_callback_group(rclcpp::CallbackGroupType::Reentrant);
    rclcpp::Service<deepracer_interfaces_pkg::srv::GetLedCtrlSrv>::SharedPtr getLedCtrlService =
        node->create_service<deepracer_interfaces_pkg::srv::GetLedCtrlSrv>(GET_LED_STATE_SERVICE_NAME,
                                                                           std::bind(&PWM::LedMgr::getLedCtrlHdl,
                                                                           ledMgr.get(),
                                                                           std::placeholders::_1,
                                                                           std::placeholders::_2,
                                                                           std::placeholders::_3),
                                                                           qos_default,
                                                                           getLedCtrlCbGrp_);

    RCLCPP_INFO(node->get_logger(), "servo_node started");
    rclcpp::executors::MultiThreadedExecutor exec;
    exec.add_node(node);
    exec.spin();
    rclcpp::shutdown();

    return 0;
}
