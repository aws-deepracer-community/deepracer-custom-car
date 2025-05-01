cmake_minimum_required(VERSION 3.5)
project(servo_pkg)

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
  add_compile_options(-Wno-deprecated-declarations)
  # Enhanced optimizations for sensor fusion
  add_compile_options(-O3)             # Maximum optimization
  add_compile_options(-flto=auto)           # Link-time optimization
  add_compile_options(-ffast-math)     # Faster math (important for sensor fusion)
endif()

# In each C++ package that needs HW_PLATFORM
if(DEFINED ENV{HW_PLATFORM})
  set(HW_PLATFORM $ENV{HW_PLATFORM})
  message(STATUS "Using hardware platform from environment: ${HW_PLATFORM}")
  add_definitions(-DHW_PLATFORM_${HW_PLATFORM})
endif()

# Process HW_PLATFORM variable
if(DEFINED HW_PLATFORM)
  message(STATUS "Building servo package for hardware platform: ${HW_PLATFORM}")
  if(HW_PLATFORM STREQUAL "RPI4")
    add_definitions(-DHW_PLATFORM_RPI4)
  elseif(HW_PLATFORM STREQUAL "RPI5")
    add_definitions(-DHW_PLATFORM_RPI5)
  elseif(HW_PLATFORM STREQUAL "DR")
    add_definitions(-DHW_PLATFORM_DR)
  endif()
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(deepracer_interfaces_pkg REQUIRED)
# Find the json parser/writer
find_package(jsoncpp REQUIRED)

add_executable(servo_node
    src/servo_node.cpp
    src/bios_version.cpp
    src/utility.cpp
    src/led_mgr.cpp
    src/servo_mgr.cpp
    src/pwm.cpp
)

target_include_directories(servo_node PRIVATE
    include
    ${JSONCPP_INCLUDE_DIRS}
)

target_link_libraries(servo_node jsoncpp)

ament_target_dependencies(servo_node rclcpp deepracer_interfaces_pkg) 

install(TARGETS
  servo_node
  DESTINATION
  lib/${PROJECT_NAME}
)

install(DIRECTORY include/
  DESTINATION include)

# Install launch files.
install(DIRECTORY
  launch
  DESTINATION share/${PROJECT_NAME}/
)

ament_export_include_directories(include)
ament_export_dependencies(deepracer_interfaces_pkg)
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
