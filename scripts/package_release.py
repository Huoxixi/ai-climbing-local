"""Package Git-tracked source and reviewed frontend, without any native runtime."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from desktop.package_scope import assert_local_frontend

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    target = args.output.resolve()
    if target.exists() or target == ROOT or ROOT in target.parents:
        raise RuntimeError('Choose a new package path outside the repository')
    assert_local_frontend(ROOT / 'frontend/dist')
    commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    files=[]
    for path in sorted((ROOT / 'frontend/dist').rglob('*')):
        if not path.is_file():
            continue
        if path.is_symlink() or path.suffix.lower() not in {'.js','.css','.html','.woff2','.svg','.txt','.md'}:
            raise RuntimeError('Unreviewed frontend asset')
        files.append({'path':path.relative_to(ROOT).as_posix(), 'bytes':path.stat().st_size,
                      'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest=json.dumps({'source_commit':commit,'files':files},indent=2)+'\n'
    # A local ignored manifest allows the installer to verify the built UI here too.
    (ROOT / 'frontend-manifest.json').write_text(manifest,encoding='utf-8')
    target.parent.mkdir(parents=True,exist_ok=True)
    prefix='AiClimbing-local/'
    subprocess.run(['git','archive','--format=zip','--prefix='+prefix,'-o',str(target),'HEAD'],cwd=ROOT,check=True)
    with zipfile.ZipFile(target,'a',compression=zipfile.ZIP_DEFLATED) as bundle:
        for item in files:
            bundle.write(ROOT / item['path'],prefix+item['path'])
        bundle.writestr(prefix+'frontend-manifest.json',manifest)
        for name in bundle.namelist():
            parts=set(Path(name).parts)
            if parts & {'.local','.private','.venv','node_modules','data'}:
                raise RuntimeError('Private or runtime files in package')
            if Path(name).suffix.lower() in {'.pth','.onnx','.exe','.dll','.pyd','.sqlite3','.mp4','.mov','.jpg','.png'}:
                raise RuntimeError('Forbidden package asset')
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix('.zip.sha256').write_text(digest+'  '+target.name+'\n',encoding='utf-8')
    print(json.dumps({'package':str(target),'sha256':digest,'source_commit':commit,'frontend_files':len(files)}))

if __name__=='__main__':
    main()
