#!/usr/bin/env python3
"""生成用于连续性能验证的三色合成视频，不替代真实相机测试。"""
import argparse
from pathlib import Path
import cv2
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/performance/synthetic_30hz.avi"))
    parser.add_argument("--frames", type=int, default=600)
    args = parser.parse_args()
    if args.frames <= 0:
        parser.error("frames 必须大于零")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(args.output), cv2.VideoWriter_fourcc(*"MJPG"), 30, (640, 480))
    if not writer.isOpened():
        raise RuntimeError("无法创建合成视频")
    rng = np.random.default_rng(23)
    try:
        for index in range(args.frames):
            image = np.zeros((480, 640, 3), np.uint8)
            if index % 60 < 50:
                shift = round(15 * np.sin(index / 20))
                for x, color in [(110, (0, 0, 255)), (320, (0, 255, 255)), (530, (255, 0, 0))]:
                    cv2.ellipse(image, (x, 240 + shift), (55, 30), 15, 0, 360, color, -1)
                cv2.ellipse(image, (535, 240 + shift), (25, 10), 15, 0, 360, (0, 0, 0), -1)
                for x, y in rng.integers([0, 0], [640, 480], size=(50, 2)):
                    image[y, x] = (0, 0, 255)
            writer.write(image)
    finally:
        writer.release()
    print("已生成 {}：640×480，30 FPS，{} 帧".format(args.output, args.frames))


if __name__ == "__main__":
    main()
