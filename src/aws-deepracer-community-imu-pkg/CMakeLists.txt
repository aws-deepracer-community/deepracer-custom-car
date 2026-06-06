cmake_minimum_required(VERSION 3.8)
project(imu_pkg)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

set(CMAKE_CXX_STANDARD 17)

# Hardware platform detection (set via environment: HW_PLATFORM=DR or HW_PLATFORM=RPI)
if(DEFINED ENV{HW_PLATFORM})
  set(HW_PLATFORM $ENV{HW_PLATFORM})
  message(STATUS "IMU package: using hardware platform from environment: ${HW_PLATFORM}")
endif()

if(DEFINED HW_PLATFORM)
  if(HW_PLATFORM STREQUAL "DR")
    add_definitions(-DHW_PLATFORM_DR)
    message(STATUS "IMU package: building for DeepRacer (I2C bus 7)")
  elseif(HW_PLATFORM STREQUAL "RPI")
    add_definitions(-DHW_PLATFORM_RPI)
    message(STATUS "IMU package: building for Raspberry Pi (I2C bus 1)")
  endif()
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(deepracer_interfaces_pkg REQUIRED)

# Include directories
include_directories(include)

# Executable
add_executable(imu_node
  src/bmi160.cpp
  src/imu_node.cpp
)

ament_target_dependencies(imu_node
  rclcpp
  sensor_msgs
  std_msgs
  deepracer_interfaces_pkg
)

# Install
install(TARGETS
  imu_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY include/
  DESTINATION include
)

install(DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_cmake_gtest REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()

  ament_add_gtest(test_conversions
    test/test_conversions.cpp
  )
  target_include_directories(test_conversions PRIVATE include)
  ament_target_dependencies(test_conversions rclcpp)
endif()

ament_package()
