# 攀岩助手

在自己的电脑上整理抱石线路、回看攀爬过程。支持照片选线、视频骨架与基础统计，以及复盘视频和资料导出。

**[下载 Windows 安装包](https://github.com/Huoxixi/climbing-assistant-local/releases/latest)** · Windows 10/11 64 位 · 当前版本 `0.1.18-local.20261018`

## 安装与开始使用

1. 下载发布页中的 **ClimbingAssistant-Windows-0.1.18-local.20261018.zip**，右键「全部解压」。
2. 双击 **安装攀岩助手.exe**，点击「开始安装」。同目录的 **安装说明.txt** 可随时查看。
3. 完成后点击「打开攀岩助手」，以后从桌面的「攀岩助手（公开版）」打开。

首次安装需要联网，运行环境和识别模型自动准备，无需自己安装 Python 或配置命令。之后照片、视频识别在本机进行，不需要外部服务密钥。

下载约 **56 MiB**；安装过程约需 **3 GiB** 空间，完成后约 **1.6 GiB**，不含个人照片和视频。缺少微软 WebView2 时，安装器会自动准备，需额外空间。

安装中可以停止或取消。失败、停止或取消会清理**本次新装的程序、环境、模型和缓存**，保留已有应用与个人资料。若文件被占用，按提示点击「继续清理」；清理完成后可重新安装。

## 能做什么

| 功能 | 使用方式 |
| --- | --- |
| 照片选线 | 上传岩壁照片 → 识别候选岩点 → 自己选线、补删和精修 → 保存到线路库 |
| 视频复盘 | 选择视频 → 从画面取色、识别并确认岩点，或选择「只生成骨架」 → 开始分析 |
| 观察动作 | 左侧原视频，右侧骨架、岩点使用记录和二维估算重心路线；查看时间、关节角度、身体倾斜和姿态停留等统计 |
| 保存与导出 | 回看历史记录，导出复盘视频或「视频＋全部资料」，支持选择范围和速度；原视频保留 |
| 文件存储 | 在桌面版设置中选择空文件夹，下次启动复制资料并切换，保留原文件 |

只生成骨架时，不计算岩点接触与使用率。照片线路默认由自己逐点选择，不自动把同色岩点当作一条路线。

## 目前能做到的程度

基础照片选线、视频复盘和导出流程已可使用，但**识别结果需要自己检查**：遮挡、旁人入镜、镜头晃动或身体出画，可能造成漏点、骨架不完整或选错人。速度取决于电脑配置及视频长度、分辨率。

重心路线是二维视频中的估算；手脚靠近岩点也不等于真正抓住或踩稳。不能据此判断真实受力、三维重心、线路难度，或替代教练点评。目前没有云端点评、不同视频的技巧对比或自动定线功能。

已在当前 Windows 电脑验证安装、模型运行、桌面打开与视频转换，尚未完成跨电脑、所有显卡和视频格式的全面验证。[详细验证记录](docs/VALIDATION.md)

## 资料与常见问题

照片、视频和复盘记录留在自己的电脑，不发送到外部分析服务。默认资料目录为 `%LOCALAPPDATA%\ClimbingAssistantCommunity`；更新时会沿用旧版公开资料位置。安装联网获取组件与模型，来源包括 PyPI、PyTorch、Kaggle、OpenMMLab 和微软。

| 问题 | 处理方法 |
| --- | --- |
| 安装失败或下载中断 | 按窗口提示检查网络和空间，清理完成后重新安装；「查看日志」可复制具体错误 |
| 安装时提示未知发布者 | 当前安装器未取得代码签名；请从本仓库发布页下载，发布页提供 SHA-256 校验文件 |
| 识别不完整或人物选错 | 尽量保持完整取景、减少遮挡和旁观者；保存前复核岩点，检查骨架是否跟随正确的人 |
| 导出失败 | 检查磁盘空间与原视频是否可读取；失败不会删除已有结果 |
| 更新后找不到记录 | 检查设置中的资料位置；内部开发版资料不会自动导入 |

仅用于本机单人使用。删除或迁移资料前请先备份。问题反馈见 [Issues](https://github.com/Huoxixi/climbing-assistant-local/issues)，附系统版本、操作步骤和错误信息即可，不要上传密钥或完整个人资料目录。

## 项目结构

桌面窗口 / 浏览器 → Vue 界面 → FastAPI 本地服务 → 岩点与姿态处理 → 本地存储和视频导出。

| 目录 | 职责 |
| --- | --- |
| `frontend/` | 照片选线、岩点编辑、线路库、复盘播放器和设置 |
| `backend/` | 任务处理、模型推理、人物跟踪、坐标对齐、基础统计与 FFmpeg 导出 |
| `desktop/`、`run-local.py` | 本地窗口、访问保护、资料存储与程序生命周期 |
| `installer/` | 中文安装器、环境与模型准备、下载校验及失败清理 |
| `docs/` | 开发、模型、架构和验证说明 |

服务仅监听本机。更详细的 [架构说明](docs/ARCHITECTURE.md)、[源码开发与启动](docs/DEVELOPMENT.md)、[模型说明](docs/MODELS.md)、[安装器重建](docs/INSTALLER.md) 供开发者查阅。源码包 `ClimbingAssistant-local-*.zip` 用于开发，普通用户下载上方 Windows 包。

## 开源来源与许可证

本项目实现照片与视频工作流、人工复核、跟踪与对齐、统计展示、历史恢复及导出；识别模型和基础框架来自以下项目：

| 来源 | 用途 |
| --- | --- |
| [rtmlib](https://github.com/Tau-J/rtmlib) | 实际复用并适配姿态、人体检测的预处理与解码代码，Apache-2.0 |
| [MMPose / RTMW](https://github.com/open-mmlab/mmpose)、[YOLOX](https://github.com/Megvii-BaseDetection/YOLOX) | 官方姿态和人体检测权重 |
| [Detectron2](https://github.com/facebookresearch/detectron2)、[Tomáš Sláma 的岩点分割项目](https://github.com/xiaoxiae/Indoor-Climbing-Hold-and-Route-Segmentation)及其 [Kaggle 发布](https://www.kaggle.com/datasets/tomasslama/indoor-climbing-gym-hold-segmentation) | 岩点分割框架、配置和专项模型 |
| Vue、Vite、Element Plus、FastAPI、pywebview | 界面、本地服务与桌面窗口 |
| ONNX Runtime、PyTorch、TorchVision、OpenCV、NumPy、Pillow、FFmpeg | 模型运行、图像计算和视频处理 |
| Noto CJK、MiSans | 中文字体，分别遵循原字体许可与小米字体条款 |

项目代码采用 **[GPL-3.0](LICENSE)**。第三方代码、字体、组件和模型各自保留原始许可，源码许可不等于模型与训练数据的全部使用条件。模型安装时从原来源下载；Detectron2 扩展的对应源码与许可随安装包提供。

完整来源、修改说明、研究参考和分发边界见 **[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)**。贡献前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)，安全问题见 [SECURITY.md](SECURITY.md)。
