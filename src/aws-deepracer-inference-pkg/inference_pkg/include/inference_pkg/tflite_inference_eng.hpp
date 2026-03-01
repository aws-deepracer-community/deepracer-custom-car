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

#ifndef TFLITE_INFERENCE_ENG_HPP
#define TFLITE_INFERENCE_ENG_HPP

#include "inference_pkg/inference_base.hpp"
#include "tensorflow/lite/interpreter.h"
#include "tensorflow/lite/kernels/register.h"
#include "tensorflow/lite/model.h"
#include "deepracer_interfaces_pkg/msg/evo_sensor_msg.hpp"
#include "deepracer_interfaces_pkg/msg/infer_results_array.hpp"
#include <atomic>

namespace TFLiteInferenceEngine {
    class RLInferenceModel : public InferTask::InferenceBase
    {
    /// Concrete inference task class for running reinforcement learning models
    /// on the GPU.
    public:
        /// @param node_name Name of the node to be created.
        /// @param subName Name of the topic to subscribe to for sensor data.
        RLInferenceModel(std::shared_ptr<rclcpp::Node> inferenceNodePtr, const std::string &sensorSubName);
        virtual ~RLInferenceModel();
        virtual bool loadModel(const char* artifactPath,
                               std::shared_ptr<InferTask::ImgProcessBase> imgProcess,
                               std::string device) override;
        virtual void startInference() override;
        virtual void stopInference() override;
        /// Callback method to retrieve sensor data.
        /// @param msg Message returned by the ROS messaging system.
        void sensorCB(const deepracer_interfaces_pkg::msg::EvoSensorMsg::SharedPtr msg);

    private:
        /// Inference node object
        std::shared_ptr<rclcpp::Node> inferenceNode;
        /// ROS subscriber object to the desired sensor topic.
        rclcpp::Subscription<deepracer_interfaces_pkg::msg::EvoSensorMsg>::SharedPtr sensorSub_;
        /// ROS publisher object to the desired topic.
        rclcpp::Publisher<deepracer_interfaces_pkg::msg::InferResultsArray>::SharedPtr resultPub_;
        /// Pointer to image processing algorithm.
        std::shared_ptr<InferTask::ImgProcessBase> imgProcess_;
        /// Inference state variable.
        std::atomic<bool> doInference_;
        /// Neural network Inference engine core object.
        std::unique_ptr<tflite::FlatBufferModel> model_;
        /// Inference request object
        std::unique_ptr<tflite::Interpreter> interpreter_;
        /// Vector of hash map that stores all relevant pre-processing parameters for each input head.
        std::vector<std::unordered_map<std::string, int>> paramsArr_;
        /// Vector of names of the input heads
        std::vector<std::string> inputNamesArr_;
        /// Name of the output layer
        std::string outputName_;      
        std::vector<std::vector<int>> outputDimsArr_;
        std::vector<TfLiteTensor const *> output_tensors_;
        /// Cached input tensor pointers for performance (like OpenVINO implementation)
        std::vector<float*> inputTensorPtrs_;
        /// Cached output tensor pointer for performance
        float* outputTensorPtr_;

    };
}
#endif