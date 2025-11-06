//////////////////////////////////////////////////////////////////////////////////
//   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.          //
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

#include "bag_log_pkg/bag_log_node.hpp"
#include <filesystem>
#include <iomanip>
#include <sstream>
#include <algorithm>

namespace bag_log_pkg {

BagLogNode::BagLogNode()
    : Node("bag_log_node"),
      pause_until_(std::chrono::steady_clock::now())
{
    // Declare parameters
    this->declare_parameter<std::string>("output_path", constants::LOGS_DEFAULT_FOLDER);
    this->declare_parameter<bool>("disable_usb_monitor", false);
    this->declare_parameter<std::string>("logging_mode", "Always");
    this->declare_parameter<std::string>("monitor_topic", "/inference_pkg/rl_results");
    this->declare_parameter<std::string>("file_name_topic", "/inference_pkg/model_name");
    this->declare_parameter<int>("monitor_topic_timeout", 15);
    this->declare_parameter<std::vector<std::string>>("log_topics", std::vector<std::string>{"/ctrl_pkg/servo_msg"});
    this->declare_parameter<std::string>("logging_provider", "sqlite3");
    
    // Get parameters
    output_path_ = this->get_parameter("output_path").as_string();
    disable_usb_monitor_ = this->get_parameter("disable_usb_monitor").as_bool();
    std::string logging_mode_str = this->get_parameter("logging_mode").as_string();
    logging_mode_ = string_to_logging_mode(logging_mode_str);
    monitor_topic_ = this->get_parameter("monitor_topic").as_string();
    file_name_topic_ = this->get_parameter("file_name_topic").as_string();
    monitor_topic_timeout_ = this->get_parameter("monitor_topic_timeout").as_int();
    log_topics_ = this->get_parameter("log_topics").as_string_array();
    logging_provider_ = this->get_parameter("logging_provider").as_string();
    
    // Initialize state
    bag_name_ = constants::DEFAULT_BAG_NAME;
    monitor_last_received_ = this->now();
    
    // Setup topics to scan
    topics_to_scan_ = log_topics_;
    topics_to_scan_.erase(
        std::remove(topics_to_scan_.begin(), topics_to_scan_.end(), monitor_topic_),
        topics_to_scan_.end());
    
    // Setup subscriptions and services
    setup_subscriptions_and_services();
    
    RCLCPP_INFO(this->get_logger(), 
                "Node started. Mode '%s'. Provider '%s'. Monitor '%s'. Additionally logging %zu topics.",
                logging_mode_str.c_str(), logging_provider_.c_str(), monitor_topic_.c_str(), 
                topics_to_scan_.size());
}

BagLogNode::~BagLogNode()
{
    RCLCPP_INFO(this->get_logger(), "Stopping the node.");
    
    shutdown_ = true;
    
    if (target_edit_state_ == RecordingState::RUNNING) {
        stop_bag();
    }
    
    topic_subscriptions_.clear();
    
    RCLCPP_INFO(this->get_logger(), "Node cleanup done. Exiting.");
}

void BagLogNode::setup_subscriptions_and_services()
{
    // Create callback groups
    main_cbg_ = this->create_callback_group(rclcpp::CallbackGroupType::Reentrant);
    st_cbg_ = this->create_callback_group(rclcpp::CallbackGroupType::MutuallyExclusive);
    
    // Start scanning if logging mode is Always
    if (logging_mode_ == LoggingMode::ALWAYS) {
        state_ = NodeState::SCANNING;
        scan_timer_ = this->create_wall_timer(
            std::chrono::seconds(1),
            std::bind(&BagLogNode::scan_for_topics_cb, this),
            main_cbg_);
    }
    
    // Create subscription to file name topic
    auto file_name_sub_opt = rclcpp::SubscriptionOptions();
    file_name_sub_opt.callback_group = main_cbg_;
    file_name_sub_ = this->create_subscription<std_msgs::msg::String>(
        file_name_topic_,
        1,
        std::bind(&BagLogNode::file_name_cb, this, std::placeholders::_1),
        file_name_sub_opt);
    
    // Create stop logging service
    stop_logging_svc_ = this->create_service<std_srvs::srv::Trigger>(
        "stop_logging",
        std::bind(&BagLogNode::stop_logging_cb, this, std::placeholders::_1, std::placeholders::_2),
        rclcpp::ServicesQoS(),
        main_cbg_);
    
    // Setup USB monitoring if not disabled
    if (!disable_usb_monitor_) {
        usb_sub_cb_group_ = this->create_callback_group(rclcpp::CallbackGroupType::Reentrant);
        usb_mpm_cb_group_ = this->create_callback_group(rclcpp::CallbackGroupType::Reentrant);
        usb_notif_cb_group_ = this->create_callback_group(rclcpp::CallbackGroupType::Reentrant);
        
        // Create USB file system subscribe client
        usb_file_system_subscribe_client_ = 
            this->create_client<deepracer_interfaces_pkg::srv::USBFileSystemSubscribeSrv>(
                constants::USB_FILE_SYSTEM_SUBSCRIBE_SERVICE_NAME,
                rclcpp::ServicesQoS(),
                usb_sub_cb_group_);
        
        // Wait for service with timeout and cancellation check
        int wait_count = 0;
        while (!usb_file_system_subscribe_client_->wait_for_service(std::chrono::seconds(1))) {
            if (!rclcpp::ok()) {
                RCLCPP_WARN(this->get_logger(), "Interrupted while waiting for USB file system service.");
                return;
            }
            wait_count++;
            if (wait_count >= 5) {
                RCLCPP_WARN(this->get_logger(), "USB file system service not available after %d seconds, continuing anyway...", wait_count);
                break;
            }
            RCLCPP_INFO(this->get_logger(), "File System Subscribe not available, waiting again...");
        }
        
        // Create USB mount point manager client
        usb_mount_point_manager_client_ = 
            this->create_client<deepracer_interfaces_pkg::srv::USBMountPointManagerSrv>(
                constants::USB_MOUNT_POINT_MANAGER_SERVICE_NAME,
                rclcpp::ServicesQoS(),
                usb_mpm_cb_group_);
        
        // Wait for service
        while (!usb_mount_point_manager_client_->wait_for_service(std::chrono::seconds(1))) {
            if (!rclcpp::ok()) {
                RCLCPP_ERROR(this->get_logger(), "Interrupted while waiting for USB mount point service.");
                return;
            }
            RCLCPP_INFO(this->get_logger(), "USB mount point manager service not available, waiting again...");
        }
        
        // Create USB file system notification subscription
        auto usb_notif_sub_opt = rclcpp::SubscriptionOptions();
        usb_notif_sub_opt.callback_group = usb_notif_cb_group_;
        usb_file_system_notification_sub_ = 
            this->create_subscription<deepracer_interfaces_pkg::msg::USBFileSystemNotificationMsg>(
                constants::USB_FILE_SYSTEM_NOTIFICATION_TOPIC,
                10,
                std::bind(&BagLogNode::usb_file_system_notification_cb, this, std::placeholders::_1),
                usb_notif_sub_opt);
        
        // Subscribe to logs directory
        auto request = std::make_shared<deepracer_interfaces_pkg::srv::USBFileSystemSubscribeSrv::Request>();
        request->file_name = constants::LOGS_SOURCE_LEAF_DIRECTORY;
        request->callback_name = constants::LOGS_DIR_CB;
        request->verify_name_exists = true;
        
        usb_file_system_subscribe_client_->async_send_request(request);
    }
}

void BagLogNode::scan_for_topics_cb()
{
    try {
        if (state_ == NodeState::SCANNING) {
            // Get publishers for monitor topic
            auto topic_endpoints = this->get_publishers_info_by_topic(monitor_topic_);
            
            if (!topic_endpoints.empty()) {
                const auto& endpoint = topic_endpoints[0];
                
                TopicInfo topic_info;
                topic_info.name = monitor_topic_;
                topic_info.type = endpoint.topic_type();
                topic_info.serialization_format = "cdr";
                // Use keep_all history to record all messages
                topic_info.qos = rclcpp::QoS(rclcpp::KeepAll());
                
                create_subscription_for_topic(topic_info);
                
                // Setup timeout check timer
                timeout_check_timer_ = this->create_wall_timer(
                    std::chrono::milliseconds(monitor_topic_timeout_ * 100),
                    std::bind(&BagLogNode::timeout_check_timer_cb, this),
                    main_cbg_);
                
                RCLCPP_INFO(this->get_logger(), 
                            "Monitoring %s of type %s with timeout %d seconds",
                            monitor_topic_.c_str(), topic_info.type.c_str(), monitor_topic_timeout_);
                
                state_ = NodeState::RUNNING;
            }
        }
        
        // Scan for additional topics
        for (auto it = topics_to_scan_.begin(); it != topics_to_scan_.end(); ) {
            auto topic_endpoints = this->get_publishers_info_by_topic(*it);
            
            if (!topic_endpoints.empty()) {
                const auto& endpoint = topic_endpoints[0];
                
                TopicInfo topic_info;
                topic_info.name = *it;
                topic_info.type = endpoint.topic_type();
                topic_info.serialization_format = "cdr";
                // Use keep_all history to record all messages
                topic_info.qos = rclcpp::QoS(rclcpp::KeepAll());
                
                create_subscription_for_topic(topic_info);
                
                RCLCPP_INFO(this->get_logger(), "Logging %s of type %s.",
                            it->c_str(), topic_info.type.c_str());
                
                it = topics_to_scan_.erase(it);
            } else {
                ++it;
            }
        }
        
        if (state_ == NodeState::RUNNING && topics_to_scan_.empty()) {
            RCLCPP_INFO(this->get_logger(), "All topics found. %zu subscriptions active.",
                        topics_type_info_.size());
            scan_timer_->cancel();
        }
        
    } catch (const std::exception& e) {
        RCLCPP_ERROR(this->get_logger(), "Exception in scan_for_topics_cb: %s", e.what());
    }
}

void BagLogNode::create_subscription_for_topic(const TopicInfo& topic_info)
{
    auto sub_opt = rclcpp::SubscriptionOptions();
    sub_opt.callback_group = main_cbg_;
    
    auto subscription = this->create_generic_subscription(
        topic_info.name,
        topic_info.type,
        topic_info.qos,
        [this, topic_name = topic_info.name](std::shared_ptr<rclcpp::SerializedMessage> msg) {
            this->receive_topic_callback(msg, topic_name);
        },
        sub_opt);
    
    topic_subscriptions_[topic_info.name] = subscription;
    topics_type_info_.push_back(topic_info);
}

void BagLogNode::receive_topic_callback(
    std::shared_ptr<rclcpp::SerializedMessage> msg,
    const std::string& topic_name)
{
    try {
        auto time_recv = this->now();
        
        if (topic_name == monitor_topic_) {
            monitor_last_received_ = time_recv;
            
            if (target_edit_state_ == RecordingState::STOPPED) {
                auto now = std::chrono::steady_clock::now();
                if (now < pause_until_) {
                    return;
                }
                
                target_edit_state_ = RecordingState::RUNNING;
                change_state();
                RCLCPP_INFO(this->get_logger(), "Got callback from %s. Triggering start.",
                            monitor_topic_.c_str());
            }
        }
        
        // Write to bag if recording
        if (target_edit_state_ == RecordingState::RUNNING && bag_writer_) {
            std::lock_guard<std::mutex> lock(bag_lock_);
            bag_writer_->write(msg, topic_name, topic_name, time_recv);
        }
        
    } catch (const std::exception& e) {
        RCLCPP_ERROR(this->get_logger(), "Exception in receive_topic_callback: %s", e.what());
    }
}

void BagLogNode::timeout_check_timer_cb()
{
    try {
        auto dur_since_last_message = this->now() - monitor_last_received_;
        
        if (dur_since_last_message > rclcpp::Duration::from_seconds(monitor_topic_timeout_) &&
            target_edit_state_ == RecordingState::RUNNING) {
            target_edit_state_ = RecordingState::STOPPED;
            change_state();
            RCLCPP_INFO(this->get_logger(), "Timeout. Triggering stop of recording.");
        }
        
    } catch (const std::exception& e) {
        RCLCPP_ERROR(this->get_logger(), "Exception in timeout_check_timer_cb: %s", e.what());
    }
}

void BagLogNode::file_name_cb(const std_msgs::msg::String::SharedPtr filename_msg)
{
    try {
        if (target_edit_state_ == RecordingState::RUNNING) {
            target_edit_state_ = RecordingState::STOPPED;
            change_state();
            RCLCPP_INFO(this->get_logger(), "Received new file name. Triggering stop of recording.");
        }
        
        // Extract bag name from path
        std::filesystem::path p(filename_msg->data);
        if (p.has_parent_path()) {
            bag_name_ = p.parent_path().filename().string();
        } else {
            bag_name_ = filename_msg->data;
        }
        
        RCLCPP_INFO(this->get_logger(), "New filename received: %s -> %s",
                    filename_msg->data.c_str(), bag_name_.c_str());
        
    } catch (const std::exception& e) {
        RCLCPP_ERROR(this->get_logger(), "Exception in file_name_cb: %s", e.what());
    }
}

void BagLogNode::usb_file_system_notification_cb(
    const deepracer_interfaces_pkg::msg::USBFileSystemNotificationMsg::SharedPtr notification_msg)
{
    RCLCPP_INFO(this->get_logger(), "File system notification: %s %s %s %s",
                notification_msg->path.c_str(), notification_msg->file_name.c_str(),
                notification_msg->node_name.c_str(), notification_msg->callback_name.c_str());
    
    if (notification_msg->file_name == constants::LOGS_SOURCE_LEAF_DIRECTORY &&
        notification_msg->callback_name == constants::LOGS_DIR_CB) {
        output_path_ = (std::filesystem::path(notification_msg->path) / notification_msg->file_name).string();
        this->set_parameter(rclcpp::Parameter("output_path", output_path_));
        RCLCPP_INFO(this->get_logger(), "New output path: %s", output_path_.c_str());
    }
    
    if (logging_mode_ == LoggingMode::USB_ONLY && state_ == NodeState::STARTING) {
        RCLCPP_INFO(this->get_logger(), "USB folder mounted, starting scanning for topics.");
        state_ = NodeState::SCANNING;
        scan_timer_ = this->create_wall_timer(
            std::chrono::seconds(1),
            std::bind(&BagLogNode::scan_for_topics_cb, this),
            main_cbg_);
    }
}

void BagLogNode::stop_logging_cb(
    const std::shared_ptr<std_srvs::srv::Trigger::Request> request,
    std::shared_ptr<std_srvs::srv::Trigger::Response> response)
{
    (void)request;  // Unused
    
    try {
        response->success = true;
        pause_until_ = std::chrono::steady_clock::now() + 
                      std::chrono::seconds(static_cast<int>(constants::PAUSE_AFTER_FORCE_STOP));
        
        auto pause_time = std::chrono::system_clock::now() + 
                         std::chrono::seconds(static_cast<int>(constants::PAUSE_AFTER_FORCE_STOP));
        auto pause_time_t = std::chrono::system_clock::to_time_t(pause_time);
        std::stringstream ss;
        ss << std::put_time(std::localtime(&pause_time_t), "%H:%M:%S");
        
        if (target_edit_state_ == RecordingState::STOPPED) {
            response->message = "Logging already stopped. Pausing until " + ss.str() + ".";
            RCLCPP_INFO(this->get_logger(), "%s", response->message.c_str());
            return;
        }
        
        target_edit_state_ = RecordingState::STOPPED;
        response->message = "Logging stopped successfully. Pausing until " + ss.str() + ".";
        
        RCLCPP_INFO(this->get_logger(), "Stopping logging on service. Closing bag file. Pausing until %s.",
                    ss.str().c_str());
        change_state();
        
    } catch (const std::exception& e) {
        RCLCPP_ERROR(this->get_logger(), "Exception in stop_logging_cb: %s", e.what());
        response->success = false;
        response->message = std::string("Failed to stop logging: ") + e.what();
    }
}

void BagLogNode::change_state()
{
    if (!shutdown_) {
        try {
            std::string state_name = (target_edit_state_ == RecordingState::RUNNING) ? "RUNNING" : "STOPPED";
            RCLCPP_INFO(this->get_logger(), "Changing state to %s", state_name.c_str());
            
            if (target_edit_state_ == RecordingState::RUNNING) {
                start_bag();
            } else {
                stop_bag();
            }
            
        } catch (const std::exception& e) {
            RCLCPP_ERROR(this->get_logger(), "Exception in change_state: %s", e.what());
        }
    }
}

void BagLogNode::start_bag()
{
    try {
        std::lock_guard<std::mutex> lock(bag_lock_);
        
        if (bag_writer_) {
            RCLCPP_WARN(this->get_logger(), "Bag already open. Will not open again.");
            return;
        }
        
        // Create bag path
        std::string bag_path = format_bag_path(bag_name_);
        
        // Create output directory if it doesn't exist
        std::filesystem::create_directories(output_path_);
        
        // Setup storage options
        rosbag2_storage::StorageOptions storage_options;
        storage_options.uri = bag_path;
        storage_options.storage_id = logging_provider_;
        
        // Setup converter options
        rosbag2_cpp::ConverterOptions converter_options;
        converter_options.input_serialization_format = "cdr";
        converter_options.output_serialization_format = "cdr";
        
        // Create and open bag
        bag_writer_ = std::make_unique<rosbag2_cpp::Writer>();
        bag_writer_->open(storage_options, converter_options);
        
        // Create topics in bag
        for (const auto& topic_info : topics_type_info_) {
            create_topic_in_bag(topic_info);
        }
        
        RCLCPP_INFO(this->get_logger(), "Started recording to %s", bag_path.c_str());
        
    } catch (const std::exception& e) {
        RCLCPP_ERROR(this->get_logger(), "Exception in start_bag: %s", e.what());
        bag_writer_.reset();
    }
}

void BagLogNode::stop_bag()
{
    std::lock_guard<std::mutex> lock(bag_lock_);
    if (bag_writer_) {
        RCLCPP_INFO(this->get_logger(), "Stopping bag recording.");
        bag_writer_.reset();
        topic_counter_ = 0;
    }
}

void BagLogNode::create_topic_in_bag(const TopicInfo& topic_info)
{
    rosbag2_storage::TopicMetadata topic_metadata;
    topic_metadata.name = topic_info.name;
    topic_metadata.type = topic_info.type;
    topic_metadata.serialization_format = topic_info.serialization_format;
    
    bag_writer_->create_topic(topic_metadata);
    topic_counter_++;
}

std::string BagLogNode::format_bag_path(const std::string& bag_name)
{
    auto now = std::chrono::system_clock::now();
    auto now_t = std::chrono::system_clock::to_time_t(now);
    std::stringstream ss;
    ss << std::put_time(std::localtime(&now_t), "%Y%m%d-%H%M%S");
    
    std::filesystem::path output_dir(output_path_);
    std::filesystem::path bag_dir = output_dir / (bag_name + "-" + ss.str());
    
    return bag_dir.string();
}

LoggingMode BagLogNode::string_to_logging_mode(const std::string& mode_str)
{
    std::string lower_mode = mode_str;
    std::transform(lower_mode.begin(), lower_mode.end(), lower_mode.begin(), ::tolower);
    
    if (lower_mode == "never") return LoggingMode::NEVER;
    if (lower_mode == "usbonly") return LoggingMode::USB_ONLY;
    if (lower_mode == "always") return LoggingMode::ALWAYS;
    
    RCLCPP_WARN(this->get_logger(), "Unknown logging mode '%s', defaulting to ALWAYS", mode_str.c_str());
    return LoggingMode::ALWAYS;
}

}  // namespace bag_log_pkg

int main(int argc, char** argv)
{
    rclcpp::init(argc, argv);
    
    try {
        auto node = std::make_shared<bag_log_pkg::BagLogNode>();
        
        // Use MultiThreadedExecutor to handle callbacks in parallel
        rclcpp::executors::MultiThreadedExecutor executor;
        executor.add_node(node);
        executor.spin();
        
        rclcpp::shutdown();
        
    } catch (const std::exception& e) {
        RCLCPP_ERROR(rclcpp::get_logger("bag_log_node"), "Error in Node: %s", e.what());
        rclcpp::shutdown();
        return 1;
    }
    
    return 0;
}
