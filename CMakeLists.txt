cmake_minimum_required(VERSION 3.0.2)
project(bucket_hsv)

find_package(catkin REQUIRED COMPONENTS
  cv_bridge
  message_generation
  rospy
  sensor_msgs
  std_msgs
)

catkin_python_setup()

add_message_files(FILES
  Detection.msg
  DetectionArray.msg
)

generate_messages(DEPENDENCIES std_msgs)

catkin_package(CATKIN_DEPENDS
  cv_bridge
  message_runtime
  rospy
  sensor_msgs
  std_msgs
)

catkin_install_python(PROGRAMS scripts/bucket_detector_node.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

install(DIRECTORY config launch
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)
