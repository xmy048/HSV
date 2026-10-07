"""独立 Python 包安装配置。"""
from setuptools import setup

setup(name="bucket_hsv", version="0.1.0", packages=["bucket_hsv"],
      package_dir={"": "src"}, python_requires=">=3.8",
      install_requires=["numpy>=1.21,<3", "opencv-python>=4.5,<5", "PyYAML>=5.4,<7"])
