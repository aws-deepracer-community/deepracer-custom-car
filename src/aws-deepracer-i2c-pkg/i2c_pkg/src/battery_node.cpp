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
#include <filesystem>
#include "i2c_pkg/i2c.hpp"
#include "deepracer_interfaces_pkg/srv/battery_level_srv.hpp"


namespace BoardChips {
    // The following battery dev id and addresses were given by pegatron.
    #define BATDEV "0000:00:17.3"
    #define SYSPATH "/sys/class/i2c-dev/"
    #define SLAVE_ADDR 0x3f
    #define REGISTER_ADDR 0x03
    // The level conversion was given by pegatron, we may have more fidelity.
    // Implemented as vector for in order iteration.
    std::vector<std::pair<uint8_t, int>> levelMap = { {0xec, 11},
                                                      {0xe0, 10},
                                                      {0xd9, 9},
                                                      {0xd3, 8},
                                                      {0xcf, 7},
                                                      {0xcb, 6},
                                                      {0xc8, 5},
                                                      {0xc5, 4},
                                                      {0xc3, 3},
                                                      {0xc0, 2},
                                                      {0xb4, 1},
                                                      {0x8c, 0} };
    class BatteryNodeMgr : public rclcpp::Node
    {
    public:
        BatteryNodeMgr(const std::string & nodeName)
        : Node(nodeName),
          level_(-1),
          busChannel_(getBusChannel()),
          batteryPin_(BoardChips::I2C(busChannel_, SLAVE_ADDR, this->get_logger()))
        {
            RCLCPP_INFO(this->get_logger(), "Battery bus channel: %d", busChannel_);
            RCLCPP_INFO(this->get_logger(), "%s started", nodeName.c_str());
            monitorBatteryService_ = this->create_service<deepracer_interfaces_pkg::srv::BatteryLevelSrv>("battery_level", std::bind(&BatteryNodeMgr::getBatteryLevel, this, std::placeholders::_1, std::placeholders::_2, std::placeholders::_3));
        }
        ~BatteryNodeMgr() = default;
    private:
        /// Rewriting the command to dynamically find the bus channel number
        // "ls -al /sys/class/i2c-dev/ | grep "0000:00:17.3" | awk '{ print $9}' | awk -F "-" '{ print $2}'"
        uint8_t getBusChannel(){
            #if defined(HW_PLATFORM_RPI4) || defined(HW_PLATFORM_RPI5)
                uint8_t busChannel = 1; // For Raspberry Pi 4/5
            #elif defined(HW_PLATFORM_DR)
                uint8_t busChannel = 7; // Default for DeepRacer (DR)
            #else
                uint8_t busChannel = 0; // Default for other platforms
            #endif

            // Try to dynamically discover bus channel if available
            for (const auto & entry : std::filesystem::directory_iterator(SYSPATH)){
                auto filepath = entry.path();
                // grep "0000:00:17.3" 
                if(std::filesystem::exists(filepath) && std::filesystem::is_symlink(filepath)){
                    std::string symlinkTarget = std::filesystem::read_symlink(filepath).c_str();
                    if (symlinkTarget.find(BATDEV) != std::string::npos) {
                        auto tmp = symlinkTarget;
                        std::string delimiter = "/";
                        size_t pos = 0;
                        std::string token;
                        size_t tokenCount = 0;
                        // awk '{ print $9}'
                        while ((pos = tmp.find(delimiter)) != std::string::npos && tokenCount < 8) {
                            tmp.erase(0, pos + delimiter.length());
                            tokenCount++;
                        }
                        // awk -F "-" '{ print $2}'
                        delimiter = "-";
                        if ((pos = tmp.find(delimiter)) != std::string::npos) {
                            tmp.erase(0, pos + delimiter.length());
                        }
                        busChannel = std::stoi(tmp);
                    }
                }
            }
            return busChannel;
        }


        void getBatteryLevel (const std::shared_ptr<rmw_request_id_t> request_header,
                              const std::shared_ptr<deepracer_interfaces_pkg::srv::BatteryLevelSrv::Request> req,
                              std::shared_ptr<deepracer_interfaces_pkg::srv::BatteryLevelSrv::Response> res) {
            (void)request_header;
            (void) req;
            int levelByte = batteryPin_.readByte(REGISTER_ADDR);

            level_ = -1;
            if(levelByte != -1){
                for (const auto& pair : levelMap) {
                    if (levelByte >= pair.first) {
                        level_ = pair.second;
                        break;
                    }
                }
            }

            RCLCPP_INFO(this->get_logger(), "Current battery_life byte:0x%x level:%d", levelByte, level_);
            res->level = level_;
        }
        rclcpp::Service<deepracer_interfaces_pkg::srv::BatteryLevelSrv>::SharedPtr monitorBatteryService_;
        int level_;
        uint8_t busChannel_;
        BoardChips::I2C batteryPin_;
    };
}



int main(int argc, char * argv[])
{
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<BoardChips::BatteryNodeMgr>("battery_node"));
    rclcpp::shutdown();
    return 0;
}