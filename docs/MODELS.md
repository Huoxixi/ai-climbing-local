# 模型与运行资源

## 安装器自动准备

Windows 安装 EXE 包含独立 Python 3.12 x64、pip、预构建界面和 Detectron2 CPU 扩展。首次安装从原始来源获取其他依赖与模型并校验；无需用户编译或输入命令。模型不提交到 Git，也不放进安装 EXE。

岩点模型来自 Tomáš Sláma 的 [研究项目](https://github.com/xiaoxiae/Indoor-Climbing-Hold-and-Route-Segmentation) 及 [Kaggle 发布](https://www.kaggle.com/datasets/tomasslama/indoor-climbing-gym-hold-segmentation)，固定第 4 版 `model/model_final.pth`。Kaggle 元信息为 CC BY-SA 4.0，研究代码为 GPL-3.0。直接从作者地址获取，不镜像或上传内部权重；原来源条件仍适用，引用不代表作者背书。

| 资源 | 文件字节数 | SHA-256 |
| --- | ---: | --- |
| Kaggle 岩点模型压缩包 | 326917448 | `85a80cd02119d154b1e27f047d327beebfaffe7f99e4d24a117f11040d79aedf` |
| 岩点权重 | 351090931 | `995960a74819e21bd66d7be56ae6e1c8124ec0a06fece4fae13812887d86ebea` |
| RTMW-L ONNX | 229320930 | `bd033156e5104c4f5d2edfe0453e02661e30a2f3da453ec93c8764d561b83054` |
| YOLOX-S ONNX | 35998962 | `332e09ea9696e3401049b6c5314851db020b6430f85da159e65f37034ab3aee8` |

OpenMMLab 官方姿态模型地址与压缩包摘要在 `backend/scripts/install_replay_rtmw.py`，提取文件清单在对应 `manifest.json`。支持 CPU，Windows 姿态推理也可用 DirectML；不同显卡与驱动尚未全部验收。

## Detectron2 与 Python

安装器提供 Detectron2 `0.6/a2f4a877` Windows cp312 CPU 扩展，固定 Torch `2.8.0+cpu` / TorchVision `0.23.0+cpu`。程序内保留 Apache-2.0 许可证、`third_party_source/detectron2-source.zip` 完整对应源码和 `detectron2-build.json` 文件摘要。运行目录去掉未使用的模型库配置以避开 Windows 长路径，源码 ZIP 仍保留全部配置。

CPU Torch wheel 从官方地址下载并校验。在用户电脑上准备精简 wheel，去掉编译用 `.lib` 和头文件，保留运行 DLL、实现与所有许可，并更新 RECORD。精简 wheel 不被上传或再分发。模型加载与合成推理检查通过后才完成安装。

独立 CPython 使用 PSF 许可，原 `runtime/LICENSE.txt` 保留；pip 及其 vendored 通知一并保留。Python 仅作用于 App，不修改系统 PATH。重建方法见 [INSTALLER.md](INSTALLER.md)。

## 开发者源码方式

`setup.ps1` 准备 `.venv`、运行依赖和 RTMW/YOLOX；纯源码 ZIP 另需 Node.js 构建界面。照片识别需另装 `backend/requirements-holds.txt`、对应 Detectron2，并从原作者取得指定权重，放在 `models/verified-model_final.pth`。它对应两类 hold/volume、R50-FPN、ROI p2/p3，不能换成任意 Mask R-CNN。

## 视频、字体与窗口

安装时从软件源取得 `imageio-ffmpeg`；其 BSD 包装层与具体 FFmpeg 构建的 GPL/LGPL 条件不同。安装 EXE 与源码 ZIP 没有 FFmpeg 可执行文件；制作离线包需核实完整对应源码、构建和链接库材料。

中文渲染使用 Noto 字体及 OFL；界面嵌入未修改 MiSans 字体及来源说明。缺少 WebView2 时，安装器下载微软官方 bootstrapper，验证微软数字签名后按当前用户安装。来源失效、要求登录或校验不符时停止并提示处理，不绕过来源限制。
