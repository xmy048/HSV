"""加载和校验配置；入口启动时调用，检测循环中不读写 YAML。"""
from pathlib import Path
import copy
import math

import yaml

COLORS = ("red", "yellow", "blue")


def _number(value, name, minimum, maximum=None, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("{} 必须是数字".format(name))
    if integer and not isinstance(value, int):
        raise ValueError("{} 必须是整数".format(name))
    if not math.isfinite(value) or value < minimum or (maximum is not None and value > maximum):
        raise ValueError("{} 超出合法范围".format(name))


def _range(value, name, maximum):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("{} 必须是 [下限, 上限]".format(name))
    for item in value:
        _number(item, name, 0, maximum, integer=True)
    if value[0] > value[1]:
        raise ValueError("{} 下限不能大于上限".format(name))


def validate_config(data):
    """校验完整配置并返回独立副本，防止调参修改调用方数据。"""
    if not isinstance(data, dict):
        raise ValueError("配置根节点必须是映射")
    cfg = copy.deepcopy(data)
    try:
        if set(cfg["colors"]) != set(COLORS):
            raise ValueError("colors 必须包含 red、yellow、blue 三种颜色")
        for color in COLORS:
            spec = cfg["colors"][color]
            ranges = spec["h_ranges"]
            count = 2 if color == "red" else 1
            if not isinstance(ranges, list) or len(ranges) != count:
                raise ValueError("{} 必须配置 {} 段 H 范围".format(color, count))
            for interval in ranges:
                _range(interval, color + ".h_ranges", 179)
            _range(spec["s_range"], color + ".s_range", 255)
            _range(spec["v_range"], color + ".v_range", 255)
        morph = cfg["morphology"]
        if morph["kernel_shape"] not in ("ellipse", "rect", "cross"):
            raise ValueError("不支持的 kernel_shape")
        _number(morph["kernel_size"], "kernel_size", 1, integer=True)
        if morph["kernel_size"] % 2 == 0:
            raise ValueError("kernel_size 必须是正奇数")
        for key in ("open_iterations", "close_iterations"):
            _number(morph[key], key, 0, integer=True)
        _number(morph["connectivity"], "connectivity", 4, 8, integer=True)
        if morph["connectivity"] not in (4, 8):
            raise ValueError("connectivity 必须为 4 或 8")
        filters = cfg["filters"]
        for key in ("min_area_fraction", "max_area_fraction", "min_circularity", "min_solidity"):
            _number(filters[key], key, 0, 1)
        for key in ("min_aspect_ratio", "max_aspect_ratio"):
            _number(filters[key], key, 0)
            if filters[key] == 0:
                raise ValueError("{} 必须大于零".format(key))
        for prefix in ("area_fraction", "aspect_ratio"):
            if filters["min_" + prefix] > filters["max_" + prefix]:
                raise ValueError("{} 下限不能大于上限".format(prefix))
        if not isinstance(filters["exclude_truncated"], bool):
            raise ValueError("exclude_truncated 必须是 YAML 布尔值")
    except (KeyError, TypeError) as exc:
        raise ValueError("配置字段缺失或结构错误：{}".format(exc)) from exc
    return cfg


def load_config(path):
    try:
        with Path(path).open("r", encoding="utf-8") as stream:
            data = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError("无法读取配置 {}：{}".format(path, exc)) from exc
    return validate_config(data)


def save_config(path, data):
    validated = validate_config(data)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(yaml.safe_dump(validated, allow_unicode=True, sort_keys=False),
                           encoding="utf-8")
