"""Isolated, resumable installation engine. Only writes program/setup folders."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile

VERSION = '0.1.15-setup.20261010'
# Rounded above the measured peak including the extracted setup payload. GiB,
# matching the values Windows commonly labels GB; see docs/VALIDATION.md.
INSTALL_PEAK_BYTES = int(2.5 * 1024**3)
HOLD_URL = ('https://www.kaggle.com/api/v1/datasets/download/tomasslama/'
            'indoor-climbing-gym-hold-segmentation/model%2Fmodel_final.pth?datasetVersionNumber=4')
HOLD_SHA = '995960a74819e21bd66d7be56ae6e1c8124ec0a06fece4fae13812887d86ebea'
HOLD_ARCHIVE_SHA = '85a80cd02119d154b1e27f047d327beebfaffe7f99e4d24a117f11040d79aedf'
WEBVIEW_URL = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703'


class InstallError(Exception):
    pass


def event(progress, title, detail='', **extra):
    print(json.dumps(dict(progress=progress, title=title, detail=detail, **extra), ensure_ascii=False), flush=True)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_extract(bundle, destination):
    destination = Path(destination).resolve()
    with zipfile.ZipFile(bundle) as archive:
        for item in archive.infolist():
            name = item.filename.replace('\\', '/')
            target = (destination / name).resolve()
            if (name.startswith('/') or ':' in name or '..' in Path(name).parts
                    or not target.is_relative_to(destination)
                    or (item.external_attr >> 16) & 0o170000 == 0o120000):
                raise InstallError('安装资源包含不安全路径，请重新下载官方安装包。')
        archive.extractall(destination)


def download(url, target, digest=None, report=None, attempts=3):
    """Resume partial HTTPS downloads; verify before making a cache entry visible."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and (not digest or sha(target) == digest):
        return target
    partial = target.with_suffix(target.suffix + '.part')
    if target.exists():
        target.replace(target.with_suffix(target.suffix + '.invalid'))
    last = None
    for attempt in range(attempts):
        try:
            offset = partial.stat().st_size if partial.exists() else 0
            headers = {'User-Agent': 'AiClimbingCommunitySetup/0.1.15', 'Accept-Encoding': 'identity'}
            if offset:
                headers['Range'] = f'bytes={offset}-'
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as response:
                if not response.geturl().startswith('https://'):
                    raise InstallError('下载源未使用安全连接，已停止。')
                if response.status == 206:
                    match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('Content-Range', ''))
                    if not match or int(match[1]) != offset:
                        raise InstallError('下载服务器返回了不一致的文件范围，请重试。')
                    total = int(match[3])
                    mode = 'ab'
                else:
                    offset, mode = 0, 'wb'
                    total = int(response.headers.get('Content-Length', 0))
                received, previous = offset, 0
                with partial.open(mode) as out:
                    while block := response.read(1024 * 1024):
                        out.write(block)
                        received += len(block)
                        if report and time.monotonic() - previous > .6:
                            report(received, total)
                            previous = time.monotonic()
                if total and received != total:
                    raise OSError('下载未完成')
            if digest and sha(partial) != digest:
                partial.replace(partial.with_suffix(partial.suffix + '.invalid'))
                raise InstallError('下载文件校验不通过，已隔离损坏文件；点击重试重新下载。')
            partial.replace(target)
            return target
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code == 416 and partial.exists():
                partial.replace(partial.with_suffix(partial.suffix + '.invalid'))
            if exc.code in (401, 403, 404):
                raise InstallError('模型来源暂时不能访问（可能需要登录或链接已变更）。请稍后重试；仍失败时在项目 Issues 提交安装日志。') from None
        except (OSError, urllib.error.URLError) as exc:
            last = exc
        if attempt + 1 < attempts:
            time.sleep(2)
    raise InstallError('下载连接中断或超时。请检查网络后点击重试；已下载部分会尽量接续。') from last


def clean_environment():
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(('PYTHON', 'PIP_', 'VIRTUAL_ENV', 'OPENAI_', 'DASHSCOPE_')):
            env.pop(key, None)
    env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PIP_DISABLE_PIP_VERSION_CHECK='1')
    return env


def command(argv, cwd, log, error, timeout=1800):
    with log.open('a', encoding='utf-8') as stream:
        env = clean_environment()
        temporary = log.parent / 'temporary'
        temporary.mkdir(exist_ok=True)
        env.update(TEMP=str(temporary), TMP=str(temporary))
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=stream,
                                   stderr=subprocess.STDOUT, creationflags=0x08000000 if os.name == 'nt' else 0)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise InstallError(error + '（等待超时）') from None
    if code:
        raise InstallError(error)


def webview_present():
    import winreg
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for prefix in ('SOFTWARE\\Microsoft', 'SOFTWARE\\WOW6432Node\\Microsoft'):
            try:
                with winreg.OpenKey(hive, prefix + '\\EdgeUpdate\\Clients\\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}') as key:
                    if winreg.QueryValueEx(key, 'pv')[0] not in ('', '0.0.0.0'):
                        return True
            except OSError:
                pass
    return False


def ensure_webview(cache, log):
    if webview_present():
        return
    event(14, '准备桌面窗口', '正在从微软下载窗口组件，无需手动配置。')
    installer = download(WEBVIEW_URL, cache / 'MicrosoftEdgeWebview2Setup.exe')
    # HTTPS alone is insufficient for executing a downloaded installer.
    command(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
             '-File', str(Path(__file__).parent / 'verify_microsoft.ps1'), '-Installer', str(installer)],
            cache, log, '微软窗口组件的数字签名校验失败。请重新下载官方安装包后重试。', 60)
    command([str(installer), '/silent', '/install'], cache, log,
            '桌面窗口组件安装失败。请在微软官网安装 WebView2 Evergreen Runtime 后重试。', 600)
    if not webview_present():
        raise InstallError('窗口组件尚未就绪。请重启电脑后重试，或从微软官网安装 WebView2 Evergreen Runtime。')


def shortcuts(target, log):
    # COM calls are in a fixed script; user/program paths are arguments, never code.
    command(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
             '-File', str(target / 'installer/shortcuts.ps1'), '-App', str(target / 'AiClimbing.exe'),
             '-Directory', str(target)], target, log,
            '程序已安装，但快捷方式创建失败。可直接打开安装目录中的 AiClimbing.exe。', 60)


def check_models(app, log):
    command([str(app / 'runtime/python.exe'), str(app / 'installer/verify_install.py')], app, log,
            '识别组件检查未通过。请点击重试；仍失败时通过项目 Issues 提交安装日志。', 600)


def clean_download_cache(cache):
    cache = Path(cache).resolve()
    for name in ('packages','torch-runtime','temporary'):
        directory = cache / name
        if directory.exists() and directory.resolve().is_relative_to(cache) and not directory.is_symlink():
            shutil.rmtree(directory,ignore_errors=True)
    for name in ('holds-v4.zip','rtmw-l-384x288.zip','yolox-s.zip','MicrosoftEdgeWebview2Setup.exe'):
        path = cache / name
        if path.is_file() and path.resolve().is_relative_to(cache):
            path.unlink(missing_ok=True)


def remaining_space(payload, staging, cache):
    """Account for this version's prepared files so retries don't need 2.5 GiB again."""
    def size(directory):
        if not directory.is_dir():
            return 0
        return sum(p.stat().st_size for p in directory.rglob('*')
                   if p.is_file() and not p.is_symlink())
    prepared = size(payload) + min(size(staging), int(1.6 * 1024**3))
    # Only named reusable downloads, never corrupt/unknown files or user data.
    reusable = size(cache / 'packages') + size(cache / 'torch-runtime')
    digests = {'holds-v4.zip':HOLD_ARCHIVE_SHA}
    from backend.scripts.install_replay_rtmw import ASSETS
    digests.update({archive:digest for _,archive,_,digest in ASSETS})
    for name,digest in digests.items():
        path = cache / name
        if path.is_file() and sha(path) == digest:
            reusable += path.stat().st_size
    prepared += min(reusable, int(.8 * 1024**3))
    return max(128 * 1024**2, INSTALL_PEAK_BYTES - prepared)


def install(payload, base, cache, make_shortcuts=True, webview=True):
    payload, base, cache = Path(payload).resolve(), Path(base).resolve(), Path(cache).resolve()
    # Developer/test override is explicit; never allow an installation into a data directory.
    protected = {'aiclimbingcommunity', 'aiclimbing', '.local', '.private'}
    if any(p.casefold() in protected for p in (*base.parts,*cache.parts)) or base == payload or base.is_relative_to(payload):
        raise InstallError('程序安装位置不能是个人资料目录，请使用默认安装位置。')
    base.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    log = cache / '安装日志.txt'
    # One writer prevents simultaneous retry/install corrupting the same version.
    lock = (cache / 'install.lock').open('a+b')
    lock.write(b'0'); lock.flush(); lock.seek(0)
    import msvcrt
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        lock.close()
        raise InstallError('另一个安装窗口正在工作，请等待它结束后再试。') from None
    try:
        target, staging = base / VERSION, base / (VERSION + '.installing')
        manifest_path = payload / 'payload-manifest.json'
        manifest_digest = sha(manifest_path)
        if target.exists():
            if not (target / 'installation.json').is_file() or json.loads((target / 'installation.json').read_text('utf-8')).get('payload') != manifest_digest:
                raise InstallError('同版本程序目录已存在但不完整。请将它另存后重试；个人资料不需要移动。')
            check_models(target, log)
            if make_shortcuts:
                shortcuts(target, log)
            clean_download_cache(cache)
            event(100, '已经安装完成', '可从桌面打开「攀岩助手（公开版）」。', done=True, app=str(target / 'AiClimbing.exe'))
            return target
        event(3, '检查电脑和安装资源', '首次需要联网 · 安装约需 2.5 GB，完成后约 1.6 GB。')
        if sys.maxsize < 2**32 or sys.version_info[:2] != (3, 12):
            raise InstallError('此安装包适用于 Windows 10/11 64 位系统。')
        required = remaining_space(payload, staging, cache)
        if shutil.disk_usage(base).free < required:
            raise InstallError(f'安装还需约 {required/1024**3:.1f} GB 可用空间。请清理磁盘空间后重试；个人资料不需要删除。')
        manifest = json.loads(manifest_path.read_text('utf-8'))
        for item in manifest['files']:
            source = (payload / item['path']).resolve()
            if not source.is_relative_to(payload) or not source.is_file() or sha(source) != item['sha256']:
                raise InstallError('安装包资源校验失败。请重新下载官方安装包。')
        staging.mkdir(exist_ok=True)
        # Copy only public build-manifest entries; retries never copy user data.
        for item in manifest['files']:
            source, destination = payload / item['path'], staging / item['path']
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                with source.open('rb') as src, destination.open('wb') as dst:
                    shutil.copyfileobj(src, dst)
            elif sha(destination) != item['sha256']:
                # Only immutable payload files (never user data) may be repaired.
                with source.open('rb') as src, destination.open('wb') as dst:
                    shutil.copyfileobj(src, dst)
        python = staging / 'runtime/python.exe'
        if webview:
            ensure_webview(cache, log)
        event(20, '准备运行环境（2/5）', '正在准备运行组件，请稍候。')
        env_cache = cache / 'packages'
        command([str(python), '-m', 'pip', '--isolated', 'install', '--disable-pip-version-check',
                 '--cache-dir', str(env_cache), '--retries', '3', '--timeout', '60',
                 '-c', str(staging / 'installer/dependencies-win.txt'),
                 'setuptools==78.1.0', 'wheel==0.45.1'], staging, log,
                '运行环境准备失败。请检查网络后重试；需要能访问 PyPI。')
        from installer.torch_runtime import prepare
        wheel = prepare(cache,download,sha,report=lambda received,total:
                        event(22,'准备运行环境（2/5）',f'已下载 {received/1024**2:.0f} MB'+(f' / {total/1024**2:.0f} MB' if total else '')))
        event(30,'准备运行环境（2/5）','正在安装识别组件。')
        command([str(python), '-m', 'pip', '--isolated', 'install', '--no-deps', '--no-cache-dir',
                 '--disable-pip-version-check', str(wheel)], staging, log,
                '识别组件安装失败。请检查磁盘空间后重试。')
        command([str(python), '-m', 'pip', '--isolated', 'install', '--disable-pip-version-check',
                 '--no-warn-script-location', '--no-build-isolation', '--cache-dir', str(env_cache), '--retries', '3', '--timeout', '60',
                 '-c', str(staging / 'installer/dependencies-win.txt'),
                 '-r', str(staging / 'backend/requirements-local.txt'), '-r', str(staging / 'backend/requirements-holds.txt')],
                staging, log, '运行组件安装失败。请检查网络、磁盘空间后重试；若网络限制访问 PyPI 或 PyTorch，请更换可访问的网络。')
        event(50, '准备岩点识别模型（3/5）', '正在下载岩点识别模型。')
        def hold_progress(received, total):
            fraction = received / total if total else 0
            event(50 + min(20, int(20*fraction)), '准备岩点识别模型（3/5）',
                  f'已下载 {received/1024**2:.0f} MB' + (f' / {total/1024**2:.0f} MB' if total else ''))
        archive = download(HOLD_URL, cache / 'holds-v4.zip', HOLD_ARCHIVE_SHA, report=hold_progress)
        model = staging / 'models/verified-model_final.pth'
        model.parent.mkdir(exist_ok=True)
        if not model.is_file() or sha(model) != HOLD_SHA:
            with zipfile.ZipFile(archive) as bundle:
                candidates = [name for name in bundle.namelist() if Path(name).name == 'model_final.pth']
                if len(candidates) != 1:
                    raise InstallError('模型下载内容发生变化，请通过项目 Issues 反馈；已停止安装。')
                partial = model.with_suffix('.part')
                with bundle.open(candidates[0]) as src, partial.open('wb') as dst:
                    shutil.copyfileobj(src, dst)
            if sha(partial) != HOLD_SHA:
                # Discard only the installer's cache, so retry actually re-fetches.
                archive.replace(archive.with_suffix('.zip.invalid'))
                raise InstallError('岩点模型校验失败，请点击重试重新下载。')
            partial.replace(model)
        event(72, '准备骨架识别模型（4/5）', '正在下载并校验骨架模型。')
        from backend.scripts.install_replay_rtmw import ASSETS
        for index, (name, archive_name, url, digest) in enumerate(ASSETS):
            download(url, cache / archive_name, digest,
                     lambda received,total: event(72+index*5, '准备骨架识别模型（4/5）',
                         f'已下载 {received/1024**2:.0f} MB' + (f' / {total/1024**2:.0f} MB' if total else '')))
        command([str(python), str(staging / 'backend/scripts/install_replay_rtmw.py'), '--cache', str(cache)],
                staging, log, '骨架模型检查失败。请检查网络并重试；安装日志中保留具体原因。', 300)
        event(88, '检查并完成安装（5/5）', '正在检查识别和视频组件。')
        check_models(staging, log)
        (staging / 'installation.json').write_text(json.dumps({'version':VERSION, 'payload':manifest_digest}), encoding='utf-8')
        import gc
        gc.collect()
        for retry in range(10):
            try:
                staging.rename(target)
                break
            except PermissionError:
                if retry == 9:
                    raise InstallError('程序文件仍被占用，请关闭攀岩助手后重试；个人资料不需要删除。') from None
                time.sleep(.5)
        if make_shortcuts:
            shortcuts(target, log)
        clean_download_cache(cache)
        event(100, '安装完成', '可从桌面打开「攀岩助手（公开版）」。以后使用不需要重新下载。', done=True, app=str(target / 'AiClimbing.exe'))
        return target
    finally:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        lock.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--base', type=Path, default=Path(os.environ['LOCALAPPDATA']) / 'Programs/AiClimb')
    parser.add_argument('--cache', type=Path, default=Path(os.environ['LOCALAPPDATA']) / 'ClimbSetup' / VERSION)
    parser.add_argument('--no-shortcuts', action='store_true')
    parser.add_argument('--skip-webview', action='store_true', help='Developer verification only')
    args = parser.parse_args()
    try:
        install(args.payload,args.base,args.cache,not args.no_shortcuts,not args.skip_webview)
    except Exception as exc:
        detail = str(exc) if isinstance(exc, InstallError) else '安装未完成。请点击重试；仍失败时请在项目 Issues 提交安装日志。'
        args.cache.mkdir(parents=True,exist_ok=True)
        with (args.cache / '安装日志.txt').open('a',encoding='utf-8') as log:
            import traceback
            traceback.print_exc(file=log)
        event(0, '安装未完成', detail, error=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
