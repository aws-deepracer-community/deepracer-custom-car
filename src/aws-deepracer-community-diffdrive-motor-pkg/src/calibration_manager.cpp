#include "diffdrive_motor_pkg/calibration_manager.hpp"
#include <jsoncpp/json/json.h>
#include <fstream>
#include <iostream>
#include <algorithm>

namespace aws_deepracer_community_diffdrive_motor_pkg
{
  // JSON keys for calibration file
const std::string HEADER_KEY = "Calibration";
const std::string DIFFDRIVE_KEY = "DifferentialDrive";
const std::string MAX_FORWARD_SPEED_KEY = "max_forward_speed";
const std::string MAX_BACKWARD_SPEED_KEY = "max_backward_speed";
const std::string MAX_LEFT_DIFFERENTIAL_KEY = "max_left_differential";
const std::string MAX_RIGHT_DIFFERENTIAL_KEY = "max_right_differential";
const std::string CENTER_OFFSET_KEY = "center_offset";
const std::string MOTOR_POLARITY_KEY = "motor_polarity";
const std::string VERSION_KEY = "version";
const std::string CAL_FILE_VERSION = "1.0";

  // Helper function to check if file exists
bool checkFile(const std::string & filePath)
{
  std::ifstream file(filePath);
  return file.good();
}

  // Helper function to write JSON to file
void writeJSONToFile(const Json::Value & jsonValue, const std::string & filePath)
{
  std::ofstream file(filePath);
  if (file.is_open()) {
    Json::StreamWriterBuilder builder;
    builder["indentation"] = "  ";
    std::unique_ptr<Json::StreamWriter> writer(builder.newStreamWriter());
    writer->write(jsonValue, &file);
  }
}

CalibrationManager::CalibrationManager(
  const std::string & calibration_file_path,
  const DifferentialDriveConfig & default_config)
: calibration_file_path_(calibration_file_path), calibration_loaded_(false), default_config_(default_config)
{
  if (calibration_file_path_.empty()) {
    calibration_file_path_ = "/opt/aws/deepracer/calibration.json";
  }
  initializeDefaults(default_config_);
  loadCalibration();   // Try to load existing calibration
}

CalibrationManager::~CalibrationManager()
{
    // Save calibration on shutdown if modified
  if (calibration_loaded_) {
    saveCalibration();
  }
}

bool CalibrationManager::loadCalibration()
{
  if (checkFile(calibration_file_path_)) {
    return parseCalibrationFile(calibration_file_path_);
  } else {
      // File doesn't exist, create it with defaults
    initializeDefaults(default_config_);
    saveCalibration();
    calibration_loaded_ = true;
    return true;
  }
}

bool CalibrationManager::saveCalibration()
{
  return writeCalibrationFile(calibration_file_path_);
}

bool CalibrationManager::handleGetCalibrationService(
  const std::shared_ptr<deepracer_interfaces_pkg::srv::GetCalibrationSrv::Request> request,
  std::shared_ptr<deepracer_interfaces_pkg::srv::GetCalibrationSrv::Response> response)
{
    // Support cal_type field: 0 = servo (steering), 1 = motor (throttle)
  response->error = 0;

  if (request->cal_type == 0) {
      // Servo (steering) calibration - encode steering-related parameters
      // Map center_offset and steering differential to integer fields
    response->min = static_cast<int>(calibration_data_.max_left_differential * -100.0f);
    response->mid = static_cast<int>(calibration_data_.center_offset * 100.0f);   // Map [-1,1] to [0,100]
    response->max = static_cast<int>(calibration_data_.max_right_differential * 100.0f);
    response->polarity = 1;   // Standard servo polarity (steering doesn't use motor polarity)
  } else if (request->cal_type == 1) {
      // Motor (throttle) calibration - encode speed parameters
    response->min = static_cast<int>(calibration_data_.max_backward_speed * -100.0f);
    response->mid = 0;   // Standard mid value for motor
    response->max = static_cast<int>(calibration_data_.max_forward_speed * 100.0f);
    response->polarity = calibration_data_.motor_polarity;   // Use configured motor polarity
  } else {
      // Invalid calibration type
    response->error = 1;
    return false;
  }

  return true;
}

bool CalibrationManager::handleSetCalibrationService(
  const std::shared_ptr<deepracer_interfaces_pkg::srv::SetCalibrationSrv::Request> request,
  std::shared_ptr<deepracer_interfaces_pkg::srv::SetCalibrationSrv::Response> response)
{
    // Validate input ranges for the new ±100 scaling system
    // Allow reasonable range for ±100 scaling: roughly -200 to +200 to accommodate edge cases
  if (request->min < -200 || request->max > 200 || request->mid < -200 || request->mid > 200) {
    response->error = 1;   // Invalid range
    return false;
  }

    // Handle different calibration types: 0 = servo (steering), 1 = motor (throttle)
  if (request->cal_type == 0) {
      // Servo (steering) calibration - decode steering parameters (inverse of Get service)
      // Decode center offset from mid value: inverse of (center_offset * 100.0f)
    calibration_data_.center_offset = static_cast<float>(request->mid) / 100.0f;

      // Decode differential values from min/max: inverse of (max_left_differential * -100.0f) and (max_right_differential * 100.0f)
    calibration_data_.max_left_differential = static_cast<float>(request->min) / -100.0f;
    calibration_data_.max_right_differential = static_cast<float>(request->max) / 100.0f;

      // Clamp steering values
    calibration_data_.center_offset = std::clamp(calibration_data_.center_offset, -1.0f, 1.0f);
    calibration_data_.max_left_differential = std::clamp(calibration_data_.max_left_differential,
        0.0f, 1.0f);
    calibration_data_.max_right_differential = std::clamp(calibration_data_.max_right_differential,
        0.0f, 1.0f);
  } else if (request->cal_type == 1) {
      // Motor (throttle) calibration - decode speed parameters (inverse of Get service)
      // Inverse of (max_backward_speed * -100.0f) and (max_forward_speed * 100.0f)
    calibration_data_.max_backward_speed = static_cast<float>(request->min) / -100.0f;
    calibration_data_.max_forward_speed = static_cast<float>(request->max) / 100.0f;

      // Set motor polarity from request (validate to be -1 or 1)
    if (request->polarity == -1 || request->polarity == 1) {
      calibration_data_.motor_polarity = request->polarity;
    } else {
      calibration_data_.motor_polarity = 1;   // Default to normal polarity
    }

      // Clamp speed values
    calibration_data_.max_forward_speed = std::clamp(calibration_data_.max_forward_speed, 0.0f,
        1.0f);
    calibration_data_.max_backward_speed = std::clamp(calibration_data_.max_backward_speed, 0.0f,
        1.0f);
  } else {
      // Invalid calibration type
    response->error = 1;
    return false;
  }

    // Save the updated calibration
  if (saveCalibration()) {
    response->error = 0;
    return true;
  }

  response->error = 1;
  return false;
}

const DifferentialDriveConfig & CalibrationManager::getCalibrationData() const
{
  return calibration_data_;
}

void CalibrationManager::initializeDefaults(const DifferentialDriveConfig & config)
{
    // Initialize with values from the provided configuration
  calibration_data_.max_forward_speed = config.max_forward_speed;
  calibration_data_.max_backward_speed = config.max_backward_speed;
  calibration_data_.max_left_differential = config.max_left_differential;
  calibration_data_.max_right_differential = config.max_right_differential;
  calibration_data_.center_offset = config.center_offset;
  calibration_data_.motor_polarity = config.motor_polarity;

    // Motor PWM calibration will be calculated from differential drive parameters
    // when needed for API compatibility
}

bool CalibrationManager::parseCalibrationFile(const std::string & file_path)
{
  Json::Value calJsonValue;
  Json::Reader reader;
  std::ifstream ifs(file_path);

  if (!reader.parse(ifs, calJsonValue)) {
    std::cerr << "Error parsing calibration.json" << std::endl;
    return false;
  }

  if (!calJsonValue.isMember(HEADER_KEY)) {
    std::cerr << "Calibration file error: No calibration header" << std::endl;
    return false;
  }

  if (!calJsonValue[HEADER_KEY].isMember(DIFFDRIVE_KEY)) {
    std::cerr << "Calibration file error: Missing differential drive section" << std::endl;
    return false;
  }

  const Json::Value & diffDriveSection = calJsonValue[HEADER_KEY][DIFFDRIVE_KEY];

    // Parse each differential drive parameter
  if (diffDriveSection.isMember(MAX_FORWARD_SPEED_KEY)) {
    calibration_data_.max_forward_speed = diffDriveSection[MAX_FORWARD_SPEED_KEY].asFloat();
  }
  if (diffDriveSection.isMember(MAX_BACKWARD_SPEED_KEY)) {
    calibration_data_.max_backward_speed = diffDriveSection[MAX_BACKWARD_SPEED_KEY].asFloat();
  }
  if (diffDriveSection.isMember(MAX_LEFT_DIFFERENTIAL_KEY)) {
    calibration_data_.max_left_differential = diffDriveSection[MAX_LEFT_DIFFERENTIAL_KEY].asFloat();
  }
  if (diffDriveSection.isMember(MAX_RIGHT_DIFFERENTIAL_KEY)) {
    calibration_data_.max_right_differential =
      diffDriveSection[MAX_RIGHT_DIFFERENTIAL_KEY].asFloat();
  }
  if (diffDriveSection.isMember(CENTER_OFFSET_KEY)) {
    calibration_data_.center_offset = diffDriveSection[CENTER_OFFSET_KEY].asFloat();
  }
  if (diffDriveSection.isMember(MOTOR_POLARITY_KEY)) {
    calibration_data_.motor_polarity = diffDriveSection[MOTOR_POLARITY_KEY].asInt();
  }

  calibration_loaded_ = true;
  return true;
}

bool CalibrationManager::writeCalibrationFile(const std::string & file_path)
{
  Json::Value calJsonValue;

    // Create the JSON structure
  calJsonValue[HEADER_KEY][DIFFDRIVE_KEY][MAX_FORWARD_SPEED_KEY] =
    calibration_data_.max_forward_speed;
  calJsonValue[HEADER_KEY][DIFFDRIVE_KEY][MAX_BACKWARD_SPEED_KEY] =
    calibration_data_.max_backward_speed;
  calJsonValue[HEADER_KEY][DIFFDRIVE_KEY][MAX_LEFT_DIFFERENTIAL_KEY] =
    calibration_data_.max_left_differential;
  calJsonValue[HEADER_KEY][DIFFDRIVE_KEY][MAX_RIGHT_DIFFERENTIAL_KEY] =
    calibration_data_.max_right_differential;
  calJsonValue[HEADER_KEY][DIFFDRIVE_KEY][CENTER_OFFSET_KEY] = calibration_data_.center_offset;
  calJsonValue[HEADER_KEY][DIFFDRIVE_KEY][MOTOR_POLARITY_KEY] = calibration_data_.motor_polarity;
  calJsonValue[HEADER_KEY][VERSION_KEY] = CAL_FILE_VERSION;

  writeJSONToFile(calJsonValue, file_path);
  return true;
}

} // namespace aws_deepracer_community_diffdrive_motor_pkg
