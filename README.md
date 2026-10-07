# 三色桶 HSV 像素定位

Python/OpenCV 同时分割红、黄、蓝颜色，筛选独立候选，输出对应输入原图的浮点像素质心。当前只使用独立图片、视频和摄像头入口，集中测试核心算法效果。

**中心是去噪后颜色区域质心，不自动等于桶口中心。** 斜拍时桶壁、反光、阴影、遮挡和截断会改变中心。颜色与外形筛选不能保证候选就是桶；本项目不包含飞行和投放控制。

## 1. 环境与安装

Python 3.8+，OpenCV 4、NumPy、PyYAML。测试另需 pytest。本次实际使用系统 Python 3.12、OpenCV 4.6.0、NumPy 1.26.4、PyYAML 6.0.1。

当前目录已建立 `.venv`，复用 `/usr/bin/python3` 已有依赖，可直接执行：

```bash
.venv/bin/python scripts/detect_image.py --help
```

默认 conda 的 `python3` 不具有本项目依赖，请使用 `.venv/bin/python`。已建环境不需再次下载依赖。

在其他电脑建立独立环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

如果当前挂载盘不支持符号链接，而系统 Python 已安装依赖，可以这样重建（不要对正在使用的环境重复执行）：

```bash
mkdir -p .venv/lib64
/usr/bin/python3 -m venv --copies --system-site-packages --without-pip .venv
```

入口会使用 `src/` 源码，无需 `pip install -e .`。希望从其他目录导入核心时，在具有 pip 的环境执行 `python -m pip install -e .`，依赖仍按 requirements 安装。

## 2. 图片检测

用初始参数处理单张图片：

```bash
.venv/bin/python scripts/detect_image.py data/DJI_20260917145809_0003_V.JPG \
  --config config/default.yaml --output results/example --no-display
```

用当前照片的调参配置处理整个目录：

```bash
.venv/bin/python scripts/detect_image.py data \
  --config config/field_photos.yaml --output results/real_images/tuned --no-display
```

删除 `--no-display` 可打开结果窗口，按任意键看下一张，按 q/ESC 退出；服务器使用无窗口模式。输入目录只读取当前层的 JPG/JPEG/PNG/BMP/TIF/TIFF。部分图片读取失败时继续处理其他图片，最终以非零状态退出。

标准输出为逐图 JSON；每张图的输出子目录包含：

```text
annotated.jpg       # 原尺寸轮廓、中心十字、颜色和坐标
detections.json     # 坐标、面积、bbox、截断及检测耗时
red_raw.png        # 红色原始掩膜
red_cleaned.png    # 红色去噪掩膜
yellow_raw.png
yellow_cleaned.png
blue_raw.png
blue_cleaned.png
```

结果图中的 `COLOR REGION CENTROID` 表示“颜色区域质心”，`possibly truncated` 表示“可能截断”。OpenCV 默认字体不直接绘制中文，图上使用英文，中文含义见此说明和 JSON。

同名但扩展名不同的图片会使用包含扩展名的目录，避免相互覆盖。重复运行同一输出目录会更新该输入的产物；需要保留历史时指定新目录。

## 3. 核心接口与坐标

```python
from bucket_hsv import load_config, detect_buckets
from bucket_hsv.io import read_image

config = load_config("config/default.yaml")  # 启动时一次加载和校验
image = read_image("data/DJI_20260917145809_0003_V.JPG")
targets = detect_buckets(image, config)
for target in targets:
    print(target.color, target.center_x, target.center_y)
```

`targets` 是 `Detection` 列表，颜色为 red/yellow/blue；需要字典时使用 `target.to_dict()`。同色多个独立区域分别返回，无目标返回 `[]`。空图像、灰度、浮点图像等无效输入抛出 `ValueError`，不能视为正常无目标。

原点为原图左上角，x 向右，y 向下。程序不改变检测输入尺寸。候选内部使用局部区域掩膜节省计算，中心加回区域偏移，还原到原图。

用 `cv2.moments(region, binaryImage=True)` 对实际区域计算 `M10/M00`、`M01/M00`。孔洞保留；外轮廓用于绘图和外形指标，不填满轮廓求中心。`M00 <= 0` 时记录日志并跳过。

需要耗时和掩膜时使用 `detect_with_diagnostics(image, config)`；仅需要检测和耗时时可传 `include_masks=False`。检测核心不导入 rospy 或 cv_bridge。

## 4. YAML 参数与斜拍

默认 HSV：红 H=0–10 或 170–179；黄 H=20–35；蓝 H=95–130。三色均 S=80–255、V=45–255，范围含端点。OpenCV H 取 0–179，S/V 取 0–255。

| 配置字段 | 含义 |
| --- | --- |
| `colors.*.h_ranges` | H 范围；红色两段，黄色和蓝色各一段 |
| `colors.*.s_range/v_range` | 饱和度/亮度的上下限 |
| `morphology.kernel_shape` | ellipse、rect、cross |
| `morphology.kernel_size` | 正奇数核尺寸，默认 3 |
| `morphology.open_iterations` | 开运算次数，默认 1，0 禁用 |
| `morphology.close_iterations` | 闭运算次数，默认 1，0 禁用 |
| `morphology.connectivity` | 连通性，默认 8，可设 4 |
| `filters.min/max_area_fraction` | 区域颜色像素数/原图总像素数，默认 0.0005–0.8 |
| `filters.min/max_aspect_ratio` | 轴对齐 bbox 宽/高，默认 0.15–6.0 |
| `filters.min_circularity` | 外轮廓圆度下限，默认 0（禁用） |
| `filters.min_solidity` | 颜色像素面积/凸包面积下限，默认 0（禁用） |
| `filters.exclude_truncated` | 是否剔除接触图像边缘的候选，默认 false |

圆度使用外轮廓面积和周长，实心程度使用保留孔洞的颜色像素面积。离散像素面积与几何面积略有差异，比值上限截为 1。斜拍默认不要求接近正圆，宽高比范围保持宽松。

`config/field_photos.yaml` 是针对已提供 9 张照片调试的配置：黄色 S 下限提高到 140，边缘候选剔除开启。它减少了草地黄色误检和一处边缘红色背景干扰。代价是低饱和度黄色和接触边缘的真桶可能漏检，需要根据现场重新调参。

所有普通入口在启动时加载一次 YAML，不每帧读写。参数错误在启动时报告。

## 5. 滑动条调参

```bash
.venv/bin/python scripts/tune_hsv.py data/DJI_20260917151230_0083_V.JPG \
  --config config/field_photos.yaml --color yellow \
  --save-config config/tuned.yaml --output results/tuning
```

- 1/2/3：切换红/黄/蓝。
- HSV 窗口调节上下限，红色支持 H2 第二段。
- Processing 窗口调节核半径、核形状、开闭次数、连通性、面积、宽高比、可选外形指标和边缘策略。
- 核尺寸 = 2×半径+1；面积 ppm = 面积比例×1000000；宽高比 x100 = 比值×100；外形指标 x1000 = 指标×1000。
- 核形状 0/1/2 对应 ellipse/rect/cross，连通性 0/1 对应 4/8。
- s：保存有效 YAML 及当前掩膜/结果；q/ESC：退出。参数上下限反向时不能保存。

预览可缩小显示，检测和输出仍对应原图。没有图形界面时编辑 YAML，再执行：

```bash
.venv/bin/python scripts/tune_hsv.py data/DJI_20260917151230_0083_V.JPG \
  --config config/field_photos.yaml --no-display \
  --save-config config/tuned.yaml --output results/tuning
```

此模式只校验、保存当前配置并生成诊断图，不模拟滑动条交互。

## 6. 视频和摄像头

```bash
.venv/bin/python scripts/detect_stream.py --video your_video.mp4 \
  --config config/field_photos.yaml --no-display --output results/performance/video

.venv/bin/python scripts/detect_stream.py --camera 0 --max-frames 900 \
  --config config/field_photos.yaml --no-display --output results/performance/camera
```

输出 `frames.jsonl`（每个成功处理帧的完整结果，含空数组）、`timings.csv`（逐帧检测耗时）和 `summary.json`（统计及测试条件）。默认处理全部帧，不主动跳帧，也不按视频文件的 30 FPS 元数据限速。

`--warmup 30` 默认把前 30 帧作为预热，但仍检测和输出。主统计包含全部帧；`steady_state` 单独报告预热后统计，`timed_frames` 为预热后帧数。

检测耗时包括颜色转换、分割、形态学、区域/轮廓、筛选和质心计算，不包括读帧、显示和保存。实际处理 FPS 使用包含读帧、绘图、输出及文件关闭刷新的墙钟时间。相机输入等待也计入墙钟时间。

`--save-debug-every 30` 每 30 帧保存一次完整诊断图，默认 0 禁用；此选项只控制保存频率，不跳过检测。`--opencv-threads N` 可显式设置 OpenCV 线程数，报告记录实际设置。

可复现合成性能测试：

```bash
.venv/bin/python scripts/generate_test_video.py
.venv/bin/python scripts/detect_stream.py \
  --video results/performance/synthetic_30hz.avi --no-display --warmup 30 \
  --output results/performance/synthetic_default
```

本次合成输入为 640×480、30 FPS、600 帧，包含三色斜拍椭圆、孔洞、噪点和空帧。实测平均检测 2.68 ms，P95 2.95 ms，最大 6.75 ms，墙钟处理约 301 FPS。结果来自本机文件回放，不代表实际无人机、实时相机或 ROS 链路的性能。

4000×3000 原照片的单帧检测明显更慢，不能把 640×480 结果外推到原照片尺寸。完整实测和局限见 [验证报告](results/验证报告.md)。

## 7. 测试与实际图片

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python tests/test_synthetic.py
```

禁用 pytest 自动插件加载是为了隔离本机 ROS2 的测试插件，不影响检测。独立合成脚本先执行测试，成功后将全部场景保存到 `results/synthetic/`。

覆盖三色同时出现、多个同色目标、红色两端、无目标、噪点、不对称圆环、截断、旋转椭圆/椭圆环、桶壁和反光缺口、遮挡分裂，以及输入/配置错误、原图坐标和流入口行为。质心通过非零像素坐标均值交叉检查。

实际调试目录：

- `results/real_images/`：初始参数结果。
- `results/real_images/tuned/`：照片调试配置结果。
- `results/real_images/contact_sheet.jpg`：初始参数九宫格。
- `results/real_images/tuned/contact_sheet.jpg`：调参后九宫格。

9 张照片原尺寸处理，已人工查看九宫格：调参后每张有一个对应颜色的候选，轮廓落在桶的可见颜色区域。没有人工逐像素真值或独立测试集，因此不宣称准确率或跨场景可靠性。

## 8. 当前阶段：只测试核心算法

ROS 节点、消息、launch 和 catkin 配置已按当前需求移除。`setup.py` 仅用于独立 Python 包安装。核心、图片/视频入口和调参工具直接运行。

直接检测现有照片：

```bash
.venv/bin/python scripts/detect_image.py data \
  --config config/field_photos.yaml --output results/core_test --no-display
```

查看输出目录中每张图片的 `annotated.jpg`，再对照 `detections.json` 和六张掩膜。每个十字表示颜色区域质心。原图和参数保持不变时，结果坐标应与前一次照片调试一致。

后续需要新环境接入时，再独立增加适配层。

## 9. 当前局限与待现场验证

- HSV 对光照敏感，现场继续调整 H/S/V，尤其黄色与草地的分离。
- 面积比例受目标距离影响；过高漏掉远桶，过低放过噪点。
- 开运算可能删细桶沿，闭运算可能连接相邻目标。
- 斜拍外形过滤保持宽松；同色背景物体仍可能误检。
- 分裂区域分别输出，粘连区域作为一个候选；没有自动拆分/合并。
- 截断标记只识别画面边缘接触，不能判断普通遮挡。
- 当前无摄像头实时测试，无滑动条 GUI 人工操作验证。
- 原始默认阈值、照片调参配置和合成测试通过都不能保证现场可靠。

## 10. 实现参考

调用 OpenCV 现成函数实现流程，使用 [OpenCV 形状分析与矩文档](https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html) 确认接口。本项目自行实现配置、候选筛选、质心输出和入口，没有复制库的算法源码。
