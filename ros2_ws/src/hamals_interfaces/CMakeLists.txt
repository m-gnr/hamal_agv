cmake_minimum_required(VERSION 3.8)
project(hamals_interfaces)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  # msg
  "msg/ForkCommand.msg"
  "msg/ForkState.msg"
  "msg/ObstacleRegionState.msg"
  "msg/ObstacleState.msg"
  "msg/WheelTicks.msg"
  "msg/MissionTask.msg"
  "msg/MissionState.msg"
  "msg/QrDetection.msg"
  "msg/PlcState.msg"
  "msg/SafetyState.msg"
  "msg/WorldModelState.msg"
  "msg/Station.msg"
  "msg/DoorEvent.msg"
  "msg/Door.msg"

  "srv/PauseMission.srv"
  "srv/ResumeMission.srv"
  "srv/GetStation.srv"
  "srv/PlanSemanticRoute.srv"
  "srv/GetDoor.srv"

  "action/ExecuteMission.action"
  "action/Dock.action"
  DEPENDENCIES builtin_interfaces std_msgs geometry_msgs
)

ament_export_dependencies(rosidl_default_runtime)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
