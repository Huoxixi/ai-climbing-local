"""Start the same local app from source, with a separate community data folder."""
import argparse
import os
from pathlib import Path
import secrets
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', action='store_true', help='Use the system browser instead of a desktop window')
    parser.add_argument('--data-root', type=Path, help='Use a separate data directory')
    parser.add_argument('--headless', action='store_true', help='Start without opening a window')
    parser.add_argument('--port', type=int, default=0, help='0 chooses a free loopback port')
    parser.add_argument('--window-check', type=Path, help='Developer-only native page smoke check and exit')
    args = parser.parse_args()
    if not (ROOT / 'frontend/dist/index.html').is_file():
        raise SystemExit('Run setup.ps1 first: built frontend is missing.')
    from desktop.paths import community_data_root
    default_data = community_data_root(os.environ.get('LOCALAPPDATA', Path.home() / '.local/share'))
    user = (args.data_root or default_data).resolve()
    if user == ROOT or ROOT in user.parents:
        raise SystemExit('User data must be outside the source folder.')
    # Do not inherit credentials, model providers or developer test-media paths.
    for name in list(os.environ):
        if name.startswith(('OPENAI_', 'DASHSCOPE_', 'SUPABASE_', 'REPLAY_', 'CLIMB_REPLAY_', 'PHOTO_ROUTE_', 'VITE_')):
            del os.environ[name]
    os.environ.update({'LOCAL_ONLY':'true','LOCAL_REPLAY_SIMPLE':'1','DISABLE_SUPABASE':'true',
        'PYTHON_DOTENV_DISABLED':'1','APP_ENV':'desktop','MEMBER_ACCOUNTS_ENABLED':'false',
        'PILOT_AUTH_ENABLED':'false','ENABLE_SIMULATION':'false','HF_HUB_OFFLINE':'1',
        'CLIMB_REPLAY_KEEP_HIGH_RESOLUTION':'1','CLIMB_REPLAY_RTMW_DEVICE':'auto',
        'CLIMB_REPLAY_RTMW_MODEL_DIR':str(ROOT / 'backend/model_assets/rtmw-l-384x288'),
        'PHOTO_ROUTE_CLIMBING_MODEL_CONFIG':str(ROOT / 'backend/model_assets/climbing-mask-rcnn-r50-fpn-1200.yaml'),
        'PHOTO_ROUTE_CLIMBING_MODEL_CHECKPOINT':str(ROOT / 'models/verified-model_final.pth'),
        'PHOTO_ROUTE_MOBILESAM_REPO':str(ROOT / 'vendor/MobileSAM'),
        'PHOTO_ROUTE_MOBILESAM_CHECKPOINT':str(ROOT / 'models/mobile_sam.pt')})
    sys.path[:0] = [str(ROOT),str(ROOT / 'backend')]
    from desktop.paths import resolve_paths
    from desktop.storage import apply_pending_change
    paths = apply_pending_change(resolve_paths(install=ROOT, user=user))
    paths.prepare()
    os.environ['PHOTO_ROUTE_DATA_DIR'] = str(paths.data / 'photo_routes')
    if args.port:
        if not 1024 <= args.port <= 65535:
            raise SystemExit('Port must be between 1024 and 65535.')
        port = args.port
    else:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            port = sock.getsockname()[1]
    origin = f'http://127.0.0.1:{port}'
    token = secrets.token_urlsafe(32)
    choose_storage = None
    if not (args.browser or args.headless):
        import webview
        def choose_storage():
            selected = window.create_file_dialog(webview.FOLDER_DIALOG)
            return selected[0] if selected else None
    from desktop.server import create_app
    import uvicorn
    app = create_app(paths, token, origin, choose_storage=choose_storage)
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1',port=port,log_level='warning',access_log=False))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    url = origin + '/desktop/bootstrap/' + token
    try:
        for _ in range(120):
            if not thread.is_alive():
                raise RuntimeError('Local server stopped during startup.')
            try:
                request = urllib.request.Request(origin + '/api/health', headers={'X-Desktop-Token':token})
                with urllib.request.urlopen(request,timeout=.5) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(.25)
        else:
            raise RuntimeError('Local server did not become ready.')
        print(f'App ready on {origin}; data: {paths.data}',flush=True)
        if args.browser:
            webbrowser.open(url)
        if args.browser or args.headless:
            while thread.is_alive():
                thread.join(.5)
        else:
            webview.settings['ALLOW_DOWNLOADS'] = True
            window = webview.create_window('攀岩助手 · 本地抱石',url,width=1280,height=860,min_size=(800,600))
            if args.window_check:
                def check_window():
                    import json
                    try:
                        for _ in range(60):
                            state = window.evaluate_js("JSON.stringify({ready:!!document.querySelector('#app')?.children.length,text:document.body.innerText})")
                            result = json.loads(state)
                            if result['ready'] and '照片' in result['text']:
                                args.window_check.write_text(json.dumps({'ready':True,'local_page':True}),encoding='utf-8')
                                break
                            time.sleep(.5)
                        else:
                            args.window_check.write_text(json.dumps({'ready':False}),encoding='utf-8')
                    finally:
                        window.destroy()
                window.events.loaded += check_window
            webview.start(gui='edgechromium', private_mode=False, storage_path=str(paths.user / 'cache/webview2'))
    except KeyboardInterrupt:
        pass
    finally:
        server.should_exit = True
        thread.join(10)

if __name__ == '__main__':
    main()
