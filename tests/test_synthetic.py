"""合成场景与独立像素均值交叉验证。可直接运行保存测试产物。"""
import copy
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bucket_hsv.config import load_config
from bucket_hsv.detector import detect_buckets, detect_with_diagnostics

ROOT = Path(__file__).resolve().parents[1]


def config():
    return load_config(ROOT / "config/default.yaml")


def scenes():
    """预期数量手工定义，避免由检测器自身生成期望值。"""
    colors = [(0, 0, 255), (0, 255, 255), (255, 0, 0)]
    out = {}
    frame = np.zeros((480, 640, 3), np.uint8)
    for x, color in zip([100, 300, 500], colors):
        cv2.circle(frame, (x, 230), 45, color, -1)
    out["three_colors"] = (frame, {"red": 1, "yellow": 1, "blue": 1})
    frame = np.zeros_like(frame)
    for x in [100, 300, 500]:
        cv2.circle(frame, (x, 220), 35, colors[0], -1)
    out["same_color"] = (frame, {"red": 3})
    hsv = np.zeros_like(frame)
    cv2.circle(hsv, (170, 230), 45, (2, 255, 255), -1)
    cv2.circle(hsv, (450, 230), 45, (175, 255, 255), -1)
    out["red_wrap"] = (cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR), {"red": 2})
    out["empty"] = (np.zeros_like(frame), {})
    frame = out["three_colors"][0].copy()
    rng = np.random.default_rng(23)
    for x, y in rng.integers([0, 0], [640, 480], size=(300, 2)):
        frame[y, x] = colors[0]
    out["noise"] = (frame, {"red": 1, "yellow": 1, "blue": 1})
    frame = np.zeros_like(frame)
    cv2.circle(frame, (320, 240), 65, colors[2], -1)
    cv2.circle(frame, (338, 233), 30, (0, 0, 0), -1)
    out["asymmetric_ring"] = (frame, {"blue": 1})
    frame = np.zeros_like(frame)
    cv2.circle(frame, (0, 240), 60, colors[0], -1)
    out["truncated"] = (frame, {"red": 1})
    frame = np.zeros_like(frame)
    cv2.ellipse(frame, (220, 240), (90, 25), 30, 0, 360, colors[1], -1)
    cv2.ellipse(frame, (475, 240), (75, 30), -20, 0, 360, colors[2], -1)
    cv2.ellipse(frame, (481, 237), (48, 12), -20, 0, 360, (0, 0, 0), -1)
    out["oblique_ellipses"] = (frame, {"yellow": 1, "blue": 1})
    frame = np.zeros_like(frame)
    cv2.rectangle(frame, (240, 230), (400, 320), colors[0], -1)
    cv2.ellipse(frame, (320, 230), (80, 25), 0, 0, 360, colors[0], -1)
    cv2.rectangle(frame, (325, 250), (370, 280), (0, 0, 0), -1)
    out["wall_and_glare"] = (frame, {"red": 1})
    frame = np.zeros_like(frame)
    cv2.circle(frame, (320, 240), 60, colors[2], -1)
    cv2.rectangle(frame, (312, 175), (328, 305), (0, 0, 0), -1)
    out["occlusion_split"] = (frame, {"blue": 2})
    return out


@pytest.mark.parametrize("name", list(scenes()))
def test_scene_counts_and_centroids(name):
    """防止漏色、多目标丢失、填孔和 ROI 偏移错误。"""
    frame, expected = scenes()[name]
    result = detect_with_diagnostics(frame, config())
    actual = {}
    for detection in result.detections:
        actual[detection.color] = actual.get(detection.color, 0) + 1
        x, y, w, h = detection.bbox
        mask = result.cleaned_masks[detection.color]
        _, labels = cv2.connectedComponents(mask, connectivity=8)
        region = labels[y:y+h, x:x+w]
        values = region[region > 0]
        label = np.bincount(values).argmax()
        ys, xs = np.nonzero(labels == label)
        assert detection.center_x == pytest.approx(float(xs.mean()), abs=1e-6)
        assert detection.center_y == pytest.approx(float(ys.mean()), abs=1e-6)
        assert detection.area_px == len(xs)
        assert isinstance(detection.center_x, float)
    assert actual == expected
    assert result.elapsed_ms >= 0
    assert all(m.shape == frame.shape[:2] for m in result.raw_masks.values())


def test_hole_is_preserved_and_changes_center():
    frame = scenes()["asymmetric_ring"][0]
    result = detect_with_diagnostics(frame, config())
    mask = result.cleaned_masks["blue"]
    assert mask[233, 338] == 0
    assert result.detections[0].center_x < 317


def test_edge_exclusion_is_configurable():
    frame = scenes()["truncated"][0]
    cfg = config()
    assert detect_buckets(frame, cfg)[0].possibly_truncated
    cfg["filters"]["exclude_truncated"] = True
    assert detect_buckets(frame, cfg) == []


@pytest.mark.parametrize("image", [None, np.zeros((0, 2, 3), np.uint8),
                                      np.zeros((20, 20), np.uint8),
                                      np.zeros((20, 20, 3), np.float32)])
def test_invalid_image_is_not_empty_detection(image):
    with pytest.raises(ValueError):
        detect_buckets(image, config())


def test_different_resolution_and_no_input_mutation():
    frame = np.zeros((600, 800, 3), np.uint8)
    cv2.rectangle(frame, (620, 410), (710, 480), (0, 255, 255), -1)
    before = frame.copy()
    target = detect_buckets(frame, config())[0]
    assert (target.center_x, target.center_y) == pytest.approx((665.0, 445.0))
    assert np.array_equal(frame, before)


def test_area_and_shape_filters():
    frame = scenes()["three_colors"][0]
    cfg = config()
    cfg["filters"]["min_area_fraction"] = 0.1
    assert detect_buckets(frame, cfg) == []
    cfg = config()
    cfg["filters"]["max_area_fraction"] = 0.001
    assert detect_buckets(frame, cfg) == []
    cfg = config()
    cfg["filters"]["min_solidity"] = 0.95
    assert detect_buckets(scenes()["asymmetric_ring"][0], cfg) == []


def main():
    """独立执行测试，然后保存所有场景的诊断文件。"""
    if pytest.main([str(Path(__file__).resolve()), "-q"]) != 0:
        return 1
    from bucket_hsv.io import save_debug
    cfg = config()
    for name, (frame, _) in scenes().items():
        save_debug(ROOT / "results/synthetic" / name, frame,
                   detect_with_diagnostics(frame, cfg))
    print("合成场景已保存到 results/synthetic/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
