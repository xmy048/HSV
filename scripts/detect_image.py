#!/usr/bin/env python3
"""独立图片/目录检测；默认保存原尺寸调试图。"""
import argparse
from collections import Counter
import json
import logging
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if (ROOT / "src").is_dir():
    sys.path.insert(0, str(ROOT / "src"))

import cv2
from bucket_hsv import load_config, detect_with_diagnostics
from bucket_hsv.io import read_image, save_debug
from bucket_hsv.visualization import render_detections


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="图片路径或图片目录")
    parser.add_argument("--config", type=Path, default=ROOT / "config/default.yaml")
    parser.add_argument("--output", type=Path, default=ROOT / "results/real_images")
    parser.add_argument("--no-display", action="store_true", help="不创建窗口")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        config = load_config(args.config)
    except ValueError as exc:
        logging.error("%s", exc)
        return 1
    if args.input.is_dir():
        files = sorted(p for p in args.input.iterdir()
                       if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"))
    else:
        files = [args.input]
    if not files:
        logging.error("目录中没有可读取的图片")
        return 1
    stems = Counter(p.stem for p in files)
    failed = False
    for path in files:
        try:
            image = read_image(path)
            result = detect_with_diagnostics(image, config)
            folder = path.name if stems[path.stem] > 1 else path.stem
            save_debug(args.output / folder, image, result,
                       {"source": str(path.resolve()), "config": config})
            print(json.dumps({"source": str(path), "elapsed_ms": result.elapsed_ms,
                              "detections": [d.to_dict() for d in result.detections]},
                             ensure_ascii=False))
            if not result.detections:
                logging.info("%s 无有效候选", path.name)
            if not args.no_display:
                cv2.imshow("Color region centroid", render_detections(image, result))
                if cv2.waitKey(0) & 0xff in (27, ord("q")):
                    break
        except (ValueError, OSError, cv2.error) as exc:
            logging.error("%s", exc)
            failed = True
    if not args.no_display:
        cv2.destroyAllWindows()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
