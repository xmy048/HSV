#!/usr/bin/env python3
"""ROS1 adapter for the existing BGR color-region detector."""
import sys

import cv2
import rospy
from cv_bridge import CvBridge, CvBridgeError
from sensor_msgs.msg import Image

from bucket_hsv import detect_buckets, load_config
from bucket_hsv.msg import Detection, DetectionArray


class BucketDetectorNode:
    def __init__(self):
        config_path = rospy.get_param("~config")
        self.config = load_config(config_path)
        self.bridge = CvBridge()
        image_topic = rospy.get_param("~image_topic", "/camera/image_raw")
        detections_topic = rospy.get_param("~detections_topic", "/bucket_hsv/detections")
        self.publisher = rospy.Publisher(detections_topic, DetectionArray, queue_size=1)
        self.subscriber = rospy.Subscriber(
            image_topic, Image, self.on_image, queue_size=1, buff_size=2 ** 22)
        rospy.loginfo("bucket_hsv: %s -> %s; config=%s", image_topic, detections_topic, config_path)

    def on_image(self, image_msg):
        if image_msg.width != 640 or image_msg.height != 480 or image_msg.encoding != "rgb8":
            rospy.logwarn_throttle(
                5.0, "bucket_hsv: expected 640x480 rgb8 image, got %sx%s %s" % (
                    image_msg.width, image_msg.height, image_msg.encoding))
            return
        try:
            bgr_image = self.bridge.imgmsg_to_cv2(image_msg, desired_encoding="bgr8")
            detections = detect_buckets(bgr_image, self.config)
        except (CvBridgeError, cv2.error, ValueError) as exc:
            rospy.logerr_throttle(5.0, "bucket_hsv: image processing failed: %s" % exc)
            return

        output = DetectionArray()
        output.header = image_msg.header
        output.detections = [
            Detection(color=item.color, center_x=item.center_x, center_y=item.center_y)
            for item in detections
        ]
        self.publisher.publish(output)


def main():
    rospy.init_node("bucket_detector")
    try:
        BucketDetectorNode()
    except (KeyError, OSError, ValueError) as exc:
        rospy.logfatal("bucket_hsv: startup failed: %s", exc)
        return 1
    rospy.spin()
    return 0


if __name__ == "__main__":
    sys.exit(main())
