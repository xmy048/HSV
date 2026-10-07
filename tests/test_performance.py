"""计时口径和统计边界验证。"""
import pytest
from bucket_hsv.performance import PerformanceStats


def test_known_samples_and_wall_clock_fps():
    stats = PerformanceStats()
    for value in [1, 2, 3, 4, 100]:
        stats.add(value)
    report = stats.summary(2.0)
    assert report["frames"] == 5
    assert report["mean_ms"] == 22
    assert report["max_ms"] == 100
    assert report["p95_ms"] == pytest.approx(80.8)
    assert report["processing_fps"] == 2.5
    assert report["elapsed_seconds"] == 2.0


def test_zero_frames_does_not_claim_performance():
    report = PerformanceStats().summary(1.0)
    assert report["frames"] == 0
    assert report["mean_ms"] is None
    assert report["p95_ms"] is None
    assert report["processing_fps"] == 0


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf")])
def test_reject_bad_duration(value):
    with pytest.raises(ValueError):
        PerformanceStats().add(value)
