"""三色 HSV 独立检测包。"""
from .config import load_config, save_config, validate_config
from .detector import Detection, DetectionResult, detect_buckets, detect_with_diagnostics

__all__ = ["Detection", "DetectionResult", "detect_buckets",
           "detect_with_diagnostics", "load_config", "save_config", "validate_config"]
