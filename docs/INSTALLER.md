# Windows 安装器实现与重建

普通用户使用发布 EXE。以下用于开发与审查。

## 流程

`WindowsApp.cs` 使用原生窗口，按系统 DPI 排版。首屏只有产品名、用途、空间提示和安装按钮。Python 输出结构化事件，窗口显示当前阶段、耗时、下载量和中文失败处理；出错可重试。

资源在 `%LOCALAPPDATA%\ClimbSetup\<版本>` 展开，逐项校验。独立环境准备在 `%LOCALAPPDATA%\Programs\AiClimb\<版本>.installing`，Windows 依赖版本固定。官方 CPU Torch wheel 校验后在本机剔除编译用静态库及头文件，不再分发这个精简 wheel。用户无需编译器。

模型从作者 Kaggle / OpenMMLab 获取并校验，支持接续下载；来源限制访问时停止。缺窗口组件时下载微软 WebView2，验证 Authenticode 签名后安装。

完成前实际加载模型、执行合成推理、检查视频组件与应用入口。准备目录改名为最终版本，创建「攀岩助手（公开版）」快捷方式。成功清理下载缓存，失败保留供重试。个人资料在独立 AiClimbingCommunity，不接触内部 `.local`。原生启动器用当前用户互斥锁避免重复打开；源码直接运行仍应避免多个进程共用资料。

## 构建输入与方法

- 已审查的 Git 源码和 boulder-local 前端构建。
- PSF 许可 CPython 3.12 x64；复制标准库，排除原环境 site-packages。
- 官方 pip 26.2.1 wheel，SHA-256 `71138adf1f4ca900cdb7d289c21b7494329f2332b6d85f0e1c42108c0384ed3e`。
- Detectron2 cp312 CPU 扩展及完整对应源码。现有 C++ 构建源码与源码树核对一致；原许可证、源码 ZIP 及源文件摘要保留。ABI 为 Torch 2.8.0+cpu / TorchVision 0.23.0+cpu，MSVC 2022 x64。
- Windows .NET Framework C# 编译器。

```powershell
python installer/build.py --output <新输出目录> --python <Python根目录> `
  --detectron <带_C.cp312-win_amd64.pyd的detectron2目录> `
  --detectron-source <完整对应源码目录> --pip-wheel <pip.whl> --pip-sha256 <摘要>
```

Detectron2 重建使用 `installer/rebuild_detectron.py`，在 VS 2022 x64 Native Tools 环境执行，需要完整 Python 3.12 headers/libs 和固定 Torch ABI。输出新目录，不覆盖原始源码。构建器拒绝已有输出与私有输入，完整源码 ZIP 位于程序 third_party_source 下。

## 验证与日志

公开 CI 检查源码、前端和安装引擎的下载接续、校验、来源错误、资料目录保护、Torch 精简与 RECORD。Windows 本机验证见 VALIDATION.md；不把单机结果当跨电脑或专业准确率验收。

安装日志：`%LOCALAPPDATA%\ClimbSetup\<版本>\安装日志.txt`。启动日志：`%LOCALAPPDATA%\AiClimbingCommunitySetup\启动日志.txt`。反馈前先脱敏，不上传照片、视频、密钥或整份资料目录。
