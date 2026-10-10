# 源码开发与启动

普通用户请使用 [Windows 安装包](https://github.com/Huoxixi/climbing-assistant-local/releases/latest)。以下为源码开发步骤。

### 1. 获取源码

**源码包：** 前往 [Releases](https://github.com/Huoxixi/climbing-assistant-local/releases)，下载 `ClimbingAssistant-local-*.zip`，解压后双击 `install.cmd`，完成后双击 `start.cmd`。源码方式需要 Python，并自行准备 Detectron2；普通用户使用上方安装 EXE。

**开发者：** 在 GitHub 点击 **Code → Download ZIP** 并解压，或：

```powershell
git clone https://github.com/Huoxixi/climbing-assistant-local.git
cd climbing-assistant-local
```

发布页提供同版本源码压缩包及 SHA-256 校验文件。程序源码与个人数据分别保存；不要解压覆盖自己的资料文件夹。

### 2. 安装运行环境

当前主支持平台为 **Windows 10/11 x64**。

- [Python 3.12 x64](https://www.python.org/downloads/windows/)：安装 Python Launcher；自定义 Python 路径也可通过 `setup.ps1 -Python` 指定。
- [Node.js](https://nodejs.org/en/download/)：仅开发者源码构建需要；22.12+ 的 22.x 或 24+，包含 npm。使用发布页的预构建界面包可跳过。
- [Microsoft WebView2 Evergreen Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/)：桌面窗口需要；浏览器模式可不依赖它。
- 首次安装需要联网下载依赖与约 265 MB 的姿态模型，实际下载体积还包括依赖、压缩包和视频编码工具。处理速度及内存占用取决于视频长度、分辨率和电脑配置；尚未给出经过跨机器验收的最低配置。

### 3. 一次安装

双击 `install.cmd`，或在源码目录执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
```

脚本在本目录创建 `.venv`，安装依赖，从 OpenMMLab 官方地址下载并校验 RTMW/YOLOX 模型。发布包的预构建界面通过清单校验后直接使用；只有纯源码下载或 `-RebuildFrontend` 才需要 Node.js 构建。脚本不读取旧开发目录，不复制你的照片或密钥，不请求任何收费分析服务。

自定义 Python：

```powershell
.\setup.ps1 -Python 'C:\Python312\python.exe'
```

模型已有或需要稍后自行安装时使用 `-SkipModels`。跳过安装不代表已具备姿态推理能力。

### 4. 启动

双击 `start.cmd` 打开独立桌面窗口。窗口关闭后本次后台服务退出。

也可运行浏览器模式：

```powershell
.\start.cmd --browser
```

浏览器模式中关闭网页不会结束后台；在启动终端按 `Ctrl+C` 退出。每次启动使用空闲的本地端口，不占用原项目端口。程序只监听 `127.0.0.1`，以实例凭证保护页面、API 与媒体。

默认资料位置为 `%LOCALAPPDATA%\ClimbingAssistantCommunity`，与内部 App 的资料目录独立；旧版公开资料自动沿用。指定新位置可用：

```powershell
.\start.cmd --data-root 'D:\MyClimbingData'
```

### 5. 可选：启用照片岩点识别

源码安装请按 [模型说明](MODELS.md) 安装 Detectron2 与专项权重。权重缺失时明确报错。Windows 源码安装的 Detectron2 编译需要额外工具链；普通用户使用的安装 EXE 已包含原生扩展，无需自行编译。

## 开发与验证

运行依赖安装完成后：

```powershell
$env:LOCAL_ONLY='true'
$env:PYTHON_DOTENV_DISABLED='1'
$env:PYTHONPATH="$PWD;$PWD\backend"
.\.venv\Scripts\python.exe -m unittest discover -s backend -p 'test_boulder*.py'
.\.venv\Scripts\python.exe -m unittest desktop.test_storage desktop.test_package_scope
cd frontend
npm run build -- --mode boulder-local
```

公开 CI 验证 Linux 的源码构建、部分本地数据流程与分发范围，**不测试真实视频识别质量、Windows 原生窗口或专项 Detectron2 扩展**。后端单测使用临时目录与合成数据，不调用收费服务。

如使用 Vite 开发服务，应配置 `LOCAL_ONLY=true`、独立 `PHOTO_ROUTE_DATA_DIR`，启动 `boulder_local_app:app`，并保持本地来源约束。普通使用者直接使用 `start.cmd`，不需要分别启动前后端。
