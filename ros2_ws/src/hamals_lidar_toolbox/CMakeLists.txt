cmake_minimum_required(VERSION 3.8)
project(hamals_lidar_toolbox)

# =========================
# Compiler options
# =========================
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# =========================
# Find dependencies
# =========================
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(visualization_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(hamals_lidar_msgs REQUIRED)

# =========================
# Core library (ROS-independent)
# =========================
add_library(hamals_lidar_toolbox_core
  src/core/ScanData.cpp
  src/core/ScanSanitizer.cpp
  src/core/ScanSegmenter.cpp
  src/core/ScanMetrics.cpp
  src/core/ObstacleDetector.cpp
)

target_include_directories(hamals_lidar_toolbox_core
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

# =========================
# ROS library (adapters + rviz)
# =========================
add_library(hamals_lidar_toolbox_ros
  src/ros/adapters/LaserScanAdapter.cpp
  src/ros/rviz/RvizDebugPublisher.cpp
)

target_include_directories(hamals_lidar_toolbox_ros
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

ament_target_dependencies(hamals_lidar_toolbox_ros
  rclcpp
  sensor_msgs
  visualization_msgs
  geometry_msgs
)

target_link_libraries(hamals_lidar_toolbox_ros
  hamals_lidar_toolbox_core
)

# =========================
# Scan processor node
# =========================
add_executable(scan_processor_node
  src/ros/nodes/scan_processor_node.cpp
)

target_include_directories(scan_processor_node
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

ament_target_dependencies(scan_processor_node
  rclcpp
  sensor_msgs
  hamals_lidar_msgs
)

target_link_libraries(scan_processor_node
  hamals_lidar_toolbox_ros
  hamals_lidar_toolbox_core
)

# =========================
# Install
# =========================
install(
  TARGETS
    hamals_lidar_toolbox_core
    hamals_lidar_toolbox_ros
    scan_processor_node
  EXPORT export_${PROJECT_NAME}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION lib/${PROJECT_NAME}
)

install(
  DIRECTORY include/
  DESTINATION include/
)

install(
  DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

install(
  DIRECTORY config/
  DESTINATION share/${PROJECT_NAME}/config
)

# =========================
# Export targets
# =========================
ament_export_targets(export_${PROJECT_NAME} HAS_LIBRARY_TARGET)
ament_export_include_directories(include)
ament_export_dependencies(
  rclcpp
  sensor_msgs
  visualization_msgs
  geometry_msgs
  hamals_lidar_msgs
)

# =========================
# Testing
# =========================
if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
