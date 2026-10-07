"""真实子进程验证入口、文件产物和错误退出。"""
import json
import os
from pathlib import Path
import subprocess
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def run(script, *args):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / script), *map(str, args)],
                          cwd=ROOT, capture_output=True, text=True, timeout=30)


def test_image_cli_saves_masks_and_original_coordinates(tmp_path):
    frame = np.zeros((600, 800, 3), np.uint8)
    cv2.rectangle(frame, (620, 410), (710, 480), (0, 255, 255), -1)
    path = tmp_path / "输入.png"
    assert cv2.imwrite(str(path), frame)
    output = tmp_path / "output"
    proc = run("detect_image.py", path, "--no-display", "--output", output)
    assert proc.returncode == 0, proc.stderr
    folder = output / path.stem
    info = json.loads((folder / "detections.json").read_text())
    target = info["detections"][0]
    assert (target["center_x"], target["center_y"]) == (665.0, 445.0)
    assert info["image_size"] == {"width": 800, "height": 600}
    for color in ["red", "yellow", "blue"]:
        for suffix in ["raw", "cleaned"]:
            mask = cv2.imread(str(folder / (color + "_" + suffix + ".png")), 0)
            assert mask.shape == (600, 800)
    annotated = cv2.imread(str(folder / "annotated.jpg"))
    assert annotated.shape == frame.shape


def test_bad_image_is_failure(tmp_path):
    proc = run("detect_image.py", tmp_path / "missing.jpg", "--no-display", "--output", tmp_path)
    assert proc.returncode != 0
    assert "读取" in proc.stderr


def test_directory_keeps_processing_but_reports_bad_file(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    cv2.imwrite(str(inputs / "valid.png"), np.zeros((40, 60, 3), np.uint8))
    (inputs / "bad.jpg").write_text("broken")
    output = tmp_path / "output"
    proc = run("detect_image.py", inputs, "--no-display", "--output", output)
    assert proc.returncode != 0
    assert (output / "valid/detections.json").is_file()
    assert json.loads((output / "valid/detections.json").read_text())["detections"] == []


def test_image_output_preserves_two_files_with_same_stem(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    for ext in [".jpg", ".png"]:
        cv2.imwrite(str(inputs / ("frame" + ext)), np.zeros((40, 60, 3), np.uint8))
    output = tmp_path / "output"
    proc = run("detect_image.py", inputs, "--no-display", "--output", output)
    assert proc.returncode == 0, proc.stderr
    assert len(list(output.glob("*/detections.json"))) == 2


def test_stream_processes_every_frame_and_publishes_empty_results(tmp_path):
    video = tmp_path / "stream.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 30, (160, 120))
    assert writer.isOpened()
    for index in range(8):
        frame = np.zeros((120, 160, 3), np.uint8)
        if index % 2 == 0:
            cv2.circle(frame, (80, 60), 20, (0, 0, 255), -1)
        writer.write(frame)
    writer.release()
    output = tmp_path / "performance"
    proc = run("detect_stream.py", "--video", video, "--no-display", "--output", output,
               "--warmup", "2", "--save-debug-every", "3")
    assert proc.returncode == 0, proc.stderr
    rows = [json.loads(line) for line in (output / "frames.jsonl").read_text().splitlines()]
    assert len(rows) == 8
    assert [row["frame_index"] for row in rows] == list(range(8))
    assert all(rows[i]["detections"] == [] for i in [1, 3, 5, 7])
    assert all(len(rows[i]["detections"]) == 1 for i in [0, 2, 4, 6])
    report = json.loads((output / "summary.json").read_text())
    assert report["frames"] == 8
    assert report["timed_frames"] == 6
    assert report["processing_fps"] > 0
    assert report["image_sizes"] == [[160, 120]]
    assert len(list(output.glob("debug/*/detections.json"))) == 3


def test_bad_video_is_failure(tmp_path):
    proc = run("detect_stream.py", "--video", tmp_path / "missing.avi", "--no-display",
               "--output", tmp_path / "out")
    assert proc.returncode != 0
    assert "打开" in proc.stderr


def test_tuner_headless_saves_valid_configuration_and_masks(tmp_path):
    image = tmp_path / "frame.png"
    cv2.imwrite(str(image), np.zeros((100, 160, 3), np.uint8))
    saved = tmp_path / "tuned.yaml"
    output = tmp_path / "debug"
    proc = run("tune_hsv.py", image, "--no-display", "--save-config", saved,
               "--output", output)
    assert proc.returncode == 0, proc.stderr
    assert saved.is_file()
    assert (output / "red_raw.png").is_file()


def test_failed_debug_write_does_not_claim_successful_frame_or_fps(tmp_path):
    video = tmp_path / "frame.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 30, (160, 120))
    assert writer.isOpened()
    writer.write(np.zeros((120, 160, 3), np.uint8))
    writer.release()
    output = tmp_path / "output"
    (output / "debug").mkdir(parents=True)
    # 用实际文件阻塞诊断目录，不模拟文件系统或检测器。
    (output / "debug/000000").write_text("blocked", encoding="utf-8")
    proc = run("detect_stream.py", "--video", video, "--no-display", "--output", output,
               "--warmup", "0", "--save-debug-every", "1")
    assert proc.returncode != 0
    report = json.loads((output / "summary.json").read_text())
    assert report["success"] is False
    assert report["frames"] == 0
    assert report["processing_fps"] == 0
    assert report["mean_ms"] is None
    assert (output / "frames.jsonl").read_text() == ""
