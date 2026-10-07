#!/usr/bin/env python3
"""图片滑动条调参：1/2/3 切换红黄蓝，s 保存配置和诊断图，q 退出。"""
import argparse
import logging
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if (ROOT / "src").is_dir():
    sys.path.insert(0, str(ROOT / "src"))

import cv2
from bucket_hsv import load_config, save_config, detect_with_diagnostics
from bucket_hsv.config import COLORS
from bucket_hsv.io import read_image, save_debug
from bucket_hsv.tuning import controls_from_config, apply_controls
from bucket_hsv.visualization import render_detections


def show_preview(window, image):
    # 仅缩小显示预览，检测始终使用原图，输出坐标不变。
    height, width = image.shape[:2]
    factor = min(1.0, 1000 / width, 650 / height)
    preview = cv2.resize(image, (round(width * factor), round(height * factor))) if factor < 1 else image
    cv2.imshow(window, preview)


def create_controls(cfg, color):
    state = controls_from_config(cfg, color)
    groups = {}
    for window in ("HSV controls", "Processing controls"):
        cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window, 560, 600)
    for name, value in state.items():
        hsv = name.startswith(("H", "S ", "V "))
        window = "HSV controls" if hsv else "Processing controls"
        if name.startswith("H"):
            maximum = 179
        elif name.startswith(("S ", "V ")):
            maximum = 255
        elif "area ppm" in name:
            maximum = 1000000
        elif "aspect" in name:
            maximum = max(1000, value)
        elif "x1000" in name:
            maximum = 1000
        elif name in ("exclude edge", "connectivity 4/8"):
            maximum = 1
        elif name == "kernel shape":
            maximum = 2
        else:
            maximum = max(15, value)
        cv2.createTrackbar(name, window, value, maximum, lambda _: None)
        groups[name] = window
    return groups


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--config", type=Path, default=ROOT / "config/default.yaml")
    parser.add_argument("--save-config", type=Path, default=ROOT / "config/tuned.yaml")
    parser.add_argument("--output", type=Path, default=ROOT / "results/tuning")
    parser.add_argument("--color", choices=COLORS, default="red")
    parser.add_argument("--no-display", action="store_true", help="校验并保存当前配置和掩膜")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        cfg, image = load_config(args.config), read_image(args.image)
        if args.no_display:
            result = detect_with_diagnostics(image, cfg)
            save_config(args.save_config, cfg)
            save_debug(args.output, image, result, {"config": cfg})
            logging.info("有效配置及掩膜已保存：%s", args.save_config)
            return 0
        if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            raise ValueError("没有图形显示环境，请使用 --no-display 或直接编辑 YAML")
        color = args.color
        groups = create_controls(cfg, color)
        while True:
            valid = False
            try:
                state = {name: cv2.getTrackbarPos(name, window) for name, window in groups.items()}
                cfg = apply_controls(cfg, color, state)
                result = detect_with_diagnostics(image, cfg)
                show_preview("Color region centroid", render_detections(image, result))
                show_preview("Raw mask " + color, result.raw_masks[color])
                show_preview("Cleaned mask " + color, result.cleaned_masks[color])
                valid = True
            except ValueError as exc:
                # 上下限暂时反向时继续响应滑动条，不保存上次的旧配置冒充新参数。
                logging.debug("当前参数无效：%s", exc)
            key = cv2.waitKey(50) & 0xff
            if key in (27, ord("q")):
                break
            if key == ord("s"):
                if valid:
                    save_config(args.save_config, cfg)
                    save_debug(args.output, image, result, {"config": cfg})
                    logging.info("已保存：%s", args.save_config)
                else:
                    logging.warning("当前参数无效，请检查上下限后再保存")
            if key in (ord("1"), ord("2"), ord("3")):
                color = COLORS[key - ord("1")]
                cv2.destroyAllWindows()
                groups = create_controls(cfg, color)
    except (ValueError, OSError, cv2.error) as exc:
        logging.error("调参失败：%s", exc)
        return 1
    finally:
        if not args.no_display:
            cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
