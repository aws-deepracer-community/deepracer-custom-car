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

#include "servo_pkg/pwm.hpp"
#include <filesystem>
#include <fstream>
#include <array>
#include <memory>
#include <cstdio>

#if defined(HW_PLATFORM_RPI)
#define PWMDEVICE "i2c-1"
#else
#define PWMDEVICE "i2c-0"
#endif

namespace PWM
{
    /// Max size of the character buffer used to concat the file paths.
    constexpr char BASE_SYS_PATH[] = "/sys/class/pwm/";

    /// Helper method that writes the given value into a specified path.
    /// @param path Path to the file where the value is to be written.
    /// @param value Value to write in the file given by path.
    /// @param logger ROS logger to report errors
    /// @return true if successful, false otherwise
    bool writePWM(const std::string &path, int value, const rclcpp::Logger &logger)
    {
        std::ofstream file(path);
        if (!file)
        {
            RCLCPP_ERROR(logger, "Failed to open: %s", path.c_str());
            return false;
        }
        file << value;
        return file.good();
    }

    /// Function to find the pwmchip directory associated with i2c-0/i2c-1
    /// @param logger ROS logger to report errors
    /// @returns Syspath pointing to the pwmchip directory.
    std::string getSysPath(const rclcpp::Logger &logger = rclcpp::get_logger("pwm"))
    {
        namespace fs = std::filesystem;

        try
        {
            // Scan all PWM chips to find the one associated with i2c-1
            for (const auto &entry : fs::directory_iterator(BASE_SYS_PATH))
            {
                if (entry.is_directory())
                {
                    std::string chipName = entry.path().filename().string();
                    if (chipName.find("pwmchip") == 0)
                    {
                        // Read the symlink to check if it contains i2c-0/i2c-1
                        std::string symlinkPath = entry.path().string();
                        if (fs::is_symlink(symlinkPath))
                        {
                            std::string target = fs::read_symlink(symlinkPath);
                            if (target.find(PWMDEVICE) != std::string::npos)
                            {
                                RCLCPP_INFO(logger, "Found PWM chip: %s", chipName.c_str());
                                return symlinkPath;
                            }
                        }
                    }
                }
            }

            // If we reach here, no PWM chip was found
            throw std::runtime_error("No PWM chip associated with " + std::string(PWMDEVICE) + " found in " + std::string(BASE_SYS_PATH));
        }
        catch (const std::exception &e)
        {
            RCLCPP_ERROR(logger, "Failed to find PWM chip: %s", e.what());
            throw;
        }
    }

    Servo::Servo(int channel, rclcpp::Logger logger)
        : channel_(channel),
          period_(0),
          duty_(0),
          logger_(logger),
          syspath_(getSysPath(logger_))
    {
        RCLCPP_INFO(logger_, "Servo syspath: %s", syspath_.c_str());

        // Export the PWM if it is not already exported
        std::string exportPath = syspath_ + "/pwm" + std::to_string(channel_);

        if (std::filesystem::exists(exportPath))
        {
            RCLCPP_INFO(logger_, "Servo channel %d has already been exported", channel_);
            return;
        }

        writePWM(syspath_ + "/export", channel_, logger_);
    }

    /// Setter for the PWM period.
    /// @param period Desired period in ms.
    void Servo::setPeriod(int period)
    {
        std::string periodPath = syspath_ + "/pwm" + std::to_string(channel_) + "/period";
        // Read current value
        int currentPeriod = -1;
        std::ifstream file(periodPath);
        if (file)
        {
            file >> currentPeriod;
        }
        // Only write if different
        if (currentPeriod != period)
        {
            if (writePWM(periodPath, period, logger_))
            {
                period_ = period;
            }
            // Wait for one period to ensure the value is written
            if (period > 0)
            {
                std::this_thread::sleep_for(std::chrono::nanoseconds(period));
            }
        }
        else
        {
            RCLCPP_INFO(logger_, "Period is already set to %d", period);
        }
    }

    /// Setter for the duty cycle, this is what determines how much the servo actuates.
    /// @param duty Desired duty cycle.
    void Servo::setDuty(int duty)
    {
        std::string dutyPath = syspath_ + "/pwm" + std::to_string(channel_) + "/duty_cycle";
        if (writePWM(dutyPath, duty, logger_))
        {
            duty_ = duty;
        }
    }

    /// @returns Current value of the period.
    int Servo::getPeriod() const
    {
        return period_;
    }

    /// @returns Current value of the duty cycle.
    int Servo::getDuty() const
    {
        return duty_;
    }
}
