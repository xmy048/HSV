"""检测耗时统计。实际 FPS 使用调用方提供的墙钟时间。"""
import math
import numpy as np


class PerformanceStats:
    def __init__(self):
        self.samples_ms = []

    def add(self, elapsed_ms):
        if not math.isfinite(elapsed_ms) or elapsed_ms < 0:
            raise ValueError("检测耗时必须是有限非负数")
        self.samples_ms.append(float(elapsed_ms))

    def summary(self, elapsed_seconds):
        if not math.isfinite(elapsed_seconds) or elapsed_seconds < 0:
            raise ValueError("墙钟时间必须是有限非负数")
        count = len(self.samples_ms)
        return {"frames": count, "elapsed_seconds": float(elapsed_seconds),
                "mean_ms": float(np.mean(self.samples_ms)) if count else None,
                "max_ms": float(max(self.samples_ms)) if count else None,
                "p95_ms": float(np.percentile(self.samples_ms, 95)) if count else None,
                "processing_fps": count / elapsed_seconds if elapsed_seconds > 0 else 0.0}
