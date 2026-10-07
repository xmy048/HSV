"""调参状态必须保持红色两段并拒绝非法范围。"""
from pathlib import Path
import pytest

from bucket_hsv import load_config
from bucket_hsv.tuning import apply_controls, controls_from_config

ROOT = Path(__file__).resolve().parents[1]


def test_red_second_range_and_round_trip():
    cfg = load_config(ROOT / "config/default.yaml")
    controls = controls_from_config(cfg, "red")
    controls["H2 low"] = 173
    updated = apply_controls(cfg, "red", controls)
    assert updated["colors"]["red"]["h_ranges"] == [[0, 10], [173, 179]]
    assert cfg["colors"]["red"]["h_ranges"] == [[0, 10], [170, 179]]
    assert apply_controls(cfg, "red", controls_from_config(cfg, "red")) == cfg


def test_reject_invalid_controls_instead_of_saving():
    cfg = load_config(ROOT / "config/default.yaml")
    controls = controls_from_config(cfg, "yellow")
    controls["H low"] = 40
    controls["H high"] = 20
    with pytest.raises(ValueError):
        apply_controls(cfg, "yellow", controls)


def test_morphology_and_filters_are_adjustable():
    cfg = load_config(ROOT / "config/default.yaml")
    controls = controls_from_config(cfg, "blue")
    controls.update({"kernel radius": 2, "open iterations": 0, "close iterations": 2,
                     "min area ppm": 800, "max aspect x100": 400, "exclude edge": 1})
    updated = apply_controls(cfg, "blue", controls)
    assert updated["morphology"]["kernel_size"] == 5
    assert updated["morphology"]["open_iterations"] == 0
    assert updated["morphology"]["close_iterations"] == 2
    assert updated["filters"]["min_area_fraction"] == 0.0008
    assert updated["filters"]["max_aspect_ratio"] == 4
    assert updated["filters"]["exclude_truncated"] is True
