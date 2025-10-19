#ifndef DIFFDRIVE_MOTOR_PKG__CALIBRATION_MANAGER_HPP_
#define DIFFDRIVE_MOTOR_PKG__CALIBRATION_MANAGER_HPP_

#include <string>
#include <memory>

#include "deepracer_interfaces_pkg/srv/get_calibration_srv.hpp"
#include "deepracer_interfaces_pkg/srv/set_calibration_srv.hpp"
#include "diffdrive_motor_pkg/differential_drive_controller.hpp"

namespace aws_deepracer_community_diffdrive_motor_pkg
{

  /**
   * @brief Calibration management for backward compatibility
   *
   * Stores native differential drive calibration parameters while providing
   * API compatibility with existing DeepRacer calibration interfaces.
   * Translates between servo/motor API calls and differential drive parameters.
   */
class CalibrationManager
{
public:
    /**
     * @brief Constructor
     * @param calibration_file_path Path to calibration file (default: standard location)
     * @param default_config Default configuration to use for initialization
     */
  explicit CalibrationManager(
    const std::string & calibration_file_path = "",
    const DifferentialDriveConfig & default_config = DifferentialDriveConfig{});

    /**
     * @brief Destructor
     */
  ~CalibrationManager();

    /**
     * @brief Load calibration data from file
     * @return true if successful, false otherwise
     */
  bool loadCalibration();

    /**
     * @brief Save calibration data to file
     * @return true if successful, false otherwise
     */
  bool saveCalibration();

    /**
     * @brief Handle GetCalibrationSrv service request
     * @param request Service request
     * @param response Service response
     * @return true if successful, false otherwise
     */
  bool handleGetCalibrationService(
    const std::shared_ptr<deepracer_interfaces_pkg::srv::GetCalibrationSrv::Request> request,
    std::shared_ptr<deepracer_interfaces_pkg::srv::GetCalibrationSrv::Response> response);

    /**
     * @brief Handle SetCalibrationSrv service request
     * @param request Service request
     * @param response Service response
     * @return true if successful, false otherwise
     */
  bool handleSetCalibrationService(
    const std::shared_ptr<deepracer_interfaces_pkg::srv::SetCalibrationSrv::Request> request,
    std::shared_ptr<deepracer_interfaces_pkg::srv::SetCalibrationSrv::Response> response);

    /**
     * @brief Get current calibration data
     * @return Current calibration data
     */
  const DifferentialDriveConfig & getCalibrationData() const;

private:
    /**
     * @brief Initialize default calibration values from config
     * @param config Configuration to use for defaults
     */
  void initializeDefaults(const DifferentialDriveConfig & config);

    /**
     * @brief Parse JSON calibration file
     * @param file_path Path to calibration file
     * @return true if successful, false otherwise
     */
  bool parseCalibrationFile(const std::string & file_path);

    /**
     * @brief Write calibration data to JSON file
     * @param file_path Path to calibration file
     * @return true if successful, false otherwise
     */
  bool writeCalibrationFile(const std::string & file_path);

  std::string calibration_file_path_;
  DifferentialDriveConfig calibration_data_;
  bool calibration_loaded_;
  DifferentialDriveConfig default_config_;
};

} // namespace aws_deepracer_community_diffdrive_motor_pkg

#endif // DIFFDRIVE_MOTOR_PKG__CALIBRATION_MANAGER_HPP_
