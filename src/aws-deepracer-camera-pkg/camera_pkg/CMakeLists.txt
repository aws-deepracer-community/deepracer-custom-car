cmake_minimum_required(VERSION 3.5)
project(camera_pkg)

# Default to C99
if(NOT CMAKE_C_STANDARD)
  set(CMAKE_C_STANDARD 99)
endif()

# Default to C++17
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
  add_compile_options(-flto=auto)           # Link-time optimization
  add_compile_options(-ffast-math)     # Faster math (important for sensor fusion)  
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(deepracer_interfaces_pkg REQUIRED)
find_package(image_transport REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(OpenCV REQUIRED)


add_executable(camera_node
    src/camera_node.cpp
)

target_include_directories(camera_node PRIVATE
#    include
    ${OpenCV_INCLUDE_DIRS}
)

target_link_libraries(camera_node ${OpenCV_LIBRARIES})

ament_target_dependencies(camera_node rclcpp deepracer_interfaces_pkg sensor_msgs std_msgs cv_bridge image_transport OpenCV) 

install(TARGETS
  camera_node
  DESTINATION
  lib/${PROJECT_NAME}
)

#install(DIRECTORY include/
#  DESTINATION include)

# Install launch files.
install(DIRECTORY
  launch
  DESTINATION share/${PROJECT_NAME}/
)

ament_export_include_directories(include)
ament_export_dependencies(deepracer_interfaces_pkg sensor_msgs std_msgs)
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
