"""Check tracked source only; private directories must never enter the release."""
import ast
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from desktop.package_scope import assert_local_frontend

def main():
    result = subprocess.run(['git','ls-files','-z'],cwd=ROOT,check=True,capture_output=True)
    files = [ROOT / item for item in result.stdout.decode().split('\0') if item]
    if not files:
        raise RuntimeError('Stage reviewed files before running the public source audit')
    for path in files:
        parts = set(path.relative_to(ROOT).parts)
        if parts & {'.local','.private','node_modules','.venv','data','__pycache__'}:
            raise RuntimeError('Forbidden directory in release: ' + str(path.relative_to(ROOT)))
        if path.suffix.lower() in {'.pth','.onnx','.exe','.dll','.pyd','.sqlite3','.mp4','.mov','.jpg','.png'}:
            raise RuntimeError('Unreviewed runtime, model, photo or user asset')
        if path.name.startswith('.env') and path.name != '.env.boulder-local':
            raise RuntimeError('Environment file in release')
        if path.suffix == '.py':
            ast.parse(path.read_text('utf-8-sig'), filename=str(path.relative_to(ROOT)))
    assert_local_frontend(ROOT / 'frontend/dist')
    print(f'Public scope audit passed: {len(files)} tracked sources/assets; local frontend verified.')

if __name__ == '__main__':
    main()
