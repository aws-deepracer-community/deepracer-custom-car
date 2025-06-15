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

#include "inference_pkg/tflite_inference_eng.hpp"

// ROS2 message headers
#include "deepracer_interfaces_pkg/msg/infer_results.hpp"
#include "deepracer_interfaces_pkg/msg/infer_results_array.hpp"

#include <thread>
#include <exception>
#include <omp.h>

#define RAD2DEG(x) ((x)*180./M_PI)

const std::string LIDAR = "LIDAR";
const std::string STEREO = "STEREO_CAMERAS";
const std::string FRONT = "FRONT_FACING_CAMERA";
const std::string OBS = "observation";
const std::string LEFT = "LEFT_CAMERA";


namespace {
    class InferenceExcept : public std::exception
    {
    /// Simple exception class that is used to send a message to the catch clause.
    public:
        /// @param msg Message to be logged
        InferenceExcept(std::string msg)
          : msg_(msg)
        {
        }
        virtual const char* what() const throw() override {
            return msg_.c_str();
        }
    private:
        /// Store message in class so that the what method can dump it when invoked.
        const std::string msg_;
    };

     /// Helper method that loads grey images into the inference engine input
     /// @param inputPtr Pointer to the input data.
     /// @param imgProcessPtr Pointer to the image processing algorithm.
     /// @param imgData ROS message containing the image data.
     /// @param params Hash map of relevant parameters for image processing.
     template<typename T, typename V> void load1DImg(V *inputPtr,
                                                     cv::Mat &retImg,
                                                     std::shared_ptr<InferTask::ImgProcessBase> imgProcessPtr,
                                                     const sensor_msgs::msg::CompressedImage &imgData,
                                                     const std::unordered_map<std::string, int> &params) {
        imgProcessPtr->processImage(imgData, retImg, params);
        if (retImg.empty()) {
            throw InferenceExcept("No image after pre-process");
        }
        int height = retImg.rows;
        int width = retImg.cols;

        for (int  h = 0; h < height; h++) {
            for (int w = 0; w < width; w++) {
                inputPtr[h * width + w] = retImg.at<T>(h, w);
            }
        }
     }

     /// Helper method that loads multi channel images into the inference engine input
     /// @param inputPtr Pointer to the input data.
     /// @param imgProcessPtr Pointer to the image processing algorithm.
     /// @param imgData ROS message containing the image data.
     /// @param params Hash map of relevant parameters for image processing.
     template<typename T, typename V> void loadStackImg(V *inputPtr,
                                                        cv::Mat &retImg, 
                                                        std::shared_ptr<InferTask::ImgProcessBase> imgProcessPtr,
                                                        const sensor_msgs::msg::CompressedImage &imgData,
                                                        const std::unordered_map<std::string, int> &params) {
        imgProcessPtr->processImage(imgData, retImg, params);
        if (retImg.empty()) {
            throw InferenceExcept("No image after-pre process");
        }
        const int channelSize = retImg.rows * retImg.cols;

         for (size_t pixelNum = 0; pixelNum < channelSize; ++pixelNum) {
             for (size_t ch = 0; ch < retImg.channels(); ++ch) {
                inputPtr[(ch*channelSize) + pixelNum] = retImg.at<T>(pixelNum)[ch];
             }
         }
     }

     /// Helper method that loads multi channel images into the inference engine input
     /// @param inputPtr Pointer to the input data.
     /// @param imgProcessPtr Pointer to the image processing algorithm.
     /// @param imgData ROS message containing the image data.
     /// @param params Hash map of relevant parameters for image processing.
     template<typename T, typename V> void loadStereoImg(V *inputPtr,
                                                        cv::Mat &retImg, 
                                                        std::shared_ptr<InferTask::ImgProcessBase> imgProcessPtr,
                                                        const std::vector<sensor_msgs::msg::CompressedImage> &imgDataArr,
                                                        const std::unordered_map<std::string, int> &params) {

        imgProcessPtr->processImageVec(imgDataArr, retImg, params);
        if (retImg.empty()) {
            throw InferenceExcept("No image after-pre process");
        }
        
        const int width = retImg.cols;
        const int height = retImg.rows;
        const int channel = retImg.channels();

        for (int c = 0; c < channel; c++) {
            for (int  h = 0; h < height; h++) {
                for (int w = 0; w < width; w++) {
                    inputPtr[c * width * height + h * width + w] = retImg.at<T>(h, w)[c];
                }
            }
        }
     }

     /// Helper method that loads 1D data into the inference engine input
     /// @param inputPtr Pointer to the input data.
     /// @param lidarData ROS message containing the lidar data.
     void loadLidarData(float *inputPtr,
                        const std::vector<float> &lidar_data) {
        size_t pixelNum = 0;
        for(const auto& lidar_value : lidar_data) {
            inputPtr[pixelNum] = lidar_value;
            ++pixelNum;
        }
     }
}

namespace TFLiteInferenceEngine {
    RLInferenceModel::RLInferenceModel(std::shared_ptr<rclcpp::Node> inferenceNodePtr, const std::string &sensorSubName)
     : doInference_(false)
    {
        inferenceNode = inferenceNodePtr;
        RCLCPP_INFO(inferenceNode->get_logger(), "Initializing RL Model");
        RCLCPP_INFO(inferenceNode->get_logger(), "%s", sensorSubName.c_str());
        // Subscribe to the sensor topic and set the call back
        sensorSub_ = inferenceNode->create_subscription<deepracer_interfaces_pkg::msg::EvoSensorMsg>(sensorSubName, 10, std::bind(&TFLiteInferenceEngine::RLInferenceModel::sensorCB, this, std::placeholders::_1));
        resultPub_ = inferenceNode->create_publisher<deepracer_interfaces_pkg::msg::InferResultsArray>("rl_results", 1);
    }

    RLInferenceModel::~RLInferenceModel() {
        stopInference();
    }

    bool RLInferenceModel::loadModel(const char* artifactPath,
                            std::shared_ptr<InferTask::ImgProcessBase> imgProcess,
                            std::string device) {
        if (doInference_) {
            RCLCPP_ERROR(inferenceNode->get_logger(), "Please stop inference prior to loading a model");
            return false;
        }
        if (!imgProcess) {
            RCLCPP_ERROR(inferenceNode->get_logger(), "Invalid image processing algorithm");
            return false;
        }

        // Validate the artifact path.
        auto strIdx = ((std::string) artifactPath).rfind('.');
        if (strIdx == std::string::npos) {
            throw InferenceExcept("Artifact missing file extension");
        }
        if (((std::string) artifactPath).substr(strIdx+1) != "tflite") {
            throw InferenceExcept("No tflite extension found");
        }
                
        // Set the image processing algorithms
        imgProcess_ = imgProcess;

        // Load the model
        try {

            model_ = tflite::FlatBufferModel::BuildFromFile(artifactPath);

            tflite::ops::builtin::BuiltinOpResolver resolver;
            tflite::InterpreterBuilder(*model_, resolver)(&interpreter_);

            // Set number of CPU threads for inference
            // Use the number of available CPU cores or a specific number (e.g., 4)
            int num_threads = std::thread::hardware_concurrency() - 2; // Get available CPU cores
            if (num_threads == 0) num_threads = 2; // Fallback if detection fails
            interpreter_->SetNumThreads(num_threads);
            // Set OpenMP threads (for operations that use OpenMP)
            omp_set_num_threads(num_threads);

            RCLCPP_INFO(inferenceNode->get_logger(), "TFLite interpreter using %d threads", num_threads);

            interpreter_->AllocateTensors();

            // Determine input and output dimensions
            for (auto i : interpreter_->inputs())
            {
                auto const *input_tensor = interpreter_->tensor(i);

                auto dims = std::vector<int>{}; 
                std::copy(
                    input_tensor->dims->data, input_tensor->dims->data + input_tensor->dims->size,
                    std::back_inserter(dims));

                inputNamesArr_.push_back(interpreter_->GetInputName(i));

                std::unordered_map<std::string, int> params_ = {{"width", input_tensor->dims->data[2]},
                       {"height", input_tensor->dims->data[1]},
                       {"channels", input_tensor->dims->data[0]}};
                paramsArr_.push_back(params_);

                RCLCPP_INFO(inferenceNode->get_logger(), "Input name: %s", input_tensor->name);
                RCLCPP_INFO(inferenceNode->get_logger(), "Input dimensions: %i x %i x %i", input_tensor->dims->data[2], input_tensor->dims->data[1], input_tensor->dims->data[0]);
            }

            for (auto o : interpreter_->outputs())
            {
                auto const *output_tensor = interpreter_->tensor(o);
                output_tensors_.push_back(output_tensor);

                auto dims = std::vector<int>{};
                std::copy(
                    output_tensor->dims->data, output_tensor->dims->data + output_tensor->dims->size,
                    std::back_inserter(dims));

                RCLCPP_INFO(inferenceNode->get_logger(), "Output name: %s", output_tensor->name);

                outputDimsArr_.push_back(dims);
            }

        }
        catch (const std::exception &ex) {
            RCLCPP_ERROR(inferenceNode->get_logger(), "Model failed to load: %s", ex.what());
            return false;
        }
        return true;
    }

    void RLInferenceModel::startInference() {
        // Reset the image processing algorithm.
        if (imgProcess_) {
            imgProcess_->reset();
        }
        doInference_ = true;
    }

    void RLInferenceModel::stopInference() {
        doInference_ = false;
    }

    void RLInferenceModel::sensorCB(const deepracer_interfaces_pkg::msg::EvoSensorMsg::SharedPtr msg) {
        if(!doInference_) {
            return;
        }
        try {
            for(size_t i = 0; i < inputNamesArr_.size(); ++i) {
                float* inputLayer = interpreter_->typed_input_tensor<float>(i);

                // Object that will hold the data sent to the inference engine post processed.
                cv::Mat retData;
                if (inputNamesArr_[i].find(STEREO) != std::string::npos)
                {
                    loadStereoImg<cv::Vec2b, float>(inputLayer, retData, imgProcess_, msg->images, paramsArr_[i]);
                }
                else if (inputNamesArr_[i].find(FRONT) != std::string::npos
                          || inputNamesArr_[i].find(LEFT) != std::string::npos
                          || inputNamesArr_[i].find(OBS) != std::string::npos) {
                    load1DImg<uchar, float>(inputLayer, retData, imgProcess_, msg->images.front(), paramsArr_[i]);
                }
                else if (inputNamesArr_[i].find(LIDAR) != std::string::npos){
                    loadLidarData(inputLayer, msg->lidar_data);
                }
                else {
                    RCLCPP_ERROR(inferenceNode->get_logger(), "Invalid input head");
                    return;
                }
                imgProcess_->reset();
            }
            // Do inference
            interpreter_->Invoke();

            // Last dimension of output is number of classes
            auto nClasses = outputDimsArr_[0].back();
            auto * outputData = output_tensors_[0]->data.f;

            auto inferMsg = deepracer_interfaces_pkg::msg::InferResultsArray();
            for (size_t i = 0; i < msg->images.size(); ++i) {
                // Send the image data over with the results
                inferMsg.images.push_back(msg->images[i]) ;
            }

            for (size_t label = 0; label < nClasses; ++label) {
                auto inferData = deepracer_interfaces_pkg::msg::InferResults();
                inferData.class_label = label;
                inferData.class_prob = outputData[label];
                // Set bounding box data to -1 to indicate to subscribers that this model offers no
                // localization information.
                inferData.x_min = -1.0;
                inferData.y_min = -1.0;
                inferData.x_max = -1.0;
                inferData.y_max = -1.0;
                inferMsg.results.push_back(inferData);
            }
            // Send results to all subscribers.
            resultPub_->publish(inferMsg);
        }
        catch (const std::exception &ex) {
            RCLCPP_ERROR(inferenceNode->get_logger(), "Inference failed %s", ex.what());
        }
    }
}
