"""Python 检测核心的独立及 catkin 安装配置。"""
from pathlib import Path
from setuptools import setup

options = dict(name="bucket_hsv", version="0.1.0", packages=["bucket_hsv"],
               package_dir={"": "src"}, python_requires=">=3.8",
               install_requires=["numpy>=1.21,<3", "opencv-python>=4.5,<5", "PyYAML>=5.4,<7"])

if Path(__file__).with_name("package.xml").exists():
    from catkin_pkg.python_setup import generate_distutils_setup

    options = generate_distutils_setup(**options)

setup(**options)
