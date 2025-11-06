#################################################################################
#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.          #
#   Copyright AWS DeepRacer Community. All Rights Reserved.                     #
#                                                                               #
#   Licensed under the Apache License, Version 2.0 (the "License").             #
#   You may not use this file except in compliance with the License.            #
#   You may obtain a copy of the License at                                     #
#                                                                               #
#       http://www.apache.org/licenses/LICENSE-2.0                              #
#                                                                               #
#   Unless required by applicable law or agreed to in writing, software         #
#   distributed under the License is distributed on an "AS IS" BASIS,           #
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.    #
#   See the License for the specific language governing permissions and         #
#   limitations under the License.                                              #
#################################################################################

cmake_minimum_required(VERSION 3.8)
project(bag_log_pkg)

# Default to C++17
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

if("$ENV{ROS_DISTRO}" STREQUAL "jazzy")
  add_definitions(-DROS_DISTRO_JAZZY)
else()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclpy REQUIRED)
find_package(rosbag2_cpp REQUIRED)
find_package(rosbag2_storage REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)
find_package(deepracer_interfaces_pkg REQUIRED)

# Include directories
include_directories(
  include
)

# Create the bag_log_node_cpp executable
add_executable(bag_log_node_cpp
  src/bag_log_node.cpp
)

# Add include directories for C++ executable
target_include_directories(bag_log_node_cpp PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

# Specify libraries to link against
ament_target_dependencies(bag_log_node_cpp
  rclcpp
  rosbag2_cpp
  rosbag2_storage
  std_msgs
  std_srvs
  deepracer_interfaces_pkg
)

# Install the C++ executable
install(TARGETS bag_log_node_cpp
  DESTINATION lib/${PROJECT_NAME}
)

# Install C++ include directories
install(DIRECTORY include/
  DESTINATION include/
)

# Install Python modules
ament_python_install_package(${PROJECT_NAME})

# Install Python scripts/executables
install(PROGRAMS
  ${PROJECT_NAME}/bag_log_node.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME bag_log_node
)

# Install launch files
install(DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # the following line skips the linter which checks for copyrights
  # comment the line when a copyright and license is added to all source files
  set(ament_cmake_copyright_FOUND TRUE)
  # the following line skips cpplint (only works in a git repo)
  # comment the line when this package is in a git repo and when
  # a copyright and license is added to all source files
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
