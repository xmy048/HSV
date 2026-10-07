#!/usr/bin/env python3
"""视频/摄像头逐帧检测；30 Hz 输入不等同于处理 FPS。"""
import argparse
import csv
import json
import logging
from pathlib import Path
import platform
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if (ROOT / "src").is_dir():
    sys.path.insert(0, str(ROOT / "src"))

import cv2
from bucket_hsv import load_config, detect_with_diagnostics
from bucket_hsv.io import save_debug
from bucket_hsv.performance import PerformanceStats
from bucket_hsv.visualization import render_detections


def nonnegative(text):
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError("参数不能为负数")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--video", type=Path)
    source.add_argument("--camera", type=nonnegative, help="摄像头设备编号")
    parser.add_argument("--config", type=Path, default=ROOT / "config/default.yaml")
    parser.add_argument("--output", type=Path, default=ROOT / "results/performance/run")
    parser.add_argument("--no-display", action="store_true")
    parser.add_argument("--max-frames", type=nonnegative, default=0, help="0 为处理至结束")
    parser.add_argument("--warmup", type=nonnegative, default=30, help="预热帧仍检测并输出")
    parser.add_argument("--save-debug-every", type=nonnegative, default=0,
                        help="每 N 帧保存诊断图；0 禁用，不影响逐帧检测")
    parser.add_argument("--opencv-threads", type=nonnegative, default=None,
                        help="可选 OpenCV 线程数；默认沿用库设置")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        cfg = load_config(args.config)
        if args.opencv_threads is not None:
            cv2.setNumThreads(args.opencv_threads)
        cap = cv2.VideoCapture(str(args.video) if args.video is not None else args.camera)
        if not cap.isOpened():
            cap.release()
            logging.error("无法打开输入：%s", args.video if args.video is not None else args.camera)
            return 1
        input_fps = cap.get(cv2.CAP_PROP_FPS)
        expected_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) if args.video else 0
        args.output.mkdir(parents=True, exist_ok=True)
    except (ValueError, OSError, cv2.error) as exc:
        logging.error("初始化失败：%s", exc)
        return 1
    all_stats, steady_stats = PerformanceStats(), PerformanceStats()
    sizes = set()
    frame_index = 0
    failed = False
    reason = "eof"
    steady_start = None
    start = perf_counter()
    try:
        with (args.output / "frames.jsonl").open("w", encoding="utf-8") as jsonl, \
                (args.output / "timings.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["frame_index", "elapsed_ms", "detections", "width", "height"])
            while args.max_frames == 0 or frame_index < args.max_frames:
                if frame_index == args.warmup:
                    steady_start = perf_counter()
                ok, frame = cap.read()
                if not ok:
                    if args.camera is not None:
                        logging.error("摄像头图像读取失败")
                        failed, reason = True, "read_error"
                    elif expected_frames > 0 and frame_index < expected_frames:
                        logging.error("视频提前结束：读取 %d / %d 帧", frame_index, expected_frames)
                        failed, reason = True, "read_error"
                    break
                save = args.save_debug_every > 0 and frame_index % args.save_debug_every == 0
                result = detect_with_diagnostics(frame, cfg, include_masks=save or not args.no_display)
                height, width = frame.shape[:2]
                sizes.add((width, height))
                info = {"frame_index": frame_index, "elapsed_ms": result.elapsed_ms,
                        "image_size": {"width": width, "height": height},
                        "detections": [d.to_dict() for d in result.detections]}
                if save:
                    save_debug(args.output / "debug" / ("{:06d}".format(frame_index)), frame,
                               result, {"frame_index": frame_index})
                jsonl.write(json.dumps(info, ensure_ascii=False) + "\n")
                writer.writerow([frame_index, result.elapsed_ms, len(result.detections), width, height])
                # 所有配置的帧产物写入成功后才算完成，避免失败帧贡献成功 FPS。
                all_stats.add(result.elapsed_ms)
                if frame_index >= args.warmup:
                    steady_stats.add(result.elapsed_ms)
                frame_index += 1
                if not args.no_display:
                    cv2.imshow("Color region centroid", render_detections(frame, result))
                    if cv2.waitKey(1) & 0xff in (27, ord("q")):
                        reason = "user_stop"
                        break
            else:
                reason = "max_frames"
    except KeyboardInterrupt:
        reason = "interrupted"
    except (ValueError, OSError, cv2.error) as exc:
        logging.error("处理失败：%s", exc)
        failed, reason = True, "processing_error"
    finally:
        # 捕获处理、绘图和结果写入时间；释放设备不计入处理 FPS。
        end = perf_counter()
        cap.release()
        if not args.no_display:
            cv2.destroyAllWindows()
    report = all_stats.summary(end - start)
    report.update({"timed_frames": len(steady_stats.samples_ms),
                   "steady_state": steady_stats.summary(end - steady_start if steady_start else 0),
                   "warmup_frames_requested": args.warmup,
                   "input_fps_reported": input_fps, "image_sizes": sorted(sizes),
                   "source": str(args.video) if args.video else "camera:{}".format(args.camera),
                   "no_display": args.no_display, "save_debug_every": args.save_debug_every,
                   "opencv_version": cv2.__version__, "opencv_threads": cv2.getNumThreads(),
                   "python_version": platform.python_version(), "machine": platform.machine(),
                   "config": cfg, "end_reason": reason, "success": not failed and frame_index > 0,
                   "fps_definition": "成功处理帧数 / 包含读取和输出的墙钟时间；视频文件不按输入 FPS 限速"})
    try:
        (args.output / "summary.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        logging.error("统计保存失败：%s", exc)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if frame_index == 0:
        logging.error("没有成功处理任何帧，不构成有效性能测试")
        return 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
