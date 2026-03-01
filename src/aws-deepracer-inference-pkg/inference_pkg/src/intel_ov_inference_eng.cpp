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

#include "inference_pkg/intel_ov_inference_eng.hpp"
// ROS2 message headers
#include "deepracer_interfaces_pkg/msg/infer_results.hpp"
#include "deepracer_interfaces_pkg/msg/infer_results_array.hpp"

#include <exception>
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
     /// Helper method that loads the multi head model into the desired plugin.
     /// @returns Inference request object that will be used to perform inference
     /// @param artifactPath Path to the artifact (xml) file
     /// @param device String value of the device being used (CPU/GPU)
     /// @param core Reference to a ov::Core object.
     /// @param inputName Reference to the vector of input layer names
     /// @param outputName Reference to the output layers name, the method will populate this string
     /// @param compiledModel Reference to the compiled model object to be populated
     /// @param inferenceNode The inference node for logging
     ov::InferRequest setMultiHeadModel(std::string artifactPath, const std::string &device,
                                            ov::Core& core, std::vector<std::string> &inputNamesArr,
                                            std::string &outputName, ov::CompiledModel &compiledModel,
                                            std::shared_ptr<rclcpp::Node> inferenceNode) {

        RCLCPP_INFO(inferenceNode->get_logger(), "******* In setMultiHeadModel *******");
        // Validate the artifact path.
        auto strIdx = artifactPath.rfind('.');
        if (strIdx == std::string::npos) {
            throw InferenceExcept("Artifact missing file extension");
        }
        if (artifactPath.substr(strIdx+1) != "xml") {
            throw InferenceExcept("No xml extension found");
        }

        auto model = core.read_model(artifactPath);
        
        // Get input names from the model
        for (const auto& input : model->inputs()) {
            std::string inputName = input.get_any_name();
            if(inputName.rfind(OBS) != std::string::npos
               || inputName.rfind(LIDAR) != std::string::npos
               || inputName.rfind(FRONT) != std::string::npos
               || inputName.rfind(STEREO) != std::string::npos
               || inputName.rfind(LEFT) != std::string::npos) {
                inputNamesArr.push_back(inputName);
            }
        }
        
        // Get output name from the model
        if (!model->outputs().empty()) {
            outputName = model->outputs().begin()->get_any_name();
        }

        // Configure for optimal latency-focused execution
        ov::AnyMap config = {
            {ov::num_streams(1)},                              // Single stream for low-latency
            {ov::hint::performance_mode(ov::hint::PerformanceMode::LATENCY)},  // Optimize for latency
            {ov::hint::inference_precision(ov::element::f16)}  // Use FP16 for better performance
        };
        if (device == "CPU") {
            config.insert({ov::inference_num_threads(2)});                    // Limit to 2 threads
        }

        RCLCPP_INFO(inferenceNode->get_logger(), "Configuring OpenVINO for low-latency execution");
        
        compiledModel = core.compile_model(model, device, config);
        return compiledModel.create_infer_request();
     }

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

namespace IntelOVInferenceEngine {
    RLInferenceModel::RLInferenceModel(std::shared_ptr<rclcpp::Node> inferenceNodePtr, const std::string &sensorSubName)
     : doInference_(false)
    {
        inferenceNode = inferenceNodePtr;
        RCLCPP_INFO(inferenceNode->get_logger(), "Initializing RL Model");
        RCLCPP_INFO(inferenceNode->get_logger(), "%s", sensorSubName.c_str());
        // Subscribe to the sensor topic and set the call back
        sensorSub_ = inferenceNode->create_subscription<deepracer_interfaces_pkg::msg::EvoSensorMsg>(sensorSubName, 10, std::bind(&IntelOVInferenceEngine::RLInferenceModel::sensorCB, this, std::placeholders::_1));
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
        // Set the image processing algorithms
        imgProcess_ = imgProcess;
        // Load the model
        try {
            inferRequest_ = setMultiHeadModel(artifactPath, device, core_, inputNamesArr_,
                                     outputName_, compiledModel_, inferenceNode);
            
            // Cache input tensor pointers for performance
            inputTensorPtrs_.clear();
            for(size_t i = 0; i != inputNamesArr_.size(); ++i) {
                auto inputTensor = inferRequest_.get_input_tensor(i);
                auto shape = inputTensor.get_shape();
                
                // Cache the tensor data pointer
                inputTensorPtrs_.push_back(inputTensor.data<float>());
                
                std::unordered_map<std::string, int> params_;
                
                // Debug: Log tensor shape information
                RCLCPP_INFO(inferenceNode->get_logger(), "Input[%zu] '%s': shape dimensions = %zu", 
                           i, inputNamesArr_[i].c_str(), shape.size());
                std::string shapeStr = "[";
                for (size_t dim = 0; dim < shape.size(); ++dim) {
                    shapeStr += std::to_string(shape[dim]);
                    if (dim < shape.size() - 1) shapeStr += ", ";
                }
                shapeStr += "]";
                RCLCPP_INFO(inferenceNode->get_logger(), "Shape values: %s", shapeStr.c_str());
                
                if (shape.size() >= 4) {
                    // For NHWC format: [batch, height, width, channels]
                    params_ = {{"width", static_cast<int>(shape[2])},
                              {"height", static_cast<int>(shape[1])},
                              {"channels", static_cast<int>(shape[3])}};
                    RCLCPP_INFO(inferenceNode->get_logger(), "Parsed as NHWC: w=%d, h=%d, c=%d", 
                               params_["width"], params_["height"], params_["channels"]);
                } else if (shape.size() == 3) {
                    // For NHW format: [batch, height, width] 
                    params_ = {{"width", static_cast<int>(shape[2])},
                              {"height", static_cast<int>(shape[1])},
                              {"channels", static_cast<int>(shape[0])}};
                    RCLCPP_INFO(inferenceNode->get_logger(), "Parsed as NHW: w=%d, h=%d, c=%d", 
                               params_["width"], params_["height"], params_["channels"]);
                } else if (shape.size() == 2) {
                    // For 1D data like LIDAR: [batch, features]
                    params_ = {{"width", static_cast<int>(shape[1])},
                              {"height", 1},
                              {"channels", 1}};
                    RCLCPP_INFO(inferenceNode->get_logger(), "Parsed as 1D (LIDAR): features=%d", 
                               params_["width"]);
                }
                paramsArr_.push_back(params_);
            }
            
            // Cache output tensor pointer and shape for performance
            auto outputTensor = inferRequest_.get_output_tensor();
            outputTensorPtr_ = outputTensor.data<float>();
            outputShape_ = outputTensor.get_shape();
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
            // Use cached tensor pointers instead of fetching them every time
            for(size_t i = 0; i < inputNamesArr_.size(); ++i) {
                auto inputPtr = inputTensorPtrs_[i];

                // Object that will hold the data sent to the inference engine post processed.
                cv::Mat retData;
                if (inputNamesArr_[i].find(STEREO) != std::string::npos)
                {
                    loadStereoImg<cv::Vec2b, float>(inputPtr, retData, imgProcess_, msg->images, paramsArr_[i]);
                }
                else if (inputNamesArr_[i].find(FRONT) != std::string::npos
                          || inputNamesArr_[i].find(LEFT) != std::string::npos
                          || inputNamesArr_[i].find(OBS) != std::string::npos) {
                    load1DImg<uchar, float>(inputPtr, retData, imgProcess_, msg->images.front(), paramsArr_[i]);
                }
                else if (inputNamesArr_[i].find(LIDAR) != std::string::npos){
                    loadLidarData(inputPtr, msg->lidar_data);
                }
                else {
                    RCLCPP_ERROR(inferenceNode->get_logger(), "Invalid input head");
                    return;
                }
                imgProcess_->reset();
            }
            // Do inference
            inferRequest_.infer();

            // Use cached output tensor pointer and shape
            auto inferMsg = deepracer_interfaces_pkg::msg::InferResultsArray();
            for (size_t i = 0; i < msg->images.size(); ++i) {
                // Send the image data over with the results
                inferMsg.images.push_back(msg->images[i]) ;
            }

            for (size_t label = 0; label < outputShape_[1]; ++label) {
                auto inferData = deepracer_interfaces_pkg::msg::InferResults();
                inferData.class_label = label;
                inferData.class_prob = outputTensorPtr_[label];
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
