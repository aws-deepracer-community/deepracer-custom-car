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

#ifndef ROS_DISTRO_JAZZY
#include "inference_pkg/intel_inference_eng.hpp"
#endif
#include "inference_pkg/tflite_inference_eng.hpp"
#include "std_msgs/msg/string.hpp"
#include "deepracer_interfaces_pkg/srv/inference_state_srv.hpp"
#include "deepracer_interfaces_pkg/srv/load_model_srv.hpp"

namespace InferTask {
    /// Enum that references the available inference tasks.
    enum InferTaskType {
        rlTask,
        objDetectTask,
        numTask
    };
    /// Enum that references the available pre-processing algorithms.
    enum PreProccessType {
        rgb,
        grey, // grey
        greyMask, // mask
        greyThreshold, // threshold
        greyThresholdMask, // threshold + mask
        greyDiff,
        numPreProcess
    };

    class InferenceNodeMgr : public rclcpp::Node
    {
    /// Class that will manage the inference task. In particular it will start and stop the
    /// inference tasks and feed the inference task the sensor data.
    /// @param nodeName Reference to the string containing name of the node.
    /// @param device Reference to the compute device (CPU, GPU, MYRIAD)
    public:
        const char* MODEL_ARTIFACT_TOPIC = "model_artifact";

        InferenceNodeMgr(const std::string & nodeName)
          : Node(nodeName),
          deviceName_("CPU"),
          inferenceEngine_("TFLITE")
        {
            RCLCPP_INFO(this->get_logger(), "%s started", nodeName.c_str());

            this->declare_parameter<std::string>("device", deviceName_);
            // Device name; OpenVINO supports CPU, GPU and MYRIAD
            deviceName_ = this->get_parameter("device").as_string();

            this->declare_parameter<std::string>("inference_engine", inferenceEngine_);
            // Inference Engine name; TFLITE or OPENVINO
            inferenceEngine_ = this->get_parameter("inference_engine").as_string();

            RCLCPP_INFO(this->get_logger(), "Using inference engine: %s", inferenceEngine_.c_str());
            if (inferenceEngine_.compare("OV") == 0) {
                RCLCPP_INFO(this->get_logger(), "Using device: %s", deviceName_.c_str());
            }

            loadModelServiceCbGrp_ = this->create_callback_group(rclcpp::CallbackGroupType::MutuallyExclusive);
            loadModelService_ = this->create_service<deepracer_interfaces_pkg::srv::LoadModelSrv>("load_model",
                                                                                                  std::bind(&InferTask::InferenceNodeMgr::LoadModelHdl,
                                                                                                  this,
                                                                                                  std::placeholders::_1,
                                                                                                  std::placeholders::_2,
                                                                                                  std::placeholders::_3),
                                                                                                  ::rmw_qos_profile_default,
                                                                                                  loadModelServiceCbGrp_);

            setInferenceStateServiceCbGrp_ = this->create_callback_group(rclcpp::CallbackGroupType::MutuallyExclusive);
            setInferenceStateService_ = this->create_service<deepracer_interfaces_pkg::srv::InferenceStateSrv>("inference_state",
                                                                                                               std::bind(&InferTask::InferenceNodeMgr::InferStateHdl,
                                                                                                               this,
                                                                                                               std::placeholders::_1,
                                                                                                               std::placeholders::_2,
                                                                                                               std::placeholders::_3),
                                                                                                               ::rmw_qos_profile_default,
                                                                                                               setInferenceStateServiceCbGrp_);

            // Create a publisher to publish the images to run inference.
            modelArtifactPub_ = this->create_publisher<std_msgs::msg::String>(MODEL_ARTIFACT_TOPIC, 1);

            // Add all available task and algorithms to these hash maps.
            taskList_ = { {rlTask, nullptr} };
            preProcessList_ = { {rgb, std::make_shared<RGB>()},
                                {grey, std::make_shared<Grey>(false, false)},
                                {greyMask, std::make_shared<Grey>(false, true)},
                                {greyThreshold, std::make_shared<Grey>(true, false)},
                                {greyThresholdMask, std::make_shared<Grey>(true, true)},
                                {greyDiff, std::make_shared<GreyDiff>()} };
        }
        ~InferenceNodeMgr() = default;
        /// Callback method for the inference state server, this method is responsible
        /// for starting and stopping inference tasks based on request.
        void InferStateHdl(const std::shared_ptr<rmw_request_id_t> request_header,
                           std::shared_ptr<deepracer_interfaces_pkg::srv::InferenceStateSrv::Request> req,
                           std::shared_ptr<deepracer_interfaces_pkg::srv::InferenceStateSrv::Response> res) {
            (void)request_header;
            auto itInferTask = taskList_.find(req->task_type);

            res->error = 1;

            if (itInferTask != taskList_.end()) {
                if (!itInferTask->second) {
                    RCLCPP_INFO(this->get_logger(), "Please load a model before starting inference");
                    res->error = 0;
                    return;
                }
                if (req->start) {
                    itInferTask->second->startInference();
                    RCLCPP_INFO(this->get_logger(), "Inference task (enum %d) has started", req->task_type);

                }
                else {
                    itInferTask->second->stopInference();
                     RCLCPP_INFO(this->get_logger(), "Inference task (enum %d) has stopped", req->task_type);
                }
                
                res->error = 0;
            }
        }
        /// Callback method for the load model server, this method is responsible
        /// for loading  the model and pre-processing algorithm to the desired inference
        /// task.
        void LoadModelHdl(const std::shared_ptr<rmw_request_id_t> request_header,
                          std::shared_ptr<deepracer_interfaces_pkg::srv::LoadModelSrv::Request> req,
                          std::shared_ptr<deepracer_interfaces_pkg::srv::LoadModelSrv::Response> res) {
            (void)request_header;
            auto itInferTask = taskList_.find(req->task_type);
            auto itPreProcess = preProcessList_.find(req->pre_process_type);
            res->error = 1;

            if (itInferTask != taskList_.end() && itPreProcess != preProcessList_.end()) {
                switch(req->task_type) {
                    case rlTask:
                        if (inferenceEngine_.compare("TFLITE") == 0) {
                            itInferTask->second.reset(new TFLiteInferenceEngine::RLInferenceModel(this->shared_from_this(), "/sensor_fusion_pkg/sensor_msg"));
                        } else {
                            #ifndef ROS_DISTRO_JAZZY
                            itInferTask->second.reset(new IntelInferenceEngine::RLInferenceModel(this->shared_from_this(), "/sensor_fusion_pkg/sensor_msg"));
                            #endif
                        }
                        
                        break;
                    case objDetectTask:
                        //! TODO add onject detection when class is implemented.
                        RCLCPP_ERROR(this->get_logger(), "Object detection not implemented");
                        return;
                    default:
                        RCLCPP_ERROR(this->get_logger(), "Unknown inference task");
                        return;
                }

                itInferTask->second->loadModel(req->artifact_path.c_str(), itPreProcess->second, deviceName_);

                // Send a message to say we have loaded a model
                std_msgs::msg::String modelArtifactMsg;
                modelArtifactMsg.data = req->artifact_path;
                modelArtifactPub_->publish(modelArtifactMsg);

                res->error = 0;
            }
        }

    private:
        /// ROS callback group for load model service.
        rclcpp::CallbackGroup::SharedPtr loadModelServiceCbGrp_;
        /// ROS service to load inference model.
        rclcpp::Service<deepracer_interfaces_pkg::srv::LoadModelSrv>::SharedPtr loadModelService_;
        /// ROS callback group for set inference state service.
        rclcpp::CallbackGroup::SharedPtr setInferenceStateServiceCbGrp_;
        /// ROS service to set the inference state to start/stop running inference.
        rclcpp::Service<deepracer_interfaces_pkg::srv::InferenceStateSrv>::SharedPtr setInferenceStateService_;

        /// List of available inference task.
        std::unordered_map<int, std::shared_ptr<InferenceBase>> taskList_;
        /// List of available pre-processing algorithms.
        std::unordered_map<int, std::shared_ptr<ImgProcessBase>> preProcessList_;
        /// Reference to the node handler.

        /// ROS publisher object to publish the name of a new model.
        rclcpp::Publisher<std_msgs::msg::String>::SharedPtr modelArtifactPub_;

        /// Compute device type.
        std::string deviceName_;
        /// Inference Engine parameter.
        std::string inferenceEngine_;
    };
}

int main(int argc, char * argv[])
{
    rclcpp::init(argc, argv);
    auto node = std::make_shared<InferTask::InferenceNodeMgr>("inference_node");
    rclcpp::executors::MultiThreadedExecutor exec;
    exec.add_node(node);
    exec.spin();
    rclcpp::shutdown();
    return 0;
}
