//////////////////////////////////////////////////////////////////////////////////
//   Copyright AWS DeepRacer Community. All Rights Reserved.                     //
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
//////////////////////////////////////////////////////////////////////////////////

#ifndef LOGGING_NODE_HPP
#define LOGGING_NODE_HPP

#include <memory>
#include <string>
#include <vector>
#include <map>
#include <mutex>
#include <atomic>
#include <chrono>

#include "rclcpp/rclcpp.hpp"
#include "rosbag2_cpp/writer.hpp"
#include "rosbag2_cpp/writers/sequential_writer.hpp"
#include "rosbag2_storage/storage_options.hpp"
#include "std_msgs/msg/string.hpp"
#include "std_srvs/srv/trigger.hpp"
#include "deepracer_interfaces_pkg/srv/usb_file_system_subscribe_srv.hpp"
#include "deepracer_interfaces_pkg/srv/usb_mount_point_manager_srv.hpp"
#include "deepracer_interfaces_pkg/msg/usb_file_system_notification_msg.hpp"

namespace logging_pkg {

// Constants
namespace constants {
    // USB File System services
    const std::string USB_FILE_SYSTEM_NOTIFICATION_TOPIC = "/usb_monitor_pkg/usb_file_system_notification";
    const std::string USB_FILE_SYSTEM_SUBSCRIBE_SERVICE_NAME = "/usb_monitor_pkg/usb_file_system_subscribe";
    const std::string USB_MOUNT_POINT_MANAGER_SERVICE_NAME = "/usb_monitor_pkg/usb_mount_point_manager";

    // Output
    const std::string LOGS_DEFAULT_FOLDER = "/opt/aws/deepracer/logs";
    const std::string LOGS_SOURCE_LEAF_DIRECTORY = "logs";
    const std::string LOGS_DIR_CB = "logs_dir_cb";
    const std::string LOGS_BAG_FOLDER_NAME_PATTERN = "{}-{}";

    // Pause after force stop
    const double PAUSE_AFTER_FORCE_STOP = 10.0;

    // Naming
    const std::string DEFAULT_BAG_NAME = "deepracer";
}

// Recording state enum
enum class RecordingState {
    STOPPED = 0,
    RUNNING = 1,
    STOPPING = 2
};

// Node state enum
enum class NodeState {
    STARTING = 0,
    SCANNING = 1,
    RUNNING = 2,
    ERROR = 3
};

// Logging mode enum
enum class LoggingMode {
    NEVER = 0,
    USB_ONLY = 1,
    ALWAYS = 2
};

// Topic info structure
struct TopicInfo {
    std::string name;
    std::string type;
    std::string serialization_format;
    rclcpp::QoS qos{10};  // Default constructor with history depth
};

class BagLogNode : public rclcpp::Node {
public:
    BagLogNode();
    virtual ~BagLogNode();

private:
    // Initialization
    void setup_subscriptions_and_services();
    
    // Timer callbacks
    void scan_for_topics_cb();
    void timeout_check_timer_cb();
    
    // Subscription callbacks
    void file_name_cb(const std_msgs::msg::String::SharedPtr filename_msg);
    void usb_file_system_notification_cb(
        const deepracer_interfaces_pkg::msg::USBFileSystemNotificationMsg::SharedPtr notification_msg);
    void receive_topic_callback(
        std::shared_ptr<rclcpp::SerializedMessage> msg,
        const std::string& topic_name);
    
    // Service callbacks
    void stop_logging_cb(
        const std::shared_ptr<std_srvs::srv::Trigger::Request> request,
        std::shared_ptr<std_srvs::srv::Trigger::Response> response);
    
    // State management
    void change_state();
    void start_bag();
    void stop_bag();
    
    // Topic management
    void create_subscription_for_topic(const TopicInfo& topic_info);
    void create_topic_in_bag(const TopicInfo& topic_info);
    
    // Helper methods
    std::string format_bag_path(const std::string& bag_name);
    LoggingMode string_to_logging_mode(const std::string& mode_str);
    
    // Member variables - Parameters
    std::string output_path_;
    bool disable_usb_monitor_;
    LoggingMode logging_mode_;
    std::string monitor_topic_;
    std::string file_name_topic_;
    int monitor_topic_timeout_;
    std::vector<std::string> log_topics_;
    std::string logging_provider_;
    
    // Member variables - State
    std::atomic<RecordingState> target_edit_state_{RecordingState::STOPPED};
    std::atomic<NodeState> state_{NodeState::STARTING};
    std::atomic<bool> shutdown_{false};
    std::string bag_name_;
    std::chrono::steady_clock::time_point pause_until_;
    rclcpp::Time monitor_last_received_;
    
    // Member variables - Topics
    std::vector<std::string> topics_to_scan_;
    std::vector<TopicInfo> topics_type_info_;
    std::map<std::string, rclcpp::GenericSubscription::SharedPtr> topic_subscriptions_;
    
    // Member variables - Bag recording
    std::unique_ptr<rosbag2_cpp::Writer> bag_writer_;
    std::mutex bag_lock_;
    int topic_counter_{0};
    
    // ROS members - Callback groups
    rclcpp::CallbackGroup::SharedPtr main_cbg_;
    rclcpp::CallbackGroup::SharedPtr st_cbg_;
    rclcpp::CallbackGroup::SharedPtr usb_sub_cb_group_;
    rclcpp::CallbackGroup::SharedPtr usb_mpm_cb_group_;
    rclcpp::CallbackGroup::SharedPtr usb_notif_cb_group_;
    
    // ROS members - Timers
    rclcpp::TimerBase::SharedPtr scan_timer_;
    rclcpp::TimerBase::SharedPtr timeout_check_timer_;
    
    // ROS members - Subscriptions
    rclcpp::Subscription<std_msgs::msg::String>::SharedPtr file_name_sub_;
    rclcpp::Subscription<deepracer_interfaces_pkg::msg::USBFileSystemNotificationMsg>::SharedPtr 
        usb_file_system_notification_sub_;
    
    // ROS members - Services
    rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr stop_logging_svc_;
    
    // ROS members - Service clients
    rclcpp::Client<deepracer_interfaces_pkg::srv::USBFileSystemSubscribeSrv>::SharedPtr 
        usb_file_system_subscribe_client_;
    rclcpp::Client<deepracer_interfaces_pkg::srv::USBMountPointManagerSrv>::SharedPtr 
        usb_mount_point_manager_client_;
};

}  // namespace logging_pkg

#endif  // LOGGING_NODE_HPP
