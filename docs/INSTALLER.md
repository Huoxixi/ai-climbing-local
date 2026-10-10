# Windows 安装器实现与重建

普通用户下载 Windows ZIP，解压后按同目录「安装说明.txt」双击安装 EXE。以下用于开发与审查。

## 流程

`WindowsApp.cs` 使用原生窗口，按系统 DPI 排版。首屏显示产品名、用途、空间提示与操作。主按钮右侧突出，停止与取消为左侧灰色次要操作。Python 输出结构化事件，窗口显示当前阶段、耗时、下载量和中文失败处理；停止、取消及失败自动回退本次安装；清理未完成时保留「继续清理」，不显示已清理成功。

资源在 `%LOCALAPPDATA%\ClimbSetup\0.1.16` 展开，逐项校验。独立环境准备在 `%LOCALAPPDATA%\Programs\AiClimb\<版本>.installing`，Windows 依赖版本固定。官方 CPU Torch wheel 校验后在本机剔除编译用静态库及头文件，不再分发这个精简 wheel。用户无需编译器。

模型从作者 Kaggle / OpenMMLab 获取并校验。同一次尝试中的短暂下载中断支持自动接续；最终失败后清理下载文件，下次重新安装。来源限制访问时停止。缺窗口组件时下载微软 WebView2，验证 Authenticode 签名后安装。

完成前实际加载模型、执行合成推理、检查视频组件与应用入口。准备目录改名为最终版本，创建「攀岩助手（公开版）」快捷方式。成功清理全部临时文件。失败、停止或取消结束自身 Windows Job 中的安装子进程后，依据本次 transaction.json 和 .setup-owned.json 归属标记删除环境、模型、新程序目录和缓存；已有安装与个人资料保留。文件被占用时保留归属标记以便继续清理。快捷方式更新前备份，回退时恢复旧链接或删除本次新建链接。个人资料在独立 AiClimbingCommunity，不接触内部 `.local`。原生启动器用当前用户互斥锁避免重复打开；源码直接运行仍应避免多个进程共用资料。

## 构建输入与方法

- 已审查的 Git 源码和 boulder-local 前端构建。
- PSF 许可 CPython 3.12 x64；复制标准库，排除原环境 site-packages。
- 官方 pip 26.2.1 wheel，SHA-256 `71138adf1f4ca900cdb7d289c21b7494329f2332b6d85f0e1c42108c0384ed3e`。
- Detectron2 cp312 CPU 扩展及完整对应源码。现有 C++ 构建源码与源码树核对一致；原许可证、源码 ZIP 及源文件摘要保留。ABI 为 Torch 2.8.0+cpu / TorchVision 0.23.0+cpu，MSVC 2022 x64。
- Windows .NET Framework C# 编译器。
- 三个固定版本纯 Python wheel：antlr4-python3-runtime 4.9.3、fvcore 0.1.5.post20221221、proxy_tools 0.1.0。由原始 PyPI 源码预打包，运行代码逐文件核对一致；ANTLR 的 pygrun 脚本只允许 Windows 换行转换。原始源码压缩包、摘要及上游许可证随 EXE 保留。详见 THIRD_PARTY_NOTICES.md。

先在短路径、带 setuptools 78.1.0 与 wheel 0.45.1 的 Python 环境运行 `python installer/prepare_pure_wheels.py --output <新短目录> --python <python.exe>`。下载源由 pure-wheels.json 固定并校验。构建器再次核对源码、代码、脚本及许可证，拒绝未知文件或修改后的模块。

```powershell
python installer/build.py --output <新输出目录> --python <Python根目录> `
  --detectron <带_C.cp312-win_amd64.pyd的detectron2目录> `
  --detectron-source <完整对应源码目录> --pip-wheel <pip.whl> --pip-sha256 <摘要> `
  --pure-wheels <上述已校验目录>
```

Detectron2 重建使用 `installer/rebuild_detectron.py`，在 VS 2022 x64 Native Tools 环境执行，需要完整 Python 3.12 headers/libs 和固定 Torch ABI。输出新目录，不覆盖原始源码。构建器拒绝已有输出与私有输入，完整源码 ZIP 位于程序 third_party_source 下。

## 验证与日志

公开 CI 检查源码、前端和安装引擎的下载接续、校验、来源错误、资料目录保护、Torch 精简与 RECORD。Windows 本机验证见 VALIDATION.md；不把单机结果当跨电脑或专业准确率验收。

安装期间日志暂存于本次缓存；结束时读入内存并删除缓存，在「查看日志」窗口查看与复制。关闭窗口后不自动留日志文件。启动日志：`%LOCALAPPDATA%\AiClimbingCommunitySetup\启动日志.txt`。反馈前先脱敏，不上传照片、视频、密钥或整份资料目录。

## Windows 路径与进程保护

原生安装器显式向引擎传入 KnownFolder 得到的程序与缓存路径，并固定运行环境的 LOCALAPPDATA，避免继承宿主 MSIX 虚拟目录。缓存版本目录缩短，临时目录使用 t。MSIX 仍可能把临时路径规范化为较长的物理路径，因此全部依赖只允许安装 wheel；三个无官方 wheel 的纯 Python 依赖预先打包，用户本机不再构建源码，无需启用系统长路径策略。后台引擎在命名事件上等待，加入本次 Job 后才获准继续，避免子进程先于隔离启动。停止关闭 Job 中的进程，不按 python 等名称结束其它程序。微软 WebView2 属于共享系统组件，已有组件不卸载；安装器自身下载文件会清理。
