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

#include "servo_pkg/servo_mgr.hpp"

namespace PWM {

    // Path to calibration file
    const std::string CAL_PATH = "/opt/aws/deepracer/calibration.json";

    // Location of the bios version on Ubuntu
    const std::string BIOS_PATH = "/sys/class/dmi/id/bios_version";

    // Keys for the calibration file
    const std::string HEADER_KEY = "Calibration";
    const std::string SERVO_KEY = "Servo";
    const std::string MOTOR_KEY = "Motor";
    const std::string MIN_KEY = "min";
    const std::string MID_KEY = "mid";
    const std::string MAX_KEY = "max";
    const std::string POLARITY_KEY = "polarity";
    const std::string VERSION_KEY = "version";


    // Enumeration for calibration type
    enum ServoCal {
        servo,
        motor
    };


    ServoMgr::ServoMgr(rclcpp::Logger logger_, std::shared_ptr<rclcpp::Clock> clock,
                       std::shared_ptr<rclcpp::Publisher<deepracer_interfaces_pkg::msg::LatencyMeasure, std::allocator<void>>> latencyPub)  
        : throttle_(std::make_unique<Servo>(0, logger_)),
          angle_(std::make_unique<Servo>(1, logger_)),
	      logger_(logger_),
          clock_(clock),
          latencyPub_(latencyPub)
    {
        throttle_->setPeriod(SERVO_PERIOD);
        angle_->setPeriod(SERVO_PERIOD);

        calibrationMap_ = {{servo, {{MAX_KEY, SERVO_MAX},{MID_KEY, SERVO_MID},
                                    {MIN_KEY, SERVO_MIN}, {POLARITY_KEY, POLARITY_SERVO_VAL}}},
                            {motor, {{MAX_KEY, MOTOR_MAX},{MID_KEY, MOTOR_MID},
                                    {MIN_KEY, MOTOR_MIN}, {POLARITY_KEY, POLARITY_MOTOR_VAL}}}};
        if (checkFile(CAL_PATH)) {
            setCalFromFile(calibrationMap_, CAL_PATH);
        }
        else {
            writeCalJSON(calibrationMap_, CAL_PATH);
        }
    }

    ServoMgr::~ServoMgr() = default;
    
    /// Subscriber for request made to the servo server.
    void ServoMgr::servoSubscriber(const deepracer_interfaces_pkg::msg::ServoCtrlMsg::SharedPtr servoMsg) {
        auto setPWM = [&](auto &servo, auto value, auto type) {
            if (value < -1.0 || value > 1.0) {
                RCLCPP_ERROR(logger_, "Invalid servo request: %f", value);
                return;
            }

            auto itCal = calibrationMap_.find(type);
            if (itCal == calibrationMap_.end()) {
                RCLCPP_ERROR(logger_, "Invalid calibration type");
                return;
            }
            auto itMin = itCal->second.find(MIN_KEY);
            auto itMid = itCal->second.find(MID_KEY);
            auto itMax = itCal->second.find(MAX_KEY);
            auto itPolar = itCal->second.find(POLARITY_KEY);

            if (itMin != itCal->second.end() && itMid != itCal->second.end() 
                && itMax != itCal->second.end() && itPolar != itCal->second.end()) {
                float adjVal = value * itPolar->second;
                if (adjVal < 0) {
                    servo->setDuty(itMid->second + adjVal * (itMid->second - itMin->second));
                }
                else if (adjVal > 0) {
                        servo->setDuty(itMid->second + adjVal * (itMax->second - itMid->second));
                }
                else {
                    servo->setDuty(itMid->second);
                }
            }
            else {
                RCLCPP_ERROR(logger_, "Invalid calibrations");
            }
        };

        setPWM(throttle_, servoMsg->throttle, motor);
        setPWM(angle_, servoMsg->angle, servo);
        auto now = clock_->now();
        
        // If there is a soruce_stamp and a subsccription count, publish the latency message
        if (servoMsg->source_stamp.sec != 0 && latencyPub_->get_subscription_count() > 0) {
            auto latency_msg = deepracer_interfaces_pkg::msg::LatencyMeasure();
            latency_msg.send = servoMsg->source_stamp;
            latency_msg.receive = now;
            latencyPub_->publish(latency_msg);
        } 

        // Sleep until 20ms has elapsed since 'now'
        const int TARGET_CYCLE_TIME_NS = 20'000'000; // 20 ms in nanoseconds
        auto elapsed_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
            (clock_->now() - now).to_chrono<std::chrono::nanoseconds>()).count();

        if (elapsed_ns < TARGET_CYCLE_TIME_NS) {
            std::this_thread::sleep_for(std::chrono::nanoseconds(TARGET_CYCLE_TIME_NS - elapsed_ns));
        }
    }

    /// Subscriber for setting the raw pwm topic.
    void ServoMgr::rawPWMSubscriber(const deepracer_interfaces_pkg::msg::ServoCtrlMsg::SharedPtr servoMsg) {
        if (servoMsg->throttle >= 0 && servoMsg->throttle <= SERVO_PERIOD) {
            throttle_->setDuty(servoMsg->throttle);
        }
        if (servoMsg->angle >= 0 && servoMsg->angle <= SERVO_PERIOD) {
            angle_->setDuty(servoMsg->angle);
        }
        std::this_thread::sleep_for(std::chrono::nanoseconds(SERVO_PERIOD));
    }

    /// Handler for setting the min and max value of the servos.
    void ServoMgr::setCalHdl(const std::shared_ptr<rmw_request_id_t> request_header,
                             const std::shared_ptr<deepracer_interfaces_pkg::srv::SetCalibrationSrv::Request> req,
                             std::shared_ptr<deepracer_interfaces_pkg::srv::SetCalibrationSrv::Response> res) {
        (void)request_header;
        auto itCal = calibrationMap_.find(req->cal_type);

        if (itCal == calibrationMap_.end()) {
            RCLCPP_ERROR(logger_, "Invalid calibration type");
            res->error = 1;
            return;
        }

        auto itMin = itCal->second.find(MIN_KEY);
        auto itMid = itCal->second.find(MID_KEY);
        auto itMax = itCal->second.find(MAX_KEY);
        auto itPolar = itCal->second.find(POLARITY_KEY);

        if (itMin != itCal->second.end() && itMid != itCal->second.end() 
            && itMax != itCal->second.end() && itPolar != itCal->second.end()) {

            itMin->second = req->min;
            itMid->second = req->mid;
            itMax->second = req->max;
            itPolar->second = req->polarity;

            writeCalJSON(calibrationMap_, CAL_PATH);
            res->error = 0;
        }
        else {
            RCLCPP_ERROR(logger_, "Invalid calibration fields");
            res->error = 1;
        }
    }
    /// Handeler for seeting the servo GPIO pin to disable/enable.
    void ServoMgr::setGPIOHdl(const std::shared_ptr<rmw_request_id_t> request_header,
                              const std::shared_ptr<deepracer_interfaces_pkg::srv::ServoGPIOSrv::Request> req,
                              std::shared_ptr<deepracer_interfaces_pkg::srv::ServoGPIOSrv::Response> res) {

        (void)request_header;
        bool ret = calibrateServo(GPIO_CHANNEL, req->enable);
        res->error = ret ? 0 : 1;
    }
    /// Handler for get calibration request
    void ServoMgr::getCalHdl(const std::shared_ptr<rmw_request_id_t> request_header,
                             const std::shared_ptr<deepracer_interfaces_pkg::srv::GetCalibrationSrv::Request> req,
                             std::shared_ptr<deepracer_interfaces_pkg::srv::GetCalibrationSrv::Response> res) {

        (void)request_header;
        auto itCal = calibrationMap_.find(req->cal_type);

        if (itCal == calibrationMap_.end()) {
            RCLCPP_ERROR(logger_, "Invalid calibration type");
            res->error = 1;
            return;
        }

        auto itMin = itCal->second.find(MIN_KEY);
        auto itMid = itCal->second.find(MID_KEY);
        auto itMax = itCal->second.find(MAX_KEY);
        auto itPolar = itCal->second.find(POLARITY_KEY);
        
        if (itMin != itCal->second.end() && itMid != itCal->second.end() 
            && itMax != itCal->second.end() && itPolar != itCal->second.end()) {
            RCLCPP_INFO(logger_, "Calibration values: Min: %d, Mid: %d, Max: %d, Polarity: %d", itMin->second, itMid->second, itMax->second, itPolar->second );
            res->min = itMin->second;
            res->mid = itMid->second;
            res->max = itMax->second;
            res->polarity = itPolar->second;
            res->error = 0;
        }
        else {
            RCLCPP_ERROR(logger_, "Invalid calibration fields");
            res->error = 1;
        }
    }

    /// Writes the given calibration map to file
    /// @param calibrationMap Calibration file to write to file
    /// @param filePath Full path to the desired file for which to write the given calibration map.
    void ServoMgr::writeCalJSON(const std::unordered_map<int, std::unordered_map<std::string, int>> &calibrationMap,
                    const std::string &filePath) {
        Json::Value calJsonValue;

        auto itServo = calibrationMap.find(servo);
        auto itMotor = calibrationMap.find(motor);

        if (itServo != calibrationMap.end() && itMotor != calibrationMap.end()) {
            for (auto servoMap : itServo->second) {
                calJsonValue[HEADER_KEY][SERVO_KEY][servoMap.first] = servoMap.second;
            }
        for (auto motorMap : itMotor->second) {
                calJsonValue[HEADER_KEY][MOTOR_KEY][motorMap.first] = motorMap.second;
            }
        calJsonValue[HEADER_KEY][VERSION_KEY] = CAL_FILE_VERSION;
        }
        else {
            RCLCPP_ERROR(logger_, "Invalid calibration map");
            return;
        }
        writeJSONToFile(calJsonValue, filePath);
    }

    /// Reads the calibration from the desired file and stores the values in memory
    /// @param calibrationMap Map to store the calibrations read from file
    /// @param filePath Full file path of the file containing the calibrations, note the client verifies existence
    void ServoMgr::setCalFromFile(std::unordered_map<int, std::unordered_map<std::string, int>> &calibrationMap,
                        const std::string &filePath) {
        Json::Value calJsonValue;
        Json::Reader reader;
        std::ifstream ifs(filePath);

        if (!reader.parse(ifs, calJsonValue)) {
            RCLCPP_ERROR(logger_, "Error parsing calibration.json");
            return;
        }
        if (!calJsonValue.isMember("Calibration")) {
            RCLCPP_ERROR(logger_, "Calibration file error: No calibration header");
            return;
        }
        if (!calJsonValue[HEADER_KEY].isMember(SERVO_KEY) || !calJsonValue[HEADER_KEY].isMember(MOTOR_KEY)) {
            RCLCPP_ERROR(logger_, "Calibration file error: Missing servo type");
            return;
        }

        std::string biosVersion;
        std::ifstream bioFile(BIOS_PATH);

        if(bioFile.is_open()) {
            std::getline (bioFile, biosVersion);
            bioFile.close();
        }
        else {
            RCLCPP_WARN(logger_, "Unable to read bios version, vechile needs to be calibrated");
        }

        if (BiosVersion(biosVersion, logger_) >= BiosVersion(BIOS_CUT_OFF, logger_)) {
            if (!calJsonValue[HEADER_KEY].isMember(VERSION_KEY)) {
                RCLCPP_INFO(logger_, "Old calibration file detected");
                writeCalJSON(calibrationMap, filePath);
                return;
            }
        }

        auto populateMap = [&](auto &map, const auto &servoType) {
            for (auto &servoMap : map) {
                if (calJsonValue[HEADER_KEY][servoType].isMember(servoMap.first)) {
                    servoMap.second = calJsonValue["Calibration"][servoType][servoMap.first].asInt();
                }
                else {
                    RCLCPP_ERROR(logger_, "Calibration file error:%s missing: %s", servoType.c_str(), servoMap.first.c_str());
                    return false;
                }
            }
            return true;
        };

        auto tmpMap = calibrationMap;
        auto itServo = tmpMap.find(servo);
        auto itMotor = tmpMap.find(motor);

        if (itServo != tmpMap.end() && itMotor != tmpMap.end()) {
            if (!populateMap(itServo->second, SERVO_KEY) || !populateMap(itMotor->second, MOTOR_KEY)) {
                return;
            }
        }
        else {
            RCLCPP_ERROR(logger_, "Invalid calibration map");
            return;
        }
        calibrationMap = tmpMap;
    }


    /// Performs the calibration on the servo so that if the servo is turned on it can calibrate properly.
    /// @param pinNum GPIO pin number to enable or disable
    /// @param pinVal Enable/disable value for the servo, should be 0 or 1.
    bool ServoMgr::calibrateServo(int pinNum, int pinVal) const {

        if (pinVal > 1 || pinVal < 0 || pinNum < 0) {
            RCLCPP_ERROR(logger_, "Invalid pin values");
            return false;
        }

        const int MAX_BUF = 64;
        auto writeGPIO = [&](const std::string &path, int pinNum,
                                const std::string &value) {
            char pinBuff[MAX_BUF];
            snprintf(pinBuff, sizeof(pinBuff), path.c_str(), pinNum);
            RCLCPP_INFO(logger_,"%s", value.c_str());
            int fd = open(pinBuff, O_WRONLY);
            if (fd < 0) {
                RCLCPP_ERROR(logger_, "Failed to open: %s", path.c_str());
                return false;
            }
            char valueBuff[MAX_BUF];
            write(fd, valueBuff, snprintf(valueBuff, sizeof(valueBuff),
                                            "%s", value.c_str()));
            close(fd);
            return true;
        };
        bool ret = true;
        // Open the pin path and check its existence, if not create it.
        char buff[MAX_BUF];
        snprintf(buff, sizeof(buff), "/sys/class/gpio/gpio%d", pinNum);
        int gpioFd = open(buff, O_WRONLY);
        if (gpioFd < 0) {
            // Open the export path to export the pin.
            ret = ret && writeGPIO("/sys/class/gpio/export", pinNum, std::to_string(pinNum));
        }
        else {
            close(gpioFd);
        }
        // Write the direction, it is always "out"
        ret = ret && writeGPIO("/sys/class/gpio/gpio%d/direction", pinNum, "out");
        // Set the value, 0 for enable and 1 for disable.
        ret = ret && writeGPIO("/sys/class/gpio/gpio%d/value", pinNum, std::to_string(pinVal));

        memset(buff, 0, sizeof(buff));
        snprintf(buff, sizeof(buff), "/sys/class/gpio/gpio%d/value", pinNum);
        chmod(buff, S_IRUSR | S_IWUSR | S_IRGRP | S_IWGRP | S_IROTH | S_IWOTH);

        return ret;
    }
}
