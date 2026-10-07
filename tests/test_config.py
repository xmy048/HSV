"""配置边界：错误配置必须在处理图像前被拒绝。"""
from pathlib import Path
import copy

import pytest
import yaml

from bucket_hsv.config import load_config, save_config, validate_config

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("section,key,value", [
    ("filters", "min_area_fraction", -0.1),
    ("filters", "max_area_fraction", 1.2),
    ("filters", "exclude_truncated", "false"),
    ("filters", "min_aspect_ratio", 0),
    ("morphology", "kernel_size", 2),
    ("morphology", "open_iterations", -1),
    ("morphology", "connectivity", 3),
    ("morphology", "kernel_shape", "unknown"),
])
def test_reject_invalid_parameter(section, key, value):
    cfg = load_config(ROOT / "config/default.yaml")
    cfg[section][key] = value
    with pytest.raises(ValueError):
        validate_config(cfg)


@pytest.mark.parametrize("bad_range", [[170, 180], [20, 10], [False, 10], [0, 1.5]])
def test_reject_invalid_hue(bad_range):
    cfg = load_config(ROOT / "config/default.yaml")
    cfg["colors"]["red"]["h_ranges"][0] = bad_range
    with pytest.raises(ValueError):
        validate_config(cfg)


def test_save_reload_and_do_not_mutate(tmp_path):
    cfg = load_config(ROOT / "config/default.yaml")
    original = copy.deepcopy(cfg)
    validated = validate_config(cfg)
    validated["colors"]["red"]["s_range"][0] = 100
    assert cfg == original
    path = tmp_path / "中文配置.yaml"
    save_config(path, validated)
    assert load_config(path) == validated


def test_missing_and_malformed_config(tmp_path):
    with pytest.raises(ValueError):
        load_config(tmp_path / "missing.yaml")
    p = tmp_path / "bad.yaml"
    p.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(p)


def test_reject_nan_and_reversed_filters():
    cfg = load_config(ROOT / "config/default.yaml")
    cfg["filters"]["min_area_fraction"] = float("nan")
    with pytest.raises(ValueError):
        validate_config(cfg)
    cfg = load_config(ROOT / "config/default.yaml")
    cfg["filters"]["min_aspect_ratio"] = 4
    cfg["filters"]["max_aspect_ratio"] = 2
    with pytest.raises(ValueError):
        validate_config(cfg)
