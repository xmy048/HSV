"""独立工具的图片读写和诊断输出，不依赖 ROS。"""
import json
from pathlib import Path

import cv2
import numpy as np

from .visualization import render_detections


def read_image(path):
    try:
        buffer = np.fromfile(str(path), dtype=np.uint8)
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR) if len(buffer) else None
    except (OSError, cv2.error) as exc:
        raise ValueError("图片读取失败 {}：{}".format(path, exc)) from exc
    if image is None:
        raise ValueError("图片读取失败：{}".format(path))
    return image


def write_image(path, image):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix, image)
    if not ok:
        raise OSError("图片编码失败：{}".format(path))
    encoded.tofile(str(path))


def save_debug(output, image, result, metadata=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for name, masks in (("raw", result.raw_masks), ("cleaned", result.cleaned_masks)):
        for color, mask in masks.items():
            write_image(output / (color + "_" + name + ".png"), mask)
    write_image(output / "annotated.jpg", render_detections(image, result))
    height, width = image.shape[:2]
    info = {"center_definition": "去噪后颜色区域质心，不自动等于桶口中心",
            "image_size": {"width": width, "height": height},
            "elapsed_ms": result.elapsed_ms,
            "detections": [d.to_dict() for d in result.detections]}
    if metadata:
        info["metadata"] = metadata
    (output / "detections.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
