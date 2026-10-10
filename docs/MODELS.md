# 模型与运行资源

## 骨架模式：默认安装路径

`setup.ps1` 调用 `backend/scripts/install_replay_rtmw.py`，直接从 OpenMMLab 官方下载两个压缩包：

- RTMW-L 384×288 cocktail14 20231122：https://download.openmmlab.com/mmpose/v1/projects/rtmw/onnx_sdk/rtmw-dw-x-l_simcc-cocktail14_270e-384x288_20231122.zip
- YOLOX-S HumanArt：https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/yolox_s_8xb8-300e_humanart-3ef259a7.zip

脚本同时核对压缩包与提取 ONNX 的 SHA-256；已存在文件校验失败会停止并保留文件，不自动覆盖。最终目标是 `backend/model_assets/rtmw-l-384x288/rtmw.onnx` 与 `detector.onnx`，尺寸、文件摘要见该目录 `manifest.json`。权重不提交到 Git。

手动安装：

```powershell
.\.venv\Scripts\python.exe backend\scripts\install_replay_rtmw.py
```

Windows 优先 ONNX Runtime DirectML，可回退 CPU。不同显卡、驱动和 CPU 的性能尚未全部验收。MMPose/YOLOX 源码许可证不单独证明所有预训练权重与训练数据使用条件；部署或再分发前查阅来源。

## 照片与带岩点复盘：需要额外安装

当前专项模型来自 Tomáš Sláma 的 [Indoor Climbing Gym Hold And Route Segmentation](https://www.kaggle.com/datasets/tomasslama/indoor-climbing-gym-hold-segmentation)。既有记录注明数据元信息 CC BY-SA 4.0、研究源码 GPL-3.0，但 exact weight artifact 的公开再分发授权未核清。因此本仓库不复制内部权重，也不提供绕过来源许可的下载镜像。

自行核实许可并取得兼容权重后，将文件放在源码目录 `models/verified-model_final.pth`。文件名变化不改变权重内容。它必须对应两类 hold/volume、R50-FPN、p2/p3 ROI 的专项配置，不是任意 Mask R-CNN 权重。

安装可选依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-holds.txt
```

然后安装 [Detectron2](https://github.com/facebookresearch/detectron2) 对应源码构建。已使用基线为 `a2f4a877`；官方安装说明在 https://detectron2.readthedocs.io/en/latest/tutorials/install.html 。本次公开包不带内部 Windows cp312 CPU 扩展；Windows 原生编译仍需 C++ 构建工具及兼容 Torch ABI。这一步没有被伪装成 Windows 已验证的一键安装。

启动脚本会使用仓库内的两份 YAML 配置、用户取得的权重路径。缺模型、缺扩展或 ABI 不匹配时明确报错。照片默认使用专项模型原生实例掩膜及轮廓内颜色处理，不默认叠加 MobileSAM 或 DeepSeek。

## FFmpeg、字体与原生窗口

源码仓库没有 FFmpeg 可执行文件。`imageio-ffmpeg` 安装到用户环境时提供其对应发行版本；它的 BSD 包装层许可证与具体 FFmpeg 构建的 GPL/LGPL 条款不同。再制作二进制发行包时需要对应完整源码、构建材料与原许可证，不能只复制 executable。本项目当前发布的是源码。

后端中文渲染保留 Noto 字体及 OFL；界面嵌入未修改 MiSans 字体及来源说明。WebView2 由用户从微软安装，仓库不复制浏览器配置或运行时。Linux/macOS 的桌面窗口并未验收，现有 Linux CI 只检查源码与本地 API。
