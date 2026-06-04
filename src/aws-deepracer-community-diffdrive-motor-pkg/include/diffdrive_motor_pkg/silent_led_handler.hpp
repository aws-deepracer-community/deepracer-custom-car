#ifndef DIFFDRIVE_MOTOR_PKG__SILENT_LED_HANDLER_HPP_
#define DIFFDRIVE_MOTOR_PKG__SILENT_LED_HANDLER_HPP_

#include <memory>

#include "deepracer_interfaces_pkg/srv/get_led_ctrl_srv.hpp"
#include "deepracer_interfaces_pkg/srv/set_led_ctrl_srv.hpp"

namespace aws_deepracer_community_diffdrive_motor_pkg
{

/**
 * @brief LED state information
 */
struct LEDState
{
  int red = 0;      // Red LED value (0-255)
  int green = 0;    // Green LED value (0-255)
  int blue = 0;     // Blue LED value (0-255)
};

/**
 * @brief Silent LED handler for compatibility
 *
 * Provides LED control service interfaces that maintain compatibility
 * with existing DeepRacer applications but silently ignore LED commands
 * since the Waveshare Motor Driver HAT does not have RGB LEDs.
 */
class SilentLEDHandler
{
public:
  /**
   * @brief Constructor
   */
  SilentLEDHandler();

  /**
   * @brief Destructor
   */
  ~SilentLEDHandler();

  /**
   * @brief Handle GetLedCtrlSrv service request
   * @param request Service request
   * @param response Service response
   * @return true if successful, false otherwise
   */
  bool handleGetLedCtrlService(
    const std::shared_ptr<deepracer_interfaces_pkg::srv::GetLedCtrlSrv::Request> request,
    std::shared_ptr<deepracer_interfaces_pkg::srv::GetLedCtrlSrv::Response> response);

  /**
   * @brief Handle SetLedCtrlSrv service request
   * @param request Service request
   * @param response Service response
   * @return true if successful, false otherwise
   */
  bool handleSetLedCtrlService(
    const std::shared_ptr<deepracer_interfaces_pkg::srv::SetLedCtrlSrv::Request> request,
    std::shared_ptr<deepracer_interfaces_pkg::srv::SetLedCtrlSrv::Response> response);

  /**
   * @brief Process GetLedState service request (convenience method)
   * @param request Service request
   * @return Service response
   */
  deepracer_interfaces_pkg::srv::GetLedCtrlSrv::Response getLedState(
    const deepracer_interfaces_pkg::srv::GetLedCtrlSrv::Request & request);

  /**
   * @brief Process SetLedState service request (convenience method)
   * @param request Service request
   * @return Service response
   */
  deepracer_interfaces_pkg::srv::SetLedCtrlSrv::Response setLedState(
    const deepracer_interfaces_pkg::srv::SetLedCtrlSrv::Request & request);

  /**
   * @brief Set LED state (silently ignored but logged)
   * @param red Red LED value (0-255)
   * @param green Green LED value (0-255)
   * @param blue Blue LED value (0-255)
   */
  void setLEDState(int red, int green, int blue);

  /**
   * @brief Get current LED state
   * @return Current LED state
   */
  const LEDState & getLEDState() const;

  /**
   * @brief Enable or disable LED command logging
   * @param enabled Logging enable state
   */
  void setLoggingEnabled(bool enabled);

private:
  /**
   * @brief Log LED command for debugging
   * @param red Red LED value
   * @param green Green LED value
   * @param blue Blue LED value
   */
  void logLEDCommand(int red, int green, int blue);

  LEDState current_state_;
  bool logging_enabled_;
};

}  // namespace aws_deepracer_community_diffdrive_motor_pkg

#endif  // DIFFDRIVE_MOTOR_PKG__SILENT_LED_HANDLER_HPP_
