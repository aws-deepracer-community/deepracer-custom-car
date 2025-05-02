#ifndef DEEPRACER_NAVIGATION_NODE_HPP
#define DEEPRACER_NAVIGATION_NODE_HPP

#include <memory>
#include <string>
#include <fstream>
#include <vector>
#include <map>
#include <jsoncpp/json/json.h>

#include "rclcpp/rclcpp.hpp"
#include "deepracer_interfaces_pkg/msg/servo_ctrl_msg.hpp"
#include "deepracer_interfaces_pkg/msg/infer_results_array.hpp"
#include "deepracer_interfaces_pkg/srv/nav_throttle_srv.hpp"
#include "deepracer_interfaces_pkg/srv/load_model_srv.hpp"

namespace deepracer_navigation_pkg {

// Constants copied from Python constants module
namespace constants {
    // Topic names
    const std::string INFERENCE_PKG_RL_RESULTS_TOPIC = "/inference_pkg/rl_results";
    const std::string AUTO_DRIVE_TOPIC_NAME = "auto_drive";

    // Service names
    const std::string NAVIGATION_THROTTLE_SERVICE_NAME = "navigation_throttle";
    const std::string LOAD_ACTION_SPACE_SERVICE_NAME = "load_action_space";

    // Action space types
    enum class ActionSpaceTypes {
        DISCRETE = 1,
        CONTINUOUS = 2
    };

    // Model metadata keys
    struct ModelMetadataKeys {
        static constexpr const char* STEERING = "steering_angle";
        static constexpr const char* SPEED = "speed";
        static constexpr const char* ACTION = "action";
        static constexpr const char* CONTINUOUS_HIGH = "high";
        static constexpr const char* CONTINUOUS_LOW = "low";
    };

    // Default speed scales
    const std::vector<double> DEFAULT_SPEED_SCALES = {0.8, 0.5};
}

class DRNavigationNode : public rclcpp::Node {
public:
    DRNavigationNode();
    virtual ~DRNavigationNode() = default;

private:
    // Timer callback
    void timer_callback();
    
    // Process inference data
    void process_inference_data(
        const deepracer_interfaces_pkg::msg::InferResultsArray::SharedPtr inference_msg,
        deepracer_interfaces_pkg::msg::ServoCtrlMsg& servo_msg);
    
    // Callback for inference results
    void inference_cb(const deepracer_interfaces_pkg::msg::InferResultsArray::SharedPtr inference_msg);
    
    // Service callbacks
    void set_throttle_scale_cb(
        const std::shared_ptr<deepracer_interfaces_pkg::srv::NavThrottleSrv::Request> request,
        std::shared_ptr<deepracer_interfaces_pkg::srv::NavThrottleSrv::Response> response);
    
    void set_action_space_cb(
        const std::shared_ptr<deepracer_interfaces_pkg::srv::LoadModelSrv::Request> request,
        std::shared_ptr<deepracer_interfaces_pkg::srv::LoadModelSrv::Response> response);
    
    // Helper methods
    void validate_action_space();
    void set_action_space_scales();
    double get_max_scaled_value(double action_value, const std::string& action_key);
    double get_non_linearly_mapped_speed(double scaled_action_space_speed);
    double scale_continuous_value(double action, double min_old, double max_old, 
                                double min_new, double max_new);

    // Member variables
    double throttle_scale_{0.0};
    Json::Value action_space_;
    constants::ActionSpaceTypes action_space_type_{constants::ActionSpaceTypes::DISCRETE};
    std::map<std::string, double> max_action_space_values_;
    std::map<std::string, double> speed_mapping_coefficients_;
    int timer_count_{0};
    
    // ROS members
    rclcpp::CallbackGroup::SharedPtr throttle_service_cb_group_;
    rclcpp::Publisher<deepracer_interfaces_pkg::msg::ServoCtrlMsg>::SharedPtr auto_drive_publisher_;
    rclcpp::Subscription<deepracer_interfaces_pkg::msg::InferResultsArray>::SharedPtr inference_subscription_;
    rclcpp::Service<deepracer_interfaces_pkg::srv::NavThrottleSrv>::SharedPtr throttle_service_;
    rclcpp::Service<deepracer_interfaces_pkg::srv::LoadModelSrv>::SharedPtr action_space_service_;
    rclcpp::TimerBase::SharedPtr timer_;
};

}  // namespace deepracer_navigation_pkg

#endif  // DEEPRACER_NAVIGATION_NODE_HPP