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

#ifndef PWM_HPP
#define PWM_HPP

#include <filesystem>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>

#include "rclcpp/rclcpp.hpp"

namespace PWM {
    class Servo
    {
    public:
        /// @param channel Servo channel for which to send the PWM signal's to.
        Servo(int channel, rclcpp::Logger logger_);
        ~Servo() = default;
        /// Setter for the PWM period.
        /// @param period Desired period in ms.
        void setPeriod(int period);
        /// Setter for the duty cycle, this is what determines how much the servo actuates.
        /// @param Desired duty cycle.
        void setDuty(int duty);
        /// @returns Current value of the period.
        int getPeriod() const;
        /// @returns Current value of the duty cycle.
        int getDuty() const;

    private:
        /// Channel that the pwm is being written to.
        int channel_;
        /// Current value of the period in ms.
        int period_;
        /// Current value of the duty cycle.
        int duty_;
        /// ROS Logger object to log messages.
    	rclcpp::Logger logger_;
        /// Dynamically assigned syspath
        std::string syspath_;
    };
}
#endif
