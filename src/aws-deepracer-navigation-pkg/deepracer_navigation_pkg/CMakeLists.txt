cmake_minimum_required(VERSION 3.8)
project(deepracer_navigation_pkg)

# Default to C++17
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
  add_compile_options(-Wno-deprecated-declarations)
  # Enhanced optimizations 
  add_compile_options(-O3)             # Maximum optimization
  add_compile_options(-flto=auto)      # Link-time optimization
  add_compile_options(-ffast-math)     # Faster math
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclpy REQUIRED)
find_package(deepracer_interfaces_pkg REQUIRED)
find_package(PkgConfig REQUIRED)
find_package(jsoncpp REQUIRED)

# Create the deepracer_navigation_node_cpp - renamed executable
add_executable(deepracer_navigation_node_cpp
  src/deepracer_navigation_node.cpp
  src/main.cpp
)

# Add include directories
target_include_directories(deepracer_navigation_node_cpp PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

# Specify libraries to link against
ament_target_dependencies(deepracer_navigation_node_cpp
  rclcpp
  deepracer_interfaces_pkg
)

target_link_libraries(deepracer_navigation_node_cpp
  jsoncpp
)

# Install the C++ executable
install(TARGETS deepracer_navigation_node_cpp
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
  ${PROJECT_NAME}/deepracer_navigation_node.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME deepracer_navigation_node
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