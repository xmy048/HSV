"""颜色候选检测。颜色和外形过滤不能保证候选就是桶。"""
from dataclasses import asdict, dataclass
import logging
import math
from time import perf_counter
from typing import Dict, List, Tuple

import cv2
import numpy as np

from .config import COLORS

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Detection:
    color: str
    center_x: float
    center_y: float
    area_px: int
    bbox: Tuple[int, int, int, int]
    possibly_truncated: bool
    circularity: float
    solidity: float

    def to_dict(self):
        return asdict(self)


@dataclass
class DetectionResult:
    detections: List[Detection]
    raw_masks: Dict[str, np.ndarray]
    cleaned_masks: Dict[str, np.ndarray]
    contours: List[List[np.ndarray]]
    elapsed_ms: float


def _detect(image, config, diagnostics):
    start = perf_counter()
    if (not isinstance(image, np.ndarray) or image.dtype != np.uint8
            or image.ndim != 3 or image.shape[2] != 3
            or image.shape[0] == 0 or image.shape[1] == 0):
        raise ValueError("输入必须是非空 uint8 BGR 三通道图像")
    height, width = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    morph, filters = config["morphology"], config["filters"]
    shapes = {"ellipse": cv2.MORPH_ELLIPSE, "rect": cv2.MORPH_RECT, "cross": cv2.MORPH_CROSS}
    size = morph["kernel_size"]
    kernel = cv2.getStructuringElement(shapes[morph["kernel_shape"]], (size, size))
    result = DetectionResult([], {}, {}, [], 0.0)
    for color in COLORS:
        spec = config["colors"][color]
        mask = np.zeros((height, width), np.uint8)
        for lo, hi in spec["h_ranges"]:
            segment = cv2.inRange(hsv, (lo, spec["s_range"][0], spec["v_range"][0]),
                                 (hi, spec["s_range"][1], spec["v_range"][1]))
            cv2.bitwise_or(mask, segment, dst=mask)
        cleaned = mask.copy() if diagnostics else mask
        for operation, key in ((cv2.MORPH_OPEN, "open_iterations"),
                               (cv2.MORPH_CLOSE, "close_iterations")):
            if morph[key] > 0:
                cleaned = cv2.morphologyEx(cleaned, operation, kernel, iterations=morph[key])
        if diagnostics:
            result.raw_masks[color] = mask
            result.cleaned_masks[color] = cleaned
        count, labels, stats, _ = cv2.connectedComponentsWithStats(
            cleaned, connectivity=morph["connectivity"], ltype=cv2.CV_32S)
        for label in range(1, count):
            x, y, w, h, area = [int(v) for v in stats[label]]
            fraction = area / float(width * height)
            if not filters["min_area_fraction"] <= fraction <= filters["max_area_fraction"]:
                continue
            if not filters["min_aspect_ratio"] <= w / float(h) <= filters["max_aspect_ratio"]:
                continue
            truncated = x == 0 or y == 0 or x + w == width or y + h == height
            if truncated and filters["exclude_truncated"]:
                continue
            # 只取当前 label，保留孔洞；ROI 只是计算优化，输出加回原图偏移。
            region = np.ascontiguousarray((labels[y:y+h, x:x+w] == label).astype(np.uint8))
            moments = cv2.moments(region, binaryImage=True)
            if moments["m00"] <= 0:
                LOGGER.warning("%s 区域 M00 为零，跳过候选", color)
                continue
            contours, _ = cv2.findContours(region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            perimeter = sum(cv2.arcLength(c, True) for c in contours)
            outer_area = sum(cv2.contourArea(c) for c in contours)
            circularity = min(1.0, 4 * math.pi * outer_area / (perimeter * perimeter)) if perimeter else 0.0
            points = np.concatenate(contours) if contours else np.empty((0, 1, 2), np.int32)
            hull_area = cv2.contourArea(cv2.convexHull(points)) if len(points) >= 3 else 0.0
            # 像素面积和几何面积离散化不同，比例上限截为 1；圆环的孔洞仍计入差异。
            solidity = min(1.0, area / hull_area) if hull_area > 0 else 0.0
            if circularity < filters["min_circularity"] or solidity < filters["min_solidity"]:
                continue
            result.detections.append(Detection(
                color=color,
                center_x=float(x + moments["m10"] / moments["m00"]),
                center_y=float(y + moments["m01"] / moments["m00"]),
                area_px=area, bbox=(x, y, w, h), possibly_truncated=truncated,
                circularity=circularity, solidity=solidity))
            if diagnostics:
                offset = np.array([[[x, y]]], dtype=np.int32)
                result.contours.append([c + offset for c in contours])
    if not result.detections:
        LOGGER.debug("当前帧无有效候选区域")
    result.elapsed_ms = (perf_counter() - start) * 1000.0
    return result


def detect_buckets(bgr_image, config):
    """返回全部候选；config 应在入口处经 load_config/validate_config 校验。"""
    return _detect(bgr_image, config, False).detections


def detect_with_diagnostics(bgr_image, config, include_masks=True):
    """额外提供核心检测耗时；include_masks=False 时不保留诊断图。"""
    return _detect(bgr_image, config, include_masks)
