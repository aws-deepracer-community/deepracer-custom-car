#include "diffdrive_motor_pkg/silent_led_handler.hpp"

namespace aws_deepracer_community_diffdrive_motor_pkg
{

SilentLEDHandler::SilentLEDHandler()
: logging_enabled_(true)
{
  // Initialize with LED off state
  current_state_.red = 0;
  current_state_.green = 0;
  current_state_.blue = 0;
}

SilentLEDHandler::~SilentLEDHandler()
{
  // No cleanup needed for silent handler
}

bool SilentLEDHandler::handleGetLedCtrlService(
  const std::shared_ptr<deepracer_interfaces_pkg::srv::GetLedCtrlSrv::Request> request,
  std::shared_ptr<deepracer_interfaces_pkg::srv::GetLedCtrlSrv::Response> response)
{
  (void)request;  // Request not used in silent implementation

  // Return current LED state (maintained in memory only)
  response->red = current_state_.red;
  response->green = current_state_.green;
  response->blue = current_state_.blue;
  // Note: GetLedCtrlSrv response has no error field, only SetLedCtrlSrv does

  return true;
}

bool SilentLEDHandler::handleSetLedCtrlService(
  const std::shared_ptr<deepracer_interfaces_pkg::srv::SetLedCtrlSrv::Request> request,
  std::shared_ptr<deepracer_interfaces_pkg::srv::SetLedCtrlSrv::Response> response)
{
  // Update internal state but don't actually control any LEDs
  setLEDState(request->red, request->green, request->blue);

  response->error = 0;  // Always successful
  return true;
}

deepracer_interfaces_pkg::srv::GetLedCtrlSrv::Response SilentLEDHandler::getLedState(
  const deepracer_interfaces_pkg::srv::GetLedCtrlSrv::Request & request)
{
  deepracer_interfaces_pkg::srv::GetLedCtrlSrv::Response response;
  handleGetLedCtrlService(
    std::make_shared<deepracer_interfaces_pkg::srv::GetLedCtrlSrv::Request>(request),
    std::make_shared<deepracer_interfaces_pkg::srv::GetLedCtrlSrv::Response>(response));
  return response;
}

deepracer_interfaces_pkg::srv::SetLedCtrlSrv::Response SilentLEDHandler::setLedState(
  const deepracer_interfaces_pkg::srv::SetLedCtrlSrv::Request & request)
{
  deepracer_interfaces_pkg::srv::SetLedCtrlSrv::Response response;
  handleSetLedCtrlService(
    std::make_shared<deepracer_interfaces_pkg::srv::SetLedCtrlSrv::Request>(request),
    std::make_shared<deepracer_interfaces_pkg::srv::SetLedCtrlSrv::Response>(response));
  return response;
}

void SilentLEDHandler::setLEDState(int red, int green, int blue)
{
  // Update internal state
  current_state_.red = red;
  current_state_.green = green;
  current_state_.blue = blue;

  // Log the command if logging is enabled
  if (logging_enabled_) {
    logLEDCommand(red, green, blue);
  }
}

const LEDState & SilentLEDHandler::getLEDState() const
{
  return current_state_;
}

void SilentLEDHandler::setLoggingEnabled(bool enabled)
{
  logging_enabled_ = enabled;
}

void SilentLEDHandler::logLEDCommand(int red, int green, int blue)
{
  // Simple logging - in a real implementation this might use ROS logging
  printf("LED Command (Silent): R=%d, G=%d, B=%d\n", red, green, blue);
}

}  // namespace aws_deepracer_community_diffdrive_motor_pkg
