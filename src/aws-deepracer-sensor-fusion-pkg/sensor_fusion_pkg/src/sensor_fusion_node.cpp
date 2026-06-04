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

/*
This module creates the sensor_fusion_node which is responsible for collecting the
messages from all the sensors and publish the combined sensor message. It provides
services and functions to subscribe to the LiDAR and camera messages, configure LiDAR,
publish a combined sensor message, publish an overlay message with the lidar data
overlayed on top of the camera frame.

The node defines:
    A subscriber to the /rplidar_ros/scan topic published
    by the rplidar_ros with LiDAR data.
    A subscriber to the /camera_pkg/video_mjpeg topic published
    by the camera_pkg with the camera data.
    A subscriber to the /camera_pkg/display_mjpeg topic published
    by the camera_pkg with the display image data.
    sensorMsgPub_: A publisher to publish the message that combines
                   the camera data published from the camera package and
                   the LiDAR data published from the rplidar_ros package
                   (preprocessed in this node as per the LiDAR configuration).
    overlayImagePub_: A publisher to publish the Image message that has the LiDAR
                      overaly data on top of the camera frame to highlight the sectors
                      with an obstacle present behind the DeepRacer device.
    statusCheckService_: A service to find out the data status of the cameras and the LiDAR
                         sensors. Based on whether the single camera/stereo camera/LiDAR data
                         is being read by the node, the corresponding sensor status are set.
    lidarConfigService_: A service to configure LiDAR processing information for each model.
                         It allows to set the LiDAR preprocessing information like the maximum
                         distance, minimum distance, number of sectors etc., which will be used
                         to create the sensor message being published for running the inference
                         for the particular model selected.
*/

#include "rclcpp/rclcpp.hpp"
#include <sys/stat.h>
#include <thread>
#include <atomic>
#include <memory>
#include <unordered_map>
#include <vector>
#include <bitset>

#include "sensor_msgs/msg/laser_scan.hpp"
#include "sensor_msgs/msg/image.hpp"
#include "sensor_msgs/msg/compressed_image.hpp"
#if __has_include(<cv_bridge/cv_bridge.hpp>)
#include <cv_bridge/cv_bridge.hpp>
#elif __has_include(<cv_bridge/cv_bridge.h>)
#include <cv_bridge/cv_bridge.h>
#endif
#include "opencv2/opencv.hpp"
#include "image_transport/image_transport.hpp"

#include "deepracer_interfaces_pkg/msg/evo_sensor_msg.hpp"
#include "deepracer_interfaces_pkg/msg/camera_msg.hpp"
#include "deepracer_interfaces_pkg/srv/lidar_config_srv.hpp"
#include "deepracer_interfaces_pkg/srv/sensor_status_check_srv.hpp"

#include "sensor_fusion_pkg/lidar_overlay.hpp"
#include "sensor_fusion_pkg/utility.hpp"
#include "ament_index_cpp/get_package_share_directory.hpp"

// Convert radian values to degrees
#define RAD2DEG(x) ((x)*180./M_PI)

namespace SensorFusion {
    #define DEFAULT_IMAGE_WIDTH 480
    #define DEFAULT_IMAGE_HEIGHT 360

    // Default lidar configuration
    #define DEFAULT_LIDAR_CONFIGURATION_MIN_LIDAR_ANGLE -60.0
    #define DEFAULT_LIDAR_CONFIGURATION_MAX_LIDAR_ANGLE 60.0
    #define DEFAULT_LIDAR_CONFIGURATION_MIN_LIDAR_DIST 0.15
    #define DEFAULT_LIDAR_CONFIGURATION_MAX_LIDAR_DIST 1.0
    #define DEFAULT_LIDAR_CONFIGURATION_LIDAR_CLIPPING_DIST 1.0
    #define DEFAULT_LIDAR_CONFIGURATION_NUM_LIDAR_VALUES 64
    #define DEFAULT_LIDAR_CONFIGURATION_NUM_LIDAR_SECTORS 64
    // Default value set to 0 - No preprocessing required
    #define DEFAULT_LIDAR_CONFIGURATION_PREPROCESS_TYPE 0

    // Default lidar overlay configuration
    #define DEFAULT_LIDAR_OVERLAY_CONFIGURATION_MIN_LIDAR_ANGLE -150.0
    #define DEFAULT_LIDAR_OVERLAY_CONFIGURATION_MAX_LIDAR_ANGLE 150.0
    #define DEFAULT_LIDAR_OVERLAY_CONFIGURATION_MIN_LIDAR_DIST 0.15
    #define DEFAULT_LIDAR_OVERLAY_CONFIGURATION_MAX_LIDAR_DIST 0.5
    #define DEFAULT_LIDAR_OVERLAY_CONFIGURATION_NUM_LIDAR_VALUES 64
    #define DEFAULT_LIDAR_OVERLAY_CONFIGURATION_NUM_LIDAR_SECTORS 8
    // Lidar overlay constants
    // Transparency factor.
    #define DEFAULT_LIDAR_OVERLAY_CONFIGURATION_LIDAR_OVERLAY_ALPHA 0.8
    // px
    #define DEFAULT_LIDAR_OVERLAY_CONFIGURATION_LIDAR_OVERLAY_LINE_WIDTH 1
    // number of sectors
    #define DEFAULT_LIDAR_OVERLAY_CONFIGURATION_LIDAR_OVERLAY_NUM_SECTORS 8
    /// Enum that references the lidar preprocessing keys.
    enum LidarPreprocessingType {
        // No processing
        defaultProcessing,
        // Preprocess the lidar values by splitting them to
        // sectors and converting to binary values
        sector,
        numLidarPreprocessingType
    };

    enum CameraMode {
        CAMERA_LEGACY_MODE,
        CAMERA_MODERN_MODE
    };

    // Message Topics to publish to.
    const char* SENSOR_MSG_TOPIC = "sensor_msg";
    const char* OVERLAY_MSG_TOPIC = "overlay_msg";
    const char* SENSOR_DATA_STATUS_SERVICE_NAME = "sensor_data_status";
    const char* CONFIGURE_LIDAR_SERVICE_NAME = "configure_lidar";

    // Message topics to subscribe to.
    const char* CAMERA_MSG_TOPIC = "/camera_pkg/video_mjpeg";
    const char* DISPLAY_MSG_TOPIC = "/camera_pkg/display_mjpeg";
    const char* COMP_IMG_MSG_TOPIC = "/camera_pkg/display_mjpeg/compressed";
    const char* LIDAR_MSG_TOPIC = "/rplidar_ros/scan";

    // Sensor configuration file path.
    const char* SENSOR_CONFIGURATION_FILE_PATH = "/opt/aws/deepracer/sensor_configuration.json";

    // Keys for the sensor configuration file
    const std::string LIDAR_KEY = "lidar";
    const std::string LIDAR_OVERLAY_KEY = "lidar_overlay";

    // Keys in the sensor fusion node lidar configuration dictionary
    const std::string LIDAR_CONFIG_NUM_LIDAR_VALUES_KEY = "num_values";
    const std::string LIDAR_CONFIG_MIN_LIDAR_ANGLE_KEY = "min_angle";
    const std::string LIDAR_CONFIG_MAX_LIDAR_ANGLE_KEY = "max_angle";
    const std::string LIDAR_CONFIG_MIN_LIDAR_DIST_KEY = "min_distance";
    const std::string LIDAR_CONFIG_MAX_LIDAR_DIST_KEY = "max_distance";
    const std::string LIDAR_CONFIG_NUM_LIDAR_SECTORS_KEY = "num_sectors";

    // Keys in the sensor fusion node lidar configuration dictionary
    const std::string LIDAR_CONFIG_LIDAR_CLIPPING_DIST_KEY = "clipping_distance";
    const std::string LIDAR_CONFIG_PREPROCESS_TYPE_KEY = "preprocess_type";

    class SensorFusionNode : public rclcpp::Node
    {
    /// This class creates the sensor_fusion_node responsible to collect data from the cameras and LiDAR
    /// and publish it as sensor message.

    public:

        /// Initialize the SensorFusionNode.
        /// @param node_name Name of the node to be created.
        SensorFusionNode(const std::string & node_name)
        : Node(node_name),
          node_handle_(std::shared_ptr<SensorFusionNode>(this, [](auto *) {})),
          image_transport_(std::shared_ptr<rclcpp::Node>(this, [](auto *) {})),
          lidarOverlayProcessingObj_(LidarOverlay()),
          enableOverlay_(true),
          enableGrayOverlay_(false),
          imageWidth_(DEFAULT_IMAGE_WIDTH),
          imageHeight_(DEFAULT_IMAGE_HEIGHT)
        {

            RCLCPP_INFO(this->get_logger(), "%s started", node_name.c_str());
            this->declare_parameter<std::string>("image_transport", "raw");
            this->declare_parameter<std::string>("camera_mode", "legacy");
            std::string mode_param = this->get_parameter("camera_mode").as_string();
            mode_ = (mode_param == "modern") ? CAMERA_MODERN_MODE : CAMERA_LEGACY_MODE;
            if (mode_param != "legacy" && mode_param != "modern") {
                RCLCPP_ERROR(this->get_logger(), "Invalid mode parameter value. Defaulting to legacy.");
            }
            this->declare_parameter<bool>("enable_overlay", true);
            enableOverlay_ = this->get_parameter("enable_overlay").as_bool();
            this->declare_parameter<bool>("enable_gray_overlay", false);
            enableGrayOverlay_ = this->get_parameter("enable_gray_overlay").as_bool();
            if (enableGrayOverlay_) {
                loadGrayOverlay();
            }
            createDefaultSensorConfiguration();
            if (checkFile(SENSOR_CONFIGURATION_FILE_PATH)) {
                setSensorConfigurationFromFile(sensorConfiguration_,
                                              SENSOR_CONFIGURATION_FILE_PATH);
            }
            else {
                writeSensorConfigJSON(sensorConfiguration_,
                                     SENSOR_CONFIGURATION_FILE_PATH);
            }
            // Update the maximum LiDAR distance based on the sensor configuration.
            maxLiDARDist_ = std::min(sensorConfiguration_[LIDAR_KEY][LIDAR_CONFIG_MAX_LIDAR_DIST_KEY],
                                     sensorConfiguration_[LIDAR_KEY][LIDAR_CONFIG_LIDAR_CLIPPING_DIST_KEY]);

            // Define the LiDAR overlay configuration. Default to use SectorPreprocessing and
            // 8 sectors.
            lidarOverlayProcessingObj_.init(sensorConfiguration_[LIDAR_OVERLAY_KEY], imageWidth_, imageHeight_);

            // Publisher that sends combined sensor messages with camera data and LiDAR data
            // to inference node.
            sensorMsgPub_ = this->create_publisher<deepracer_interfaces_pkg::msg::EvoSensorMsg>(SENSOR_MSG_TOPIC, 1);

            // Publisher to publish the overlay message with sector LiDAR information
            // overlayed over the camera image frame.
            if (enableOverlay_ || enableGrayOverlay_)
                overlayImagePub_ = image_transport_.advertise(OVERLAY_MSG_TOPIC, 1);
            
            statusCheckService_ = this->create_service<deepracer_interfaces_pkg::srv::SensorStatusCheckSrv>(
                                                                                SENSOR_DATA_STATUS_SERVICE_NAME,
                                                                                std::bind(&SensorFusionNode::statusCheckCallback,
                                                                                          this,
                                                                                          std::placeholders::_1,
                                                                                          std::placeholders::_2,
                                                                                          std::placeholders::_3));

            lidarConfigService_ = this->create_service<deepracer_interfaces_pkg::srv::LidarConfigSrv>(
                                                                                CONFIGURE_LIDAR_SERVICE_NAME,
                                                                                std::bind(&SensorFusionNode::setLidarConfigCallback,
                                                                                          this,
                                                                                          std::placeholders::_1,
                                                                                          std::placeholders::_2,
                                                                                          std::placeholders::_3));
                                                                                         
            auto sensorMsgQOS = rclcpp::QoS(rclcpp::KeepLast(1));
            sensorMsgQOS.best_effort();
            // Subscriber to subscribe to the lidar scan messages published by the LiDAR.
            lidarSub_ = this->create_subscription<sensor_msgs::msg::LaserScan>(LIDAR_MSG_TOPIC,
                                                                               sensorMsgQOS,
                                                                               std::bind(&SensorFusionNode::lidarCB,
                                                                                         this,
                                                                                         std::placeholders::_1));
            // Subscriber to subscribe to the camera sensor messages published by the camera_pkg.
            if (mode_ == CAMERA_LEGACY_MODE) {
                cameraSub_ = this->create_subscription<deepracer_interfaces_pkg::msg::CameraMsg>(std::string(CAMERA_MSG_TOPIC),
                                                                                                sensorMsgQOS,
                                                                                                std::bind(&SensorFusionNode::cameraCB,
                                                                                                          this,
                                                                                                          std::placeholders::_1));
            } else {
                cameraModernSub_ = this->create_subscription<sensor_msgs::msg::CompressedImage>(std::string(COMP_IMG_MSG_TOPIC),
                                                                                             sensorMsgQOS,
                                                                                             std::bind(&SensorFusionNode::cameraModernCB,
                                                                                                       this,
                                                                                                       std::placeholders::_1));
            }
            if (enableOverlay_ || enableGrayOverlay_) {
                // Subscriber to subscribe to the camera display messages published by the camera_pkg.
                image_transport::TransportHints ith(this);
                RCLCPP_INFO(this->get_logger(), "image_transport configured to use %s", ith.getTransport().c_str());
                displaySub_ = image_transport_.subscribe<SensorFusionNode>(DISPLAY_MSG_TOPIC, 1,
                                                                        &SensorFusionNode::displayCB,
                                                                        node_handle_, &ith);
            }
            cameraImageCount_ = 0;
        }
        ~SensorFusionNode() = default;
    private:
        /// Create sensor configuration with default LiDAR configuration.
        void createDefaultSensorConfiguration(){
            sensorConfiguration_ = {
                {LIDAR_KEY, {
                    {LIDAR_CONFIG_MIN_LIDAR_ANGLE_KEY, DEFAULT_LIDAR_CONFIGURATION_MIN_LIDAR_ANGLE},
                    {LIDAR_CONFIG_MAX_LIDAR_ANGLE_KEY, DEFAULT_LIDAR_CONFIGURATION_MAX_LIDAR_ANGLE},
                    {LIDAR_CONFIG_MIN_LIDAR_DIST_KEY, DEFAULT_LIDAR_CONFIGURATION_MIN_LIDAR_DIST},
                    {LIDAR_CONFIG_MAX_LIDAR_DIST_KEY, DEFAULT_LIDAR_CONFIGURATION_MAX_LIDAR_DIST},
                    {LIDAR_CONFIG_LIDAR_CLIPPING_DIST_KEY, DEFAULT_LIDAR_CONFIGURATION_LIDAR_CLIPPING_DIST},
                    {LIDAR_CONFIG_NUM_LIDAR_VALUES_KEY, DEFAULT_LIDAR_CONFIGURATION_NUM_LIDAR_VALUES},
                    {LIDAR_CONFIG_NUM_LIDAR_SECTORS_KEY, DEFAULT_LIDAR_CONFIGURATION_NUM_LIDAR_SECTORS},
                    {LIDAR_CONFIG_PREPROCESS_TYPE_KEY, DEFAULT_LIDAR_CONFIGURATION_PREPROCESS_TYPE}}},
                {LIDAR_OVERLAY_KEY, {
                    {LIDAR_OVERLAY_CONFIG_MIN_LIDAR_ANGLE_KEY, DEFAULT_LIDAR_OVERLAY_CONFIGURATION_MIN_LIDAR_ANGLE},
                    {LIDAR_OVERLAY_CONFIG_MAX_LIDAR_ANGLE_KEY, DEFAULT_LIDAR_OVERLAY_CONFIGURATION_MAX_LIDAR_ANGLE},
                    {LIDAR_OVERLAY_CONFIG_MIN_LIDAR_DIST_KEY, DEFAULT_LIDAR_OVERLAY_CONFIGURATION_MIN_LIDAR_DIST},
                    {LIDAR_OVERLAY_CONFIG_MAX_LIDAR_DIST_KEY, DEFAULT_LIDAR_OVERLAY_CONFIGURATION_MAX_LIDAR_DIST},
                    {LIDAR_OVERLAY_CONFIG_NUM_LIDAR_VALUES_KEY, DEFAULT_LIDAR_OVERLAY_CONFIGURATION_NUM_LIDAR_VALUES},
                    {LIDAR_OVERLAY_CONFIG_NUM_LIDAR_SECTORS_KEY, DEFAULT_LIDAR_OVERLAY_CONFIGURATION_NUM_LIDAR_SECTORS},
                    {LIDAR_OVERLAY_CONFIG_LIDAR_OVERLAY_ALPHA_KEY, DEFAULT_LIDAR_OVERLAY_CONFIGURATION_LIDAR_OVERLAY_ALPHA},
                    {LIDAR_OVERLAY_CONFIG_LIDAR_OVERLAY_LINE_WIDTH_KEY, DEFAULT_LIDAR_OVERLAY_CONFIGURATION_LIDAR_OVERLAY_LINE_WIDTH},
                    {LIDAR_OVERLAY_CONFIG_LIDAR_OVERLAY_NUM_SECTORS_KEY, DEFAULT_LIDAR_OVERLAY_CONFIGURATION_LIDAR_OVERLAY_NUM_SECTORS}}}};
        }

        /// Callback function for camera message subscription.
        /// @param msg Message with images from DeepRacer cameras.
        void cameraCB(const deepracer_interfaces_pkg::msg::CameraMsg::SharedPtr msg) {
            try {
                lastCameraMsgRecievedTime = std::chrono::steady_clock::now();
                cameraImageCount_ = msg->images.size();
                auto sensorMsg = deepracer_interfaces_pkg::msg::EvoSensorMsg();
                sensorMsg.images = msg->images;
                if (enableGrayOverlay_) {
                    for (auto & compImg : sensorMsg.images) {
                        cv::Mat img = cv::imdecode(cv::Mat(compImg.data), cv::IMREAD_COLOR);
                        if (!img.empty()) {
                            applyGrayOverlay(img);
                            std::vector<uchar> buf;
                            cv::imencode(".jpg", img, buf);
                            compImg.data = buf;
                        }
                    }
                }
                // Update the LiDAR data with sector LiDAR data based on preprocessing configuration
                if(sensorConfiguration_[LIDAR_KEY][LIDAR_CONFIG_PREPROCESS_TYPE_KEY] == sector){
                    std::lock_guard<std::mutex> guard(lidarMutex_);
                    size_t blockSize = lidarData_.size()/sensorConfiguration_[LIDAR_KEY][LIDAR_CONFIG_NUM_LIDAR_SECTORS_KEY];
                    auto sectorLidarData = binarySectorizeLidarData(lidarData_, blockSize, maxLiDARDist_);
                    sensorMsg.lidar_data = sectorLidarData;
                } else {
                    std::lock_guard<std::mutex> guard(lidarMutex_);
                    // Set LiDAR data by default
                    sensorMsg.lidar_data = lidarData_; 
                }
                this->sensorMsgPub_->publish(sensorMsg);  // Publish it along.
            }
            catch (const std::exception &ex) {
                RCLCPP_ERROR(this->get_logger(), "Camera callback failed: %s", ex.what());
            }
        }


        /// Callback function for camera message subscription.
        /// @param msg Message with images from DeepRacer cameras.
        void cameraModernCB(const sensor_msgs::msg::CompressedImage::SharedPtr msg) {
            try {
                auto camera_msg = std::make_shared<deepracer_interfaces_pkg::msg::CameraMsg>();
                camera_msg->images.push_back(*msg);
                cameraCB(camera_msg);
            }
            catch (const std::exception &ex) {
                RCLCPP_ERROR(this->get_logger(), "Camera callback failed: %s", ex.what());
            }
        }

        /// Callback function for camera message subscription.
        /// @param msg Message with images from DeepRacer cameras.
        void displayCB(const sensor_msgs::msg::Image::ConstSharedPtr & msg) {
            try {
                cv::Mat resizedImg;
                if (msg->height > imageHeight_) {
                    cv::resize(cv_bridge::toCvCopy(msg, "bgr8")->image, resizedImg, cv::Size(imageWidth_, imageHeight_));
                } else {
                    resizedImg = cv_bridge::toCvCopy(msg, "bgr8")->image;
                }

                applyGrayOverlay(resizedImg);

                if (enableOverlay_) {
                    std::chrono::duration<float> timeSinceLastLidar = std::chrono::steady_clock::now() - lastLidarMsgRecievedTime;
                    std::chrono::duration<float> LIDAR_DATA_MAX_AGE(1.0);
                    if (timeSinceLastLidar < LIDAR_DATA_MAX_AGE) {
                        std::bitset<8> sectorOverlayValues;
                        {
                            std::lock_guard<std::mutex> guard(lidarMutex_);
                            size_t blockSize = overlayLidarData_.size()/sensorConfiguration_[LIDAR_OVERLAY_KEY][LIDAR_OVERLAY_CONFIG_LIDAR_OVERLAY_NUM_SECTORS_KEY];
                            if(blockSize == 8){
                                auto overlaySectorLidarData = binarySectorizeLidarData(overlayLidarData_,
                                                                                    blockSize,
                                                                                    sensorConfiguration_[LIDAR_OVERLAY_KEY][LIDAR_OVERLAY_CONFIG_MAX_LIDAR_DIST_KEY]);
                                for(size_t sector_idx = 0; sector_idx < overlaySectorLidarData.size(); sector_idx++){
                                    sectorOverlayValues[sector_idx] = (int)overlaySectorLidarData[sector_idx];
                                }
                            }
                        }
                        cv::Mat overlayCVImage = lidarOverlayProcessingObj_.overlayLidarDataOnImage(resizedImg, sectorOverlayValues);
                        overlayImagePub_.publish(*(cv_bridge::CvImage(std_msgs::msg::Header(), "bgr8", overlayCVImage).toImageMsg().get()));
                        return;
                    }
                }

                overlayImagePub_.publish(*(cv_bridge::CvImage(std_msgs::msg::Header(), "bgr8", resizedImg).toImageMsg().get()));
            }
            catch (const std::exception &ex) {
                RCLCPP_ERROR(this->get_logger(), "Display callback failed: %s", ex.what());
            }
        }

        /// Callback function for LiDAR scan message subscription.
        /// @param msg Message with raw data from LiDAR.
        void lidarCB(const sensor_msgs::msg::LaserScan::SharedPtr msg) {
            try {
                lastLidarMsgRecievedTime = std::chrono::steady_clock::now();
                std::vector<float> overlayRanges, overlayDegrees, lidarRanges, lidarDegrees;
                for (size_t i = 0; i < msg->ranges.size(); i++) {
                    float degree = RAD2DEG(msg->angle_min + msg->angle_increment * i);
                    if(degree >= sensorConfiguration_[LIDAR_KEY][LIDAR_CONFIG_MIN_LIDAR_ANGLE_KEY] &&
                       degree <= sensorConfiguration_[LIDAR_KEY][LIDAR_CONFIG_MAX_LIDAR_ANGLE_KEY]){
                        if(std::isinf(msg->ranges[i])) {
                            lidarRanges.push_back(maxLiDARDist_);
                        }
                        else {
                            lidarRanges.push_back(std::min(std::max(static_cast<float>(msg->ranges[i]),
                            sensorConfiguration_[LIDAR_KEY][LIDAR_CONFIG_MIN_LIDAR_DIST_KEY]),
                            maxLiDARDist_));
                        }
                        lidarDegrees.push_back(degree);
                    }
                    overlayRanges.push_back(std::min(std::max(static_cast<float>(msg->ranges[i]),
                                            sensorConfiguration_[LIDAR_OVERLAY_KEY][
                                             LIDAR_OVERLAY_CONFIG_MIN_LIDAR_DIST_KEY]),
                                            sensorConfiguration_[LIDAR_OVERLAY_KEY][
                                             LIDAR_OVERLAY_CONFIG_MAX_LIDAR_DIST_KEY]));
                    overlayDegrees.push_back(degree);
                }

                auto desiredLidarDegrees = linspace(sensorConfiguration_[LIDAR_KEY][LIDAR_CONFIG_MIN_LIDAR_ANGLE_KEY],
                                                    sensorConfiguration_[LIDAR_KEY][LIDAR_CONFIG_MAX_LIDAR_ANGLE_KEY],
                                                    sensorConfiguration_[LIDAR_KEY][LIDAR_CONFIG_NUM_LIDAR_VALUES_KEY]);

                auto desiredOverlayLidarDegrees = linspace(sensorConfiguration_[LIDAR_OVERLAY_KEY][LIDAR_OVERLAY_CONFIG_MIN_LIDAR_ANGLE_KEY],
                                                           sensorConfiguration_[LIDAR_OVERLAY_KEY][LIDAR_OVERLAY_CONFIG_MAX_LIDAR_ANGLE_KEY],
                                                           sensorConfiguration_[LIDAR_OVERLAY_KEY][LIDAR_OVERLAY_CONFIG_NUM_LIDAR_VALUES_KEY]);

                // Add the min/max lidarDegrees and ranges for interpolation in case not present.
                if(!std::count(lidarDegrees.begin(), lidarDegrees.end(), sensorConfiguration_[LIDAR_KEY][LIDAR_CONFIG_MIN_LIDAR_ANGLE_KEY])) {
                    lidarDegrees.insert(lidarDegrees.begin(), sensorConfiguration_[LIDAR_KEY][LIDAR_CONFIG_MIN_LIDAR_ANGLE_KEY]);
                    lidarDegrees.push_back(sensorConfiguration_[LIDAR_KEY][LIDAR_CONFIG_MAX_LIDAR_ANGLE_KEY]);
                    lidarRanges.insert(lidarRanges.begin(), maxLiDARDist_);
                    lidarRanges.push_back(maxLiDARDist_);
                }
                std::lock_guard<std::mutex> guard(lidarMutex_);
                lidarData_ = interp(desiredLidarDegrees, lidarDegrees, lidarRanges);
                overlayLidarData_ = interp(desiredOverlayLidarDegrees, overlayDegrees, overlayRanges);
            }
            catch (const std::exception &ex) {
                RCLCPP_ERROR(this->get_logger(), "LiDAR callback failed: %s", ex.what());
            }
        }

        /// Loads the gray fade overlay image from the package share directory.
        void loadGrayOverlay() {
            try {
                std::string pkg_share = ament_index_cpp::get_package_share_directory("sensor_fusion_pkg");
                std::string overlay_path = pkg_share + "/images/fade_gray_overlay.png";
                grayOverlay_ = cv::imread(overlay_path, cv::IMREAD_UNCHANGED);
                if (grayOverlay_.empty()) {
                    RCLCPP_WARN(this->get_logger(), "Gray overlay image not found at %s", overlay_path.c_str());
                } else {
                    RCLCPP_INFO(this->get_logger(), "Loaded gray overlay image (%dx%d, channels=%d)",
                                grayOverlay_.cols, grayOverlay_.rows, grayOverlay_.channels());
                }
            }
            catch (const std::exception &ex) {
                RCLCPP_WARN(this->get_logger(), "Failed to load gray overlay image: %s", ex.what());
            }
        }

        /// Blends the gray fade overlay onto an BGR image in-place using per-pixel alpha compositing.
        /// The overlay PNG's alpha channel controls the blend weight at each pixel.
        /// Has no effect if enable_gray_overlay is false or the overlay image is not loaded.
        /// Precomputes the two cached float32 blend mats from grayOverlayResized_.
        /// Must be called whenever grayOverlayResized_ changes.
        void prepareOverlayCache() {
            std::vector<cv::Mat> channels;
            cv::split(grayOverlayResized_, channels);

            cv::Mat overlayBGR;
            cv::Mat alphaNorm;
            if (channels.size() == 4) {
                std::vector<cv::Mat> bgrChannels = {channels[0], channels[1], channels[2]};
                cv::merge(bgrChannels, overlayBGR);
                channels[3].convertTo(alphaNorm, CV_32F, 1.0 / 255.0);
            } else {
                overlayBGR = grayOverlayResized_;
                alphaNorm = cv::Mat(grayOverlayResized_.size(), CV_32F, cv::Scalar(1.0));
            }

            cv::Mat alpha3;
            std::vector<cv::Mat> alphaChannels = {alphaNorm, alphaNorm, alphaNorm};
            cv::merge(alphaChannels, alpha3);

            cv::Mat overlay32;
            overlayBGR.convertTo(overlay32, CV_32FC3);
            overlayBGRPremul_ = overlay32.mul(alpha3);           // overlay * alpha
            oneMinusAlpha3_   = cv::Scalar(1, 1, 1) - alpha3;   // 1 - alpha
        }

        /// Blends the gray fade overlay onto a BGR image in-place using cached alpha compositing.
        /// Has no effect if enable_gray_overlay is false or the overlay image is not loaded.
        void applyGrayOverlay(cv::Mat & image) {
            if (!enableGrayOverlay_ || grayOverlay_.empty() || image.empty()) {
                return;
            }
            // Resize overlay and rebuild cache when image dimensions change.
            if (grayOverlayResized_.size() != image.size()) {
                cv::resize(grayOverlay_, grayOverlayResized_, image.size(), 0, 0, cv::INTER_LINEAR);
                prepareOverlayCache();
            }
            // Hot path: result = src * (1-alpha) + overlay_premul
            cv::Mat src32;
            image.convertTo(src32, CV_32FC3);
            cv::Mat result32 = src32.mul(oneMinusAlpha3_) + overlayBGRPremul_;
            result32.convertTo(image, CV_8UC3);
        }

        /// Function to sectorize the lidarData to represent sectors where an object is detected.
        std::vector<float> binarySectorizeLidarData(const std::vector<float>& lidarData, size_t blockSize, float maxDist){
            std::vector<float> sectorLidarData;
            for(size_t i = 0; i < lidarData.size(); i += blockSize) {
                bool setBit = false;
                for(size_t b = 0; b < blockSize; b++) {
                    setBit = setBit || (lidarData[i+b] < maxDist);
                }
                sectorLidarData.push_back((setBit) ? 1 : 0);
            }
            return sectorLidarData;
        }
 
        /// Callback function for the statusCheckService_ service to return the status of the
        /// sensors based on the presence of data in the data buffer at the sensor fusion node.
        void statusCheckCallback(const std::shared_ptr<rmw_request_id_t> request_header,
                                 std::shared_ptr<deepracer_interfaces_pkg::srv::SensorStatusCheckSrv::Request> req,
                                 std::shared_ptr<deepracer_interfaces_pkg::srv::SensorStatusCheckSrv::Response> res) {
            try {
                (void)request_header; 
                (void)req;

                res->single_camera_status = 0;
                res->stereo_camera_status = 0;
                res->lidar_status = 0;
                std::chrono::steady_clock::time_point now = std::chrono::steady_clock::now();
                if(std::chrono::duration_cast<std::chrono::seconds>(now - lastLidarMsgRecievedTime).count() > 1) {
                    res->lidar_status = 1;
                }
                if(cameraImageCount_ != 2){
                    res->stereo_camera_status = 1;
                }
                if (cameraImageCount_ != 1) {
                    res->single_camera_status = 1;
                }
                if(std::chrono::duration_cast<std::chrono::seconds>(now - lastCameraMsgRecievedTime).count() > 1) {
                    res->stereo_camera_status = 1;
                    res->single_camera_status = 1;
                }
            }
            catch (const std::exception &ex) {
                RCLCPP_ERROR(this->get_logger(), "statusCheckCallback failed: %s", ex.what());
            }

         }

        /// Callback method for the lidarConfigService_ service. Allows clients to dynamically
        /// set the LiDAR configuration: min_angle, max_angle, min_distance,
        /// max_distance, num_values, clipping_distance, num_sectors, preprocess_type.
        void setLidarConfigCallback(const std::shared_ptr<rmw_request_id_t> request_header,
                                     std::shared_ptr<deepracer_interfaces_pkg::srv::LidarConfigSrv::Request> req,
                                     std::shared_ptr<deepracer_interfaces_pkg::srv::LidarConfigSrv::Response> res) {
            try {
                (void)request_header; 
                if(req->min_angle > req->max_angle ||
                   req->min_distance > req->max_distance ||
                   req->min_distance > req->clipping_distance ||
                   req->num_values < 1){
                    RCLCPP_ERROR(this->get_logger(), "Incorrect lidar configuration values.");
                    res->error = 1;
                    return;
                }
                // Check if the preprocessing is valid
                if(req->preprocess_type < 0 || req->preprocess_type >= numLidarPreprocessingType){
                    RCLCPP_ERROR(this->get_logger(), "Incorrect lidar preprocess type");
                    res->error = 1;
                    return;
                }
                sensorConfiguration_[LIDAR_KEY][LIDAR_CONFIG_MIN_LIDAR_ANGLE_KEY] = req->min_angle;
                sensorConfiguration_[LIDAR_KEY][LIDAR_CONFIG_MAX_LIDAR_ANGLE_KEY] = req->max_angle;
                sensorConfiguration_[LIDAR_KEY][LIDAR_CONFIG_MIN_LIDAR_DIST_KEY] = req->min_distance;
                sensorConfiguration_[LIDAR_KEY][LIDAR_CONFIG_MAX_LIDAR_DIST_KEY] = req->max_distance;
                sensorConfiguration_[LIDAR_KEY][LIDAR_CONFIG_NUM_LIDAR_VALUES_KEY] = req->num_values;
                sensorConfiguration_[LIDAR_KEY][LIDAR_CONFIG_LIDAR_CLIPPING_DIST_KEY] = req->clipping_distance;
                sensorConfiguration_[LIDAR_KEY][LIDAR_CONFIG_NUM_LIDAR_SECTORS_KEY] = req->num_sectors;
                sensorConfiguration_[LIDAR_KEY][LIDAR_CONFIG_PREPROCESS_TYPE_KEY] = req->preprocess_type;
                
                // Select the minimum of the clipping distance and max_lidar_distance as upper bound of the range
                maxLiDARDist_ = std::min(sensorConfiguration_[LIDAR_KEY][LIDAR_CONFIG_MAX_LIDAR_DIST_KEY],
                                         sensorConfiguration_[LIDAR_KEY][LIDAR_CONFIG_LIDAR_CLIPPING_DIST_KEY]);
                RCLCPP_INFO(this->get_logger(), "Setting the lidar configuration values for the model");
                res->error = 0;
                return;
            }
            catch (const std::exception &ex) {
                RCLCPP_ERROR(this->get_logger(), "setLidarConfigCallback failed: %s", ex.what());
            }

         }
        
        /// Writes the given sensor configuration map to file
        /// @param sensorConfiguration Sensor configuration file to write to file
        /// @param filePath Full path to the desired file for which to write the given sensor configuration map.
        void writeSensorConfigJSON(const std::unordered_map<std::string, std::unordered_map<std::string, float>> &sensorConfiguration,
                                   const std::string &filePath) {
            try {
                Json::Value sensorConfigJsonValue;
                auto itLidarConfig = sensorConfiguration.find(LIDAR_KEY);
                auto itLidarOverlayConfig = sensorConfiguration.find(LIDAR_OVERLAY_KEY);

                if (itLidarConfig != sensorConfiguration.end() && itLidarOverlayConfig != sensorConfiguration.end()) {
                    for (auto lidarConfigMap : itLidarConfig->second) {
                        sensorConfigJsonValue[LIDAR_KEY][lidarConfigMap.first] = lidarConfigMap.second;
                    }
                    for (auto lidarOverlayConfigMap : itLidarOverlayConfig->second) {
                        sensorConfigJsonValue[LIDAR_OVERLAY_KEY][lidarOverlayConfigMap.first] = lidarOverlayConfigMap.second;
                    }
                }
                else {
                    RCLCPP_ERROR(this->get_logger(), "Invalid sensor configuration map");
                    return;
                }
                writeJSONToFile(sensorConfigJsonValue, filePath);
            }
            catch (const std::exception &ex) {
                RCLCPP_ERROR(this->get_logger(), "writeSensorConfigJSON failed: %s", ex.what());
            }

        }

        /// Reads the sensor configuration data from the desired file and stores the values in memory
        /// @param sensorConfiguration Map to store the sensor configuration read from file
        /// @param filePath Full file path of the file containing the sensor configuration details, note the client verifies existence
        void setSensorConfigurationFromFile(std::unordered_map<std::string, std::unordered_map<std::string, float>> &sensorConfiguration,
                                           const std::string &filePath) {
            try {
                Json::Value sensorConfigJsonValue;
                Json::Reader reader;
                std::ifstream ifs(filePath);
        
                if (!reader.parse(ifs, sensorConfigJsonValue)) {
                    RCLCPP_ERROR(this->get_logger(), "Error parsing sensor_configuration.json");
                    return;
                }
                if (!sensorConfigJsonValue.isMember(LIDAR_KEY) || !sensorConfigJsonValue.isMember(LIDAR_OVERLAY_KEY)) {
                    RCLCPP_ERROR(this->get_logger(), "Sensor Configuration file error: Missing servo type");
                    return;
                }

                auto populateMap = [&](auto &map, const auto &configType) {
                    for (auto &sensorConfigMap : map) {
                        if (sensorConfigJsonValue[configType].isMember(sensorConfigMap.first)) {
                            sensorConfigMap.second = sensorConfigJsonValue[configType][sensorConfigMap.first].asFloat();
                        }
                        else {
                            RCLCPP_ERROR(this->get_logger(), "Sensor Configuration file error:%s missing: %s", configType.c_str(), sensorConfigMap.first.c_str());
                            return false;
                        }
                    }
                    return true;
                };
        
                auto tmpMap = sensorConfiguration;
                auto itLidarConfig = tmpMap.find(LIDAR_KEY);
                auto itLidarOverlayConfig = tmpMap.find(LIDAR_OVERLAY_KEY);
        
                if (itLidarConfig != tmpMap.end() && itLidarOverlayConfig != tmpMap.end()) {
                    if (!populateMap(itLidarConfig->second, LIDAR_KEY) || !populateMap(itLidarOverlayConfig->second, LIDAR_OVERLAY_KEY)) {
                        return;
                    }
                }
                else {
                    RCLCPP_ERROR(this->get_logger(), "Invalid sensor configuration map");
                    return;
                }
                sensorConfiguration = tmpMap;
            }
            catch (const std::exception &ex) {
                RCLCPP_ERROR(this->get_logger(), "setSensorConfigurationFromFile failed: %s", ex.what());
            }

        }

        rclcpp::Subscription<sensor_msgs::msg::LaserScan>::SharedPtr lidarSub_;
        rclcpp::Subscription<deepracer_interfaces_pkg::msg::CameraMsg>::SharedPtr cameraSub_;
        image_transport::Subscriber displaySub_;
        rclcpp::Subscription<sensor_msgs::msg::CompressedImage>::SharedPtr cameraModernSub_;

        rclcpp::Service<deepracer_interfaces_pkg::srv::LidarConfigSrv>::SharedPtr lidarConfigService_;
        rclcpp::Service<deepracer_interfaces_pkg::srv::SensorStatusCheckSrv>::SharedPtr statusCheckService_;

        rclcpp::Publisher<deepracer_interfaces_pkg::msg::EvoSensorMsg>::SharedPtr sensorMsgPub_;

        std::shared_ptr<SensorFusionNode> node_handle_;
        image_transport::ImageTransport image_transport_;       
        image_transport::Publisher overlayImagePub_;

        // Max LiDAR distance required to replace the incorrect/erroneous LiDAR data point
        // that is read as 'inf' in the LaserScan message.
        float maxLiDARDist_;
        std::vector<float> lidarData_;
        std::vector<float> overlayLidarData_;
        LidarOverlay lidarOverlayProcessingObj_;
        /// Hash map that stores the min/max of each servo.
        std::unordered_map<std::string, std::unordered_map<std::string, float>> sensorConfiguration_;
        /// Flag to enable publishing the overlay image.
        std::atomic<bool> enableOverlay_;
        /// Flag to enable the gray fade overlay on camera images.
        std::atomic<bool> enableGrayOverlay_;
        /// Gray fade overlay image loaded from the package share directory (BGRA or BGR).
        cv::Mat grayOverlay_;
        /// Cached overlay resized to the current image dimensions.
        cv::Mat grayOverlayResized_;
        /// Cached premultiplied overlay (overlay_bgr * alpha), float32 BGR.
        cv::Mat overlayBGRPremul_;
        /// Cached inverse-alpha broadcast to 3 channels (1 - alpha), float32 BGR.
        cv::Mat oneMinusAlpha3_;
        std::chrono::steady_clock::time_point lastLidarMsgRecievedTime;
        std::chrono::steady_clock::time_point lastCameraMsgRecievedTime;
        size_t cameraImageCount_;
        unsigned int imageWidth_;
        unsigned int imageHeight_;
        std::mutex lidarMutex_;
        CameraMode mode_;

    };
}


/// Node entry point
int main(int argc, char * argv[])
{
    rclcpp::init(argc, argv);
    auto node = std::make_shared<SensorFusion::SensorFusionNode>("sensor_fusion_node");
    rclcpp::executors::MultiThreadedExecutor exec;
    exec.add_node(node);
    exec.spin();
    rclcpp::shutdown();
    return 0;
}
