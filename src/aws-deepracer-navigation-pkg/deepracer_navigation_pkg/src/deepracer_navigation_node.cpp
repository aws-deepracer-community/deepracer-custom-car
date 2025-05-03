#include "deepracer_navigation_pkg/deepracer_navigation_node.hpp"

#include <filesystem>
#include <fstream>
#include <algorithm>
#include <stdexcept>
#include <cmath>

namespace deepracer_navigation_pkg {

DRNavigationNode::DRNavigationNode() 
    : Node("deepracer_navigation_node")
{
    RCLCPP_INFO(get_logger(), "deepracer_navigation_node started");
    
    // Publisher for autonomous driving commands
    auto_drive_publisher_ = create_publisher<deepracer_interfaces_pkg::msg::ServoCtrlMsg>(
        constants::AUTO_DRIVE_TOPIC_NAME, 1);
        
    // Create callback group for throttle service
    throttle_service_cb_group_ = create_callback_group(
        rclcpp::CallbackGroupType::MutuallyExclusive);
    
    // Create services
    throttle_service_ = create_service<deepracer_interfaces_pkg::srv::NavThrottleSrv>(
        constants::NAVIGATION_THROTTLE_SERVICE_NAME,
        std::bind(&DRNavigationNode::set_throttle_scale_cb, this, 
                 std::placeholders::_1, std::placeholders::_2),
                 rclcpp::QoS(rclcpp::SystemDefaultsQoS()).get_rmw_qos_profile(),
        throttle_service_cb_group_);
    
    action_space_service_ = create_service<deepracer_interfaces_pkg::srv::LoadModelSrv>(
        constants::LOAD_ACTION_SPACE_SERVICE_NAME,
        std::bind(&DRNavigationNode::set_action_space_cb, this, 
                 std::placeholders::_1, std::placeholders::_2));
    
    // Initialize map for action space values
    max_action_space_values_[constants::ModelMetadataKeys::STEERING] = 0.0;
    max_action_space_values_[constants::ModelMetadataKeys::SPEED] = 0.0;
    
    // Initialize speed mapping coefficients
    speed_mapping_coefficients_["a"] = 0.0;
    speed_mapping_coefficients_["b"] = 0.0;
    
    // Set default action space scales
    set_action_space_scales();
    
    // Subscribe to inference results
    inference_subscription_ = create_subscription<deepracer_interfaces_pkg::msg::InferResultsArray>(
        constants::INFERENCE_PKG_RL_RESULTS_TOPIC, 10,
        std::bind(&DRNavigationNode::inference_cb, this, std::placeholders::_1));
    
    // Create heartbeat timer
    timer_ = create_wall_timer(
        std::chrono::seconds(5),
        std::bind(&DRNavigationNode::timer_callback, this));
    
    RCLCPP_INFO(get_logger(), "DeepRacer navigation node (C++) successfully created");
}

void DRNavigationNode::timer_callback() {
    RCLCPP_DEBUG(get_logger(), "Timer heartbeat %d", timer_count_);
    timer_count_++;
}

void DRNavigationNode::process_inference_data(
    const deepracer_interfaces_pkg::msg::InferResultsArray::SharedPtr inference_msg,
    deepracer_interfaces_pkg::msg::ServoCtrlMsg& servo_msg) 
{
    // Add the source_stamp header
    servo_msg.source_stamp = inference_msg->images[0].header.stamp;
    // Negative value moves the car forward, positive values move the car backwards
    servo_msg.throttle = throttle_scale_;
    
    try {
        if (action_space_type_ == constants::ActionSpaceTypes::DISCRETE) {
            // Find the result with maximum probability
            auto max_prob_result = std::max_element(
                inference_msg->results.begin(),
                inference_msg->results.end(),
                [](const auto& a, const auto& b) { return a.class_prob < b.class_prob; });
                
            int action_id = max_prob_result->class_label;
            double steering = action_space_[action_id][constants::ModelMetadataKeys::STEERING].asDouble();
            double speed = action_space_[action_id][constants::ModelMetadataKeys::SPEED].asDouble();
            
            servo_msg.angle = get_max_scaled_value(steering, constants::ModelMetadataKeys::STEERING);
            servo_msg.throttle *= get_non_linearly_mapped_speed(speed);
        }
        else if (action_space_type_ == constants::ActionSpaceTypes::CONTINUOUS) {
            // Map action values for continuous action space
            std::map<int, double> action_values;
            for (const auto& result : inference_msg->results) {
                action_values[result.class_label] = std::max(std::min(static_cast<double>(result.class_prob), 1.0), -1.0);
            }
            
            double scaled_angle = scale_continuous_value(
                action_values[0], -1.0, 1.0,
                action_space_[constants::ModelMetadataKeys::STEERING][constants::ModelMetadataKeys::CONTINUOUS_LOW].asDouble(),
                action_space_[constants::ModelMetadataKeys::STEERING][constants::ModelMetadataKeys::CONTINUOUS_HIGH].asDouble());
                
            servo_msg.angle = get_max_scaled_value(scaled_angle, constants::ModelMetadataKeys::STEERING);
            
            double scaled_throttle = scale_continuous_value(
                action_values[1], -1.0, 1.0,
                action_space_[constants::ModelMetadataKeys::SPEED][constants::ModelMetadataKeys::CONTINUOUS_LOW].asDouble(),
                action_space_[constants::ModelMetadataKeys::SPEED][constants::ModelMetadataKeys::CONTINUOUS_HIGH].asDouble());
                
            servo_msg.throttle *= get_non_linearly_mapped_speed(scaled_throttle);
        }
        else {
            throw std::runtime_error("Action space type is not supported");
        }
    }
    catch (const std::exception& ex) {
        RCLCPP_ERROR(get_logger(), "Error while processing data in navigation node: %s", ex.what());
        servo_msg.throttle = 0.0;
        servo_msg.angle = 0.0;
    }
}

void DRNavigationNode::inference_cb(
    const deepracer_interfaces_pkg::msg::InferResultsArray::SharedPtr inference_msg) 
{
    deepracer_interfaces_pkg::msg::ServoCtrlMsg servo_msg;
    process_inference_data(inference_msg, servo_msg);
    auto_drive_publisher_->publish(servo_msg);
}

void DRNavigationNode::set_throttle_scale_cb(
    const std::shared_ptr<deepracer_interfaces_pkg::srv::NavThrottleSrv::Request> request,
    std::shared_ptr<deepracer_interfaces_pkg::srv::NavThrottleSrv::Response> response) 
{
    throttle_scale_ = request->throttle;
    RCLCPP_INFO(get_logger(), "Setting throttle to %f", request->throttle);
    response->error = 0;
}

void DRNavigationNode::set_action_space_cb(
    const std::shared_ptr<deepracer_interfaces_pkg::srv::LoadModelSrv::Request> request,
    std::shared_ptr<deepracer_interfaces_pkg::srv::LoadModelSrv::Response> response)
{
    try {
        std::filesystem::path model_path(request->artifact_path);
        auto model_dir = model_path.parent_path().string();
        std::string model_metadata_file = model_dir + "/model_metadata.json";
        
        RCLCPP_INFO(get_logger(), "Loading model metadata from: %s", model_metadata_file.c_str());
        
        std::ifstream json_file(model_metadata_file);
        if (!json_file.is_open()) {
            throw std::runtime_error("Could not open model metadata file");
        }
        
        Json::Value root;
        Json::Reader reader;
        if (!reader.parse(json_file, root)) {
            throw std::runtime_error("Failed to parse model metadata JSON");
        }
        
        if (!root.isMember("action_space")) {
            throw std::runtime_error("Model metadata missing 'action_space' key");
        }
        
        action_space_ = root["action_space"];
        
        // Properly set action space type based on the enum values
        // If request is 0 (default), set to DISCRETE (1)
        // If request is 2, set to CONTINUOUS (2)
        // Otherwise, set to DISCRETE (1)
        if (request->action_space_type == 0 || request->action_space_type == 1) {
            action_space_type_ = constants::ActionSpaceTypes::DISCRETE;
        } else if (request->action_space_type == 2) {
            action_space_type_ = constants::ActionSpaceTypes::CONTINUOUS;
        } else {
            action_space_type_ = constants::ActionSpaceTypes::DISCRETE;
        }
        
        RCLCPP_INFO(get_logger(), "Action space loaded successfully, type: %d", 
                   static_cast<int>(action_space_type_));
        
        validate_action_space();
        
        RCLCPP_INFO(get_logger(), "Action space validated successfully");
        set_action_space_scales();
        response->error = 0;
    }
    catch (const std::exception& e) {
        // Reset to defaults on failure
        action_space_ = Json::Value(Json::arrayValue);
        action_space_type_ = constants::ActionSpaceTypes::DISCRETE;
        RCLCPP_ERROR(get_logger(), "Failed to load action space: %s", e.what());
        response->error = 1;
    }
}

void DRNavigationNode::validate_action_space() {
    bool valid_action_space = true;
    
    // First, check the JSON type to diagnose the issue
    RCLCPP_INFO(get_logger(), "Action space type: %d, JSON type: %d", 
                static_cast<int>(action_space_type_), action_space_.type());
    
    if (action_space_type_ == constants::ActionSpaceTypes::DISCRETE) {
        if (!action_space_.isArray()) {
            RCLCPP_ERROR(get_logger(), "Discrete action space must be an array");
            valid_action_space = false;
        } else {
            for (const auto& action : action_space_) {
                if (!action.isObject()) {
                    RCLCPP_ERROR(get_logger(), "Each action must be an object");
                    valid_action_space = false;
                    break;
                }
                if (!action.isMember(constants::ModelMetadataKeys::STEERING) ||
                    !action.isMember(constants::ModelMetadataKeys::SPEED)) {
                    RCLCPP_ERROR(get_logger(), "Action missing steering or speed");
                    valid_action_space = false;
                    break;
                }
            }
        }
    }
    else if (action_space_type_ == constants::ActionSpaceTypes::CONTINUOUS) {
        if (!action_space_.isObject()) {
            // For continuous action space, we need an object but got something else
            // Fall back to treating it as a discrete action space with array elements
            RCLCPP_WARN(get_logger(), "Continuous action space isn't an object, falling back to first array element");
            
            if (action_space_.isArray() && !action_space_.empty()) {
                // Use first element from array as representative values
                const Json::Value& first_action = action_space_[0];
                
                // Create a temporary object with the structure we need
                Json::Value temp_action_space(Json::objectValue);
                
                Json::Value steering(Json::objectValue);
                // FIX: Make sure high is always greater than low
                double steering_val = std::abs(first_action[constants::ModelMetadataKeys::STEERING].asDouble());
                steering[constants::ModelMetadataKeys::CONTINUOUS_LOW] = -steering_val;
                steering[constants::ModelMetadataKeys::CONTINUOUS_HIGH] = steering_val;
                
                Json::Value speed(Json::objectValue);
                speed[constants::ModelMetadataKeys::CONTINUOUS_LOW] = 0;
                speed[constants::ModelMetadataKeys::CONTINUOUS_HIGH] = first_action[constants::ModelMetadataKeys::SPEED].asDouble();
                
                temp_action_space[constants::ModelMetadataKeys::STEERING] = steering;
                temp_action_space[constants::ModelMetadataKeys::SPEED] = speed;
                
                // Replace the action space
                action_space_ = temp_action_space;
                RCLCPP_INFO(get_logger(), "Created compatible action space structure: steering [%f, %f], speed [%f, %f]", 
                           steering[constants::ModelMetadataKeys::CONTINUOUS_LOW].asDouble(),
                           steering[constants::ModelMetadataKeys::CONTINUOUS_HIGH].asDouble(),
                           speed[constants::ModelMetadataKeys::CONTINUOUS_LOW].asDouble(),
                           speed[constants::ModelMetadataKeys::CONTINUOUS_HIGH].asDouble());
            } else {
                valid_action_space = false;
            }
        }
        
        // Now validate the object structure (original or newly created)
        if (valid_action_space) {
            if (!action_space_.isMember(constants::ModelMetadataKeys::STEERING) ||
                !action_space_.isMember(constants::ModelMetadataKeys::SPEED)) {
                RCLCPP_ERROR(get_logger(), "Missing steering or speed in continuous action space");
                valid_action_space = false;
            }
            else {
                const auto& steering_action = action_space_[constants::ModelMetadataKeys::STEERING];
                const auto& speed_action = action_space_[constants::ModelMetadataKeys::SPEED];
                
                if (!steering_action.isObject() || !speed_action.isObject()) {
                    RCLCPP_ERROR(get_logger(), "Steering or speed value is not an object");
                    valid_action_space = false;
                }
                else if (!steering_action.isMember(constants::ModelMetadataKeys::CONTINUOUS_HIGH) ||
                    !steering_action.isMember(constants::ModelMetadataKeys::CONTINUOUS_LOW) ||
                    !speed_action.isMember(constants::ModelMetadataKeys::CONTINUOUS_HIGH) ||
                    !speed_action.isMember(constants::ModelMetadataKeys::CONTINUOUS_LOW)) {
                    RCLCPP_ERROR(get_logger(), "Missing high/low bounds in continuous action space");
                    valid_action_space = false;
                }
                else if (steering_action[constants::ModelMetadataKeys::CONTINUOUS_HIGH].asDouble() <=
                        steering_action[constants::ModelMetadataKeys::CONTINUOUS_LOW].asDouble() ||
                    speed_action[constants::ModelMetadataKeys::CONTINUOUS_HIGH].asDouble() <=
                        speed_action[constants::ModelMetadataKeys::CONTINUOUS_LOW].asDouble()) {
                    RCLCPP_ERROR(get_logger(), "Invalid high/low bounds in continuous action space");
                    valid_action_space = false;
                }
            }
        }
    }
    
    if (!valid_action_space) {
        throw std::runtime_error("Incorrect action space values");
    }
}

void DRNavigationNode::set_action_space_scales() {
    try {
        if (action_space_type_ == constants::ActionSpaceTypes::DISCRETE) {
            double max_steering = 0.0;
            double max_speed = 0.0;
            
            for (const auto& action : action_space_) {
                double steering = std::abs(action[constants::ModelMetadataKeys::STEERING].asDouble());
                double speed = std::abs(action[constants::ModelMetadataKeys::SPEED].asDouble());
                
                if (steering > max_steering) max_steering = steering;
                if (speed > max_speed) max_speed = speed;
            }
            
            max_action_space_values_[constants::ModelMetadataKeys::STEERING] = max_steering;
            max_action_space_values_[constants::ModelMetadataKeys::SPEED] = max_speed;
        }
        else if (action_space_type_ == constants::ActionSpaceTypes::CONTINUOUS) {
            max_action_space_values_[constants::ModelMetadataKeys::STEERING] = 
                action_space_[constants::ModelMetadataKeys::STEERING][constants::ModelMetadataKeys::CONTINUOUS_HIGH].asDouble();
            max_action_space_values_[constants::ModelMetadataKeys::SPEED] = 
                action_space_[constants::ModelMetadataKeys::SPEED][constants::ModelMetadataKeys::CONTINUOUS_HIGH].asDouble();
        }
        else {
            throw std::runtime_error("Incorrect action space type");
        }
        
        // Calculate speed mapping coefficients
        double max_speed = max_action_space_values_[constants::ModelMetadataKeys::SPEED];
        if (max_speed > 0.0) {
            // Solution to a*x^2 + b*x for the two points in DEFAULT_SPEED_SCALES
            speed_mapping_coefficients_["a"] = (1.0 / (max_speed * max_speed)) * 
                (2.0 * constants::DEFAULT_SPEED_SCALES[0] - 4.0 * constants::DEFAULT_SPEED_SCALES[1]);
                
            speed_mapping_coefficients_["b"] = (1.0 / max_speed) *
                (4.0 * constants::DEFAULT_SPEED_SCALES[1] - constants::DEFAULT_SPEED_SCALES[0]);
        }
        
        RCLCPP_INFO(get_logger(), "Action space scale set - Mapping equation params a: %f, b: %f",
                  speed_mapping_coefficients_["a"], speed_mapping_coefficients_["b"]);
    }
    catch (const std::exception& ex) {
        RCLCPP_ERROR(get_logger(), "Unable to detect action space scale: %s", ex.what());
    }
}

double DRNavigationNode::get_max_scaled_value(double action_value, const std::string& action_key) {
    try {
        double max_value = max_action_space_values_[action_key];
        if (max_value <= 0.0) {
            RCLCPP_ERROR(get_logger(), "Invalid %s value %f", action_key.c_str(), max_value);
            return 0.0;
        }
        return action_value / max_value;
    }
    catch (const std::exception& ex) {
        RCLCPP_ERROR(get_logger(), "Unable to scale the action value %s: %s", 
                   action_key.c_str(), ex.what());
        return 0.0;
    }
}

double DRNavigationNode::get_non_linearly_mapped_speed(double scaled_action_space_speed) {
    double mapped_speed = speed_mapping_coefficients_["a"] * scaled_action_space_speed * scaled_action_space_speed +
                         speed_mapping_coefficients_["b"] * scaled_action_space_speed;
                         
    return std::max(std::min(mapped_speed, 1.0), -1.0);
}

double DRNavigationNode::scale_continuous_value(double action, double min_old, double max_old, 
                                             double min_new, double max_new) 
{
    if (max_old == min_old) {
        RCLCPP_ERROR(get_logger(), "Unsupported minimum and maximum action space bounds for scaling values. "
                               "min_old: %f; max_old: %f", min_old, max_old);
        return 0.0;
    }
    return ((max_new - min_new) / (max_old - min_old)) * (action - min_old) + min_new;
}

} // namespace deepracer_navigation_pkg