cmake_minimum_required(VERSION 3.5)
project(sensor_fusion_pkg)

# Default to C99
if(NOT CMAKE_C_STANDARD)
  set(CMAKE_C_STANDARD 99)
endif()

# Default to C++14
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 14)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
  
  # Enhanced optimizations for sensor fusion
  add_compile_options(-flto=auto)      # Link-time optimization
  add_compile_options(-ffast-math)     # Faster math (important for sensor fusion)
  
  # Architecture-specific optimizations - detect at runtime
  include(CheckCXXSourceRuns)
  check_cxx_source_runs("
  #include <stdio.h>
  int main() {
    #if defined(__x86_64__) || defined(_M_X64)
      return 0;
    #else
      return 1;
    #endif
  }
  " IS_X86_64)
  
  if(IS_X86_64)
    add_compile_options(-march=goldmont -mtune=goldmont)
  endif()
  
  check_cxx_source_runs("
  #include <stdio.h>
  int main() {
    #if defined(__aarch64__)
      return 0;
    #else
      return 1;
    #endif
  }
  " IS_ARM64)
  
  if(IS_ARM64)
    add_compile_options(-march=armv8-a+crc -mtune=cortex-a72)
  endif()
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(rclcpp REQUIRED)
find_package(image_transport REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(deepracer_interfaces_pkg REQUIRED)
# Find the json parser/writer
find_package(jsoncpp REQUIRED)

add_executable(sensor_fusion_node
src/sensor_fusion_node.cpp
src/utility.cpp
src/lidar_overlay.cpp)

target_include_directories(sensor_fusion_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
  ${JSONCPP_INCLUDE_DIRS}
)
target_link_libraries(sensor_fusion_node jsoncpp)
ament_target_dependencies(
  sensor_fusion_node
  "cv_bridge"
  "rclcpp"
  "image_transport"
  "sensor_msgs"
  "deepracer_interfaces_pkg"
)

install(TARGETS sensor_fusion_node
  DESTINATION lib/${PROJECT_NAME})

# Install launch files.
install(DIRECTORY
  launch
  DESTINATION share/${PROJECT_NAME}/
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # the following line skips the linter which checks for copyrights
  # uncomment the line when a copyright and license is not present in all source files
  #set(ament_cmake_copyright_FOUND TRUE)
  # the following line skips cpplint (only works in a git repo)
  # uncomment the line when this package is not in a git repo
  #set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
