cmake_minimum_required(VERSION 3.5)
project(inference_pkg)
include(FetchContent)

set(ABSL_PROPAGATE_CXX_STD ON)
set(CMAKE_SUPPRESS_DEVELOPER_WARNINGS 1)

# Default to C99
if(NOT CMAKE_C_STANDARD)
  set(CMAKE_C_STANDARD 99)
endif()

# Default to C++17
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

# Find and use OpenMP for multi-core optimization
find_package(OpenMP)
if(OpenMP_CXX_FOUND)
  message(STATUS "OpenMP found. Enabling multi-core optimizations for CM4")
  add_compile_options(${OpenMP_CXX_FLAGS})
  link_libraries(${OpenMP_CXX_LIBRARIES})
endif()

# Check for Intel architecture
include(CheckCXXSourceRuns)
set(CMAKE_REQUIRED_FLAGS)
check_cxx_source_runs("
#include <stdio.h>
int main() {
  #if defined(__x86_64__) || defined(_M_X64) || defined(i386) || defined(_M_IX86)
    return 0;
  #else
    return 1;
  #endif
}
" IS_INTEL_ARCHITECTURE)

# Check for ARM architecture (Raspberry Pi)
check_cxx_source_runs("
#include <stdio.h>
int main() {
  #if defined(__arm__) || defined(__aarch64__)
    return 0;
  #else
    return 1;
  #endif
}
" IS_ARM_ARCHITECTURE)

if(IS_INTEL_ARCHITECTURE)
  message(STATUS "Intel architecture detected, enabling optimizations")
  # Enable Intel-specific optimizations for TensorFlow Lite
  set(TFLITE_ENABLE_XNNPACK ON CACHE BOOL "Enable XNNPACK acceleration")
  set(TFLITE_ENABLE_RUY ON CACHE BOOL "Enable RUY matrix multiplication library")
  set(TFLITE_ENABLE_X86_OPTIMIZATIONS ON CACHE BOOL "Enable x86 optimizations")

  # Add Intel-specific compiler flags
  if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    add_compile_options(-Wno-deprecated-declarations -Wno-ignored-attributes -Wno-deprecated)
    add_compile_options(-msse4.2 -maes -mssse3 -mpclmul -mpopcnt -march=goldmont)
  endif()
elseif(IS_ARM_ARCHITECTURE)
  message(STATUS "ARM architecture detected, optimizing for 64-bit Compute Module 4")
  
  # Check if 64-bit ARM
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
    message(STATUS "64-bit ARM architecture confirmed, applying CM4-specific optimizations")
    
    # Enable ARM-specific optimizations for TensorFlow Lite
    set(TFLITE_ENABLE_XNNPACK ON CACHE BOOL "Enable XNNPACK acceleration")
    set(TFLITE_ENABLE_RUY ON CACHE BOOL "Enable RUY matrix multiplication library")
    set(TFLITE_ENABLE_NEON ON CACHE BOOL "Enable NEON optimizations for ARM")
    set(TFLITE_ENABLE_MMAP ON CACHE BOOL "Enable mmap for faster file access")
    
    # Disable features not needed on RPi CM4
    set(TFLITE_ENABLE_GPU OFF CACHE BOOL "Disable GPU")
    set(TFLITE_ENABLE_NNAPI OFF CACHE BOOL "Disable Android NNAPI")
    
    # CM4 64-bit specific compiler flags
    if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
      add_compile_options(-Wno-deprecated-declarations -Wno-ignored-attributes -Wno-deprecated)
      add_compile_options(
        -march=armv8-a            # ARMv8 architecture (required for 64-bit)
        -mtune=cortex-a72         # Optimize for CM4's Cortex-A72 CPU
        -O3                       # Maximum optimization level
        -ftree-vectorize          # Enable auto-vectorization
        -ffast-math               # Faster floating-point math (may affect precision)
      )
      
    endif()
  else()
    message(WARNING "32-bit ARM detected. For best CM4 performance, use 64-bit OS/toolchain")
    # Add basic ARM optimizations even for 32-bit mode
    set(TFLITE_ENABLE_XNNPACK ON CACHE BOOL "Enable XNNPACK acceleration")
    set(TFLITE_ENABLE_NEON ON CACHE BOOL "Enable NEON optimizations for ARM")
    
    if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
      add_compile_options(-Wno-deprecated-declarations -Wno-ignored-attributes -Wno-deprecated)
    endif()
  endif()
else()
  message(STATUS "Non-Intel/ARM architecture detected")
  if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    add_compile_options(-Wno-deprecated-declarations -Wno-ignored-attributes -Wno-deprecated)
  endif()
endif()

FetchContent_Declare(tensorflow-lite
  GIT_REPOSITORY https://github.com/tensorflow/tensorflow.git
  GIT_TAG v2.17.1  # Specify the desired tag here
)
FetchContent_Populate(tensorflow-lite)

add_subdirectory(
  ${tensorflow-lite_SOURCE_DIR}/tensorflow/lite 
  ${tensorflow-lite_BINARY_DIR}
  EXCLUDE_FROM_ALL
)

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(deepracer_interfaces_pkg REQUIRED)
find_package(image_transport REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(OpenCV 4.2 QUIET
  COMPONENTS
    opencv_core
    opencv_imgproc
    opencv_imgcodecs
  CONFIG
)
if(NOT OpenCV_FOUND)
  find_package(OpenCV 3 REQUIRED
    COMPONENTS
      opencv_core
      opencv_imgproc
      opencv_imgcodecs
    CONFIG
  )
endif()

# Check if ROS_DISTRO is jazzy and define a macro
if("$ENV{ROS_DISTRO}" STREQUAL "jazzy")
  add_definitions(-DROS_DISTRO_JAZZY)

  add_executable(inference_node
    src/inference_node.cpp
    src/tflite_inference_eng.cpp
    src/image_process.cpp
  )

  target_include_directories(inference_node PRIVATE
    include
    ${OpenCV_INCLUDE_DIRS}
    ${CMAKE_CURRENT_BINARY_DIR}/flatbuffers/include
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  )

  target_link_libraries(inference_node  -lm -ldl
    ${OpenCV_LIBRARIES}
    tensorflow-lite
  )

  ament_target_dependencies(inference_node rclcpp deepracer_interfaces_pkg sensor_msgs std_msgs cv_bridge image_transport OpenCV)

else()

  find_package(ngraph REQUIRED)
  find_package(InferenceEngine REQUIRED)

  add_executable(inference_node
      src/inference_node.cpp
      src/tflite_inference_eng.cpp
      src/intel_inference_eng.cpp
      src/image_process.cpp
      )

  target_include_directories(inference_node PRIVATE
    include
    ${OpenCV_INCLUDE_DIRS}
    ${InferenceEngine_INCLUDE_DIRS}
    ${CMAKE_CURRENT_BINARY_DIR}/flatbuffers/include
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  )

  target_link_libraries(inference_node  -lm -ldl
    ${OpenCV_LIBRARIES}
    tensorflow-lite
    ${InferenceEngine_LIBRARIES}
    ${NGRAPH_LIBRARIES}
    )

  ament_target_dependencies(inference_node rclcpp deepracer_interfaces_pkg sensor_msgs std_msgs cv_bridge image_transport OpenCV InferenceEngine ngraph)

endif()

install(TARGETS
  inference_node
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
ament_export_dependencies(inference_pkg sensor_msgs std_msgs)
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
