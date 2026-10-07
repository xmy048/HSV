# 三色桶 HSV Implementation Plan

> **For agentic workers:** 使用 executing-plans 在当前目录逐项实现；步骤以复选框跟踪。

**Goal:** 独立检测三色候选，输出原图颜色区域质心，并交付调试工具、验证产物和 ROS1 适配。

**Architecture:** `src/bucket_hsv` 为无 ROS 检测包；图片、流和调参入口复用核心。ROS 只做消息适配，诊断掩膜按需返回。

**Tech Stack:** Python 3.8+、OpenCV 4、NumPy、PyYAML、pytest；ROS1 Noetic 仅写代码。

**Spec:** `三色桶HSV定位项目方案.md`

## Global Constraints

- 原图坐标、浮点质心、保留孔洞；无目标返回空列表。
- 核心不得导入 rospy 或 cv_bridge；不缩放、不主动跳帧。
- 所有 HSV、形态学和筛选参数来自 YAML；启动时加载。
- 输入错误不能伪装成空检测；斜拍不启用严格圆度过滤。
- 当前目录不是 Git 仓库，保留进度记录，不建立 worktree 或提交。
- 用户已明确要求按确认的方案开始实现，直接实施并完成验证。

## Review Focus

- 不对称孔洞及局部区域坐标偏移：矩质心与非零像素均值对照。
- 非 uint8/空/灰度输入：明确拒绝；正常黑图为空列表。
- 错误 YAML、反向阈值、非法核和布尔参数：启动即拒绝。
- 流输入不存在、零帧及正常结束：退出状态和统计不能误导。
- 全分辨率照片中的同色干扰、阴影分裂：人工查看结果并记录局限。

## Task 1: 配置、核心与合成测试

**Files:** `config/default.yaml`, `src/bucket_hsv/{__init__,config,detector}.py`, `tests/{conftest,test_synthetic,test_config}.py`, 依赖文件。

**Interfaces:** `load_config(path)->dict`, `validate_config(data)->dict`, `detect_buckets(image,config)->list[Detection]`, `detect_with_diagnostics(image,config)->DetectionResult`。Detection 包含颜色、质心、像素面积、bbox、截断、圆度及实心程度；Result 包含检测、掩膜、轮廓和耗时。

- [x] 编写并运行测试，确认核心与配置尚不存在导致失败。
- [x] 实现校验、连通区域（ROI 内掩膜 moments 后还原偏移）、可选外形过滤。
- [x] 运行三色、多目标、色相两端、黑图、噪声、非对称环、边缘、斜拍及配置测试，全部通过。

## Task 2: 图片入口与诊断输出

**Files:** `src/bucket_hsv/{visualization,io}.py`, `scripts/detect_image.py`, `tests/test_cli.py`。

**Interfaces:** `render_detections(image,result)->ndarray`, `save_debug(output,image,result)->None`, `read_image(path)->ndarray`。图片入口支持单图/目录、配置、输出目录、无窗口。

- [x] 先运行 CLI 测试，检查不存在的脚本失败。
- [x] 实现 JSON、六张掩膜和标注图输出，检查写入失败。
- [x] 用合成图片跑通 headless 入口及读取失败测试，然后处理 9 张原尺寸照片。
- [x] 查看实际标注结果，保存对照图和观察报告；需要时提供独立现场调试配置，不冒充默认阈值通用。

## Task 3: 视频入口与性能

**Files:** `src/bucket_hsv/performance.py`, `scripts/detect_stream.py`, `tests/test_performance.py`，扩展 CLI 测试。

**Interfaces:** `PerformanceStats.add(ms)`, `summary(elapsed_seconds)->dict`；流入口逐帧检测，输出 JSONL/CSV/统计 JSON，可选显示和采样保存调试图。

- [x] 编写统计边界和短视频端到端失败测试。
- [x] 实现单调时钟检测计时、逐帧统计、平均/最大/P95 和墙钟 FPS。
- [x] 创建可复现的 640×480、30 FPS 合成视频，连续跑测试并保留结果；不把文件吞吐宣称为相机实测。

## Task 4: 滑动条工具

**Files:** `src/bucket_hsv/tuning.py`, `scripts/tune_hsv.py`, `tests/test_tuning.py`。

**Interfaces:** 将滑动条状态转成配置并完整校验，红色两段可调，形态学及面积/比例参数可调；有效配置才保存。

- [x] 先测试非法滑动条组合不能保存、红色第二段变化生效、配置往返。
- [x] 实现图形界面和无窗口检查/掩膜保存；无显示环境给予日志。
- [x] 执行无窗口路径测试；交互 GUI 未运行时明确记录。

## Task 5: ROS、文档和最终验证

**Files:** `scripts/bucket_detector_node.py`, `msg/*.msg`, `launch/*.launch`, `package.xml`, `CMakeLists.txt`, `setup.py`, `README.md`, `results/验证报告.md`。

- [x] ROS 只调用已验证核心：bgr8、queue_size=1、空数组发布、输入 header 沿用、错误日志。
- [x] 写 catkin 消息和 Python 安装、launch 参数；用语法/XML 检查，不声称 ROS 编译运行。
- [x] 中文 README 写完整命令、参数、实际照片局限和性能结果。
- [x] 完整 pytest、编译静态检查、独立合成脚本、真实照片产物检查；最后代码审查。

## 进度

执行证据与决策记录在 `docs/superpowers/plans/实施记录.md`，不改变原方案的历史状态。
