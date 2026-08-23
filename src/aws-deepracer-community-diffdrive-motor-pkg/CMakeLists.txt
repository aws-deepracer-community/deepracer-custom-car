cmake_minimum_required(VERSION 3.8)
project(diffdrive_motor_pkg)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# In each C++ package that needs HW_PLATFORM
if(DEFINED ENV{HW_PLATFORM})
  set(HW_PLATFORM $ENV{HW_PLATFORM})
  message(STATUS "Using hardware platform from environment: ${HW_PLATFORM}")
endif()

# Process HW_PLATFORM variable
if(DEFINED HW_PLATFORM)
  message(STATUS "Building i2c package for hardware platform: ${HW_PLATFORM}")
  if(HW_PLATFORM STREQUAL "RPI")
    add_definitions(-DHW_PLATFORM_RPI)
  elseif(HW_PLATFORM STREQUAL "DR")
    add_definitions(-DHW_PLATFORM_DR)
  endif()
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(deepracer_interfaces_pkg REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(PkgConfig REQUIRED)
pkg_check_modules(JSONCPP jsoncpp)

# Include directories
include_directories(include)

# Create executable
add_executable(diffdrive_motor_node
  src/differential_drive_node.cpp
  src/differential_drive_controller.cpp
  src/motor_manager.cpp
  src/calibration_manager.cpp
  src/silent_led_handler.cpp
  src/pwm.cpp
)

# Specify dependencies
ament_target_dependencies(diffdrive_motor_node
  rclcpp
  deepracer_interfaces_pkg
  std_msgs
  geometry_msgs
  sensor_msgs
)

# Link jsoncpp
target_link_libraries(diffdrive_motor_node ${JSONCPP_LIBRARIES})
target_include_directories(diffdrive_motor_node PRIVATE ${JSONCPP_INCLUDE_DIRS})

# Install targets
install(TARGETS
  diffdrive_motor_node
  DESTINATION lib/${PROJECT_NAME}
)

# Install launch files
install(DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_cmake_gtest REQUIRED)

  # the following line skips the linter which checks for copyrights
  # comment the line when a copyright and license is added to all source files
  set(ament_cmake_copyright_FOUND TRUE)
  # the following line skips cpplint (only works in a git repo)
  # comment the line when this package is in a git repo and when
  # a copyright and license is added to all source files
  set(ament_cmake_cpplint_FOUND TRUE)

  ament_lint_auto_find_test_dependencies()

  # Add unit tests
  ament_add_gtest(test_differential_drive_controller
    test/test_differential_drive_controller.cpp
    src/differential_drive_controller.cpp
  )
  ament_target_dependencies(test_differential_drive_controller
    rclcpp
    deepracer_interfaces_pkg
  )

  ament_add_gtest(test_motor_manager
    test/test_motor_manager.cpp
    src/motor_manager.cpp
    src/pwm.cpp
  )
  ament_target_dependencies(test_motor_manager
    rclcpp
  )

  # Basic PWM integration test
  ament_add_gtest(test_motor_pwm_basic
    test/test_motor_pwm_basic.cpp
    src/motor_manager.cpp
    src/pwm.cpp
  )
  ament_target_dependencies(test_motor_pwm_basic
    rclcpp
  )

  ament_add_gtest(test_calibration_manager
    test/test_calibration_manager.cpp
    src/calibration_manager.cpp
  )
  ament_target_dependencies(test_calibration_manager
    rclcpp
    deepracer_interfaces_pkg
  )
  target_link_libraries(test_calibration_manager ${JSONCPP_LIBRARIES})
  target_include_directories(test_calibration_manager PRIVATE ${JSONCPP_INCLUDE_DIRS})

endif()

ament_package()