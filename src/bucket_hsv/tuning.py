"""滑动条状态转换。非法上下限必须修正后才能保存。"""
import copy
from .config import validate_config

SHAPES = ("ellipse", "rect", "cross")


def controls_from_config(config, color):
    spec, morph, filters = config["colors"][color], config["morphology"], config["filters"]
    controls = {"H low": spec["h_ranges"][0][0], "H high": spec["h_ranges"][0][1],
                "S low": spec["s_range"][0], "S high": spec["s_range"][1],
                "V low": spec["v_range"][0], "V high": spec["v_range"][1],
                "kernel radius": (morph["kernel_size"] - 1) // 2,
                "kernel shape": SHAPES.index(morph["kernel_shape"]),
                "open iterations": morph["open_iterations"],
                "close iterations": morph["close_iterations"],
                "connectivity 4/8": int(morph["connectivity"] == 8),
                "min area ppm": round(filters["min_area_fraction"] * 1000000),
                "max area ppm": round(filters["max_area_fraction"] * 1000000),
                "min aspect x100": round(filters["min_aspect_ratio"] * 100),
                "max aspect x100": round(filters["max_aspect_ratio"] * 100),
                "min circularity x1000": round(filters["min_circularity"] * 1000),
                "min solidity x1000": round(filters["min_solidity"] * 1000),
                "exclude edge": int(filters["exclude_truncated"])}
    if color == "red":
        controls.update({"H2 low": spec["h_ranges"][1][0], "H2 high": spec["h_ranges"][1][1]})
    return controls


def apply_controls(config, color, controls):
    updated = copy.deepcopy(config)
    spec, morph, filters = updated["colors"][color], updated["morphology"], updated["filters"]
    spec["h_ranges"][0] = [controls["H low"], controls["H high"]]
    if color == "red":
        spec["h_ranges"][1] = [controls["H2 low"], controls["H2 high"]]
    spec["s_range"] = [controls["S low"], controls["S high"]]
    spec["v_range"] = [controls["V low"], controls["V high"]]
    morph.update({"kernel_size": 2 * controls["kernel radius"] + 1,
                  "kernel_shape": SHAPES[controls["kernel shape"]],
                  "open_iterations": controls["open iterations"],
                  "close_iterations": controls["close iterations"],
                  "connectivity": 8 if controls["connectivity 4/8"] else 4})
    filters.update({"min_area_fraction": controls["min area ppm"] / 1000000,
                    "max_area_fraction": controls["max area ppm"] / 1000000,
                    "min_aspect_ratio": controls["min aspect x100"] / 100,
                    "max_aspect_ratio": controls["max aspect x100"] / 100,
                    "min_circularity": controls["min circularity x1000"] / 1000,
                    "min_solidity": controls["min solidity x1000"] / 1000,
                    "exclude_truncated": bool(controls["exclude edge"])})
    return validate_config(updated)
