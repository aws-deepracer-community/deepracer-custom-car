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

#ifndef SERVO_MGR_HPP
#define SERVO_MGR_HPP

#include <sys/stat.h>
#include "servo_pkg/pwm.hpp"
#include "rclcpp/rclcpp.hpp"
#include "servo_pkg/bios_version.hpp"
#include "servo_pkg/utility.hpp"

#include "deepracer_interfaces_pkg/msg/servo_ctrl_msg.hpp"
#include "deepracer_interfaces_pkg/msg/latency_measure_msg.hpp"
#include "deepracer_interfaces_pkg/srv/get_calibration_srv.hpp"
#include "deepracer_interfaces_pkg/srv/set_calibration_srv.hpp"
#include "deepracer_interfaces_pkg/srv/servo_gpio_srv.hpp"

namespace PWM {
    /// Current version of the calibration file, when incremented
    /// check writeJSONToFile and setCalFromFile to ensure backward
    /// compatibility
    #define CAL_FILE_VERSION 1
    /// Default servo parameters provided by pegatron. All values in ns
    #define SERVO_MAX 1700000
    #define SERVO_MID 1450000
    #define SERVO_MIN 1200000
    #define MOTOR_MAX 1603500
    #define MOTOR_MID 1446000
    #define MOTOR_MIN 1311000
    #define POLARITY_SERVO_VAL 1
    #define POLARITY_MOTOR_VAL -1
    #define SERVO_PERIOD 20000000
    /// Servo GPIO channel based on hardware platform
    #if defined(HW_PLATFORM_RPI)
        #define GPIO_CHANNEL -1
    #else
        // Default for DeepRacer (DR)
        #define GPIO_CHANNEL 436
    #endif

    class ServoMgr
        {
        public:
            ServoMgr(rclcpp::Logger logger_, std::shared_ptr<rclcpp::Clock> clock, 
                     std::shared_ptr<rclcpp::Publisher<deepracer_interfaces_pkg::msg::LatencyMeasureMsg, std::allocator<void>>> latencyPub);
            ~ServoMgr();
            void servoSubscriber(const deepracer_interfaces_pkg::msg::ServoCtrlMsg::SharedPtr servoMsg);
            void rawPWMSubscriber(const deepracer_interfaces_pkg::msg::ServoCtrlMsg::SharedPtr servoMsg);
            
            /// Handler for setting the min and max value of the servos.
            void setCalHdl(const std::shared_ptr<rmw_request_id_t> request_header,
                           const std::shared_ptr<deepracer_interfaces_pkg::srv::SetCalibrationSrv::Request> req,
                           std::shared_ptr<deepracer_interfaces_pkg::srv::SetCalibrationSrv::Response> res);

            /// Handler for seeting the servo GPIO pin to disable/enable.
            void setGPIOHdl(const std::shared_ptr<rmw_request_id_t> request_header,
                            const std::shared_ptr<deepracer_interfaces_pkg::srv::ServoGPIOSrv::Request> req,
                            std::shared_ptr<deepracer_interfaces_pkg::srv::ServoGPIOSrv::Response> res);
            
            /// Handler for get calibration request
            void getCalHdl(const std::shared_ptr<rmw_request_id_t> request_header,
                           const std::shared_ptr<deepracer_interfaces_pkg::srv::GetCalibrationSrv::Request> req,
                           std::shared_ptr<deepracer_interfaces_pkg::srv::GetCalibrationSrv::Response> res);


        private:
            /// Writes the given calibration map to file
            /// @param calibrationMap Calibration file to write to file
            /// @param filePath Full path to the desired file for which to write the given calibration map.
            void writeCalJSON(const std::unordered_map<int, std::unordered_map<std::string, int>> &calibrationMap,
                            const std::string &filePath);

            /// Reads the calibration from the desired file and stores the values in memory
            /// @param calibrationMap Map to store the calibrations read from file
            /// @param filePath Full file path of the file containing the calibrations, note the client verifies existence
            void setCalFromFile(std::unordered_map<int, std::unordered_map<std::string, int>> &calibrationMap,
                                const std::string &filePath);

            /// Performs the calibration on the servo so that if the servo is turned on it can calibrate properly.
            /// @param pinNum GPIO pin number to enable or disable
            /// @param pinVal Enable/disable value for the servo, should be 0 or 1.
            bool calibrateServo(int pinNum, int pinVal) const ;

            /// Pointer to the throttle servo
            std::unique_ptr<Servo> throttle_;
            /// Ponter to the steering servo.
            std::unique_ptr<Servo> angle_;
            /// Hash map that stores the min/max of each servo.
            std::unordered_map<int, std::unordered_map<std::string, int>> calibrationMap_;
            /// ROS Logger object to log messages.
	        rclcpp::Logger logger_;
            /// ROS Clock object to get the current time.
            std::shared_ptr<rclcpp::Clock> clock_;
            /// ROS Publisher for latency measure
            std::shared_ptr<rclcpp::Publisher<deepracer_interfaces_pkg::msg::LatencyMeasureMsg, std::allocator<void>>> latencyPub_;
    };
}
#endif
