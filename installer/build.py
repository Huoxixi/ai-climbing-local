"""Build the online setup EXE from reviewed source, PSF Python and Apache Detectron2.

Model weights and pip-installed dependencies are deliberately not bundled.
Every native Detectron2 build must provide its exact corresponding source tree.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from desktop.package_scope import assert_local_frontend
from installer.engine import VERSION, sha


def copy_tree(source, destination, skip):
    for path in sorted(Path(source).rglob('*')):
        relative = path.relative_to(source)
        if any(part in skip for part in relative.parts) or path.suffix in {'.pyc','.pyo'}:
            continue
        if path.is_symlink():
            raise RuntimeError('Symlinks are not accepted: '+str(relative))
        if path.is_file():
            target = destination / relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,target)


def build(args):
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError('Choose a new build output; existing files are preserved')
    for path in (args.python, args.detectron, args.detectron_source):
        if {p.lower() for p in path.parts} & {'.local','.private'}:
            raise RuntimeError('Private inputs are forbidden')
    assert_local_frontend(ROOT / 'frontend/dist')
    output.mkdir(parents=True)
    payload = output / 'payload'
    payload.mkdir()
    tracked = subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    for name in tracked:
        if not name:
            continue
        source = ROOT / name
        if source.is_symlink() or not source.is_file() or set(source.relative_to(ROOT).parts) & {'.local','.private','.venv','data','node_modules'}:
            raise RuntimeError('Unreviewed source input: '+name)
        if source.suffix.lower() in {'.exe','.pyd','.dll','.pth','.onnx','.sqlite3','.jpg','.png','.mp4'}:
            raise RuntimeError('Binary/model/media in tracked source: '+name)
        target = payload / name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
    copy_tree(ROOT / 'frontend/dist',payload / 'frontend/dist',set())
    runtime = payload / 'runtime'
    runtime.mkdir()
    for name in ('python.exe','pythonw.exe','python3.dll','python312.dll','vcruntime140.dll','vcruntime140_1.dll','LICENSE.txt'):
        shutil.copy2(args.python / name,runtime / name)
    copy_tree(args.python / 'DLLs',runtime / 'DLLs',{'__pycache__'})
    copy_tree(args.python / 'Lib',runtime / 'Lib',{'site-packages','__pycache__','test','tests','ensurepip','idlelib','venv'})
    (runtime / 'python312._pth').write_text('DLLs\nLib\nLib/site-packages\n..\n../backend\nimport site\n',encoding='utf-8')
    site = runtime / 'Lib/site-packages'
    site.mkdir()
    if sha(args.pip_wheel) != args.pip_sha256:
        raise RuntimeError('pip wheel digest mismatch')
    with zipfile.ZipFile(args.pip_wheel) as wheel:
        wheel.extractall(site)  # Build input is a fixed, hash-verified PyPI wheel.
    native = args.detectron / '_C.cp312-win_amd64.pyd'
    if not native.is_file() or not (args.detectron_source / 'setup.py').is_file() or not (args.detectron_source / 'detectron2/layers/csrc/vision.cpp').is_file():
        raise RuntimeError('Native extension requires complete corresponding source')
    copy_tree(args.detectron,site / 'detectron2',{'__pycache__','configs'})
    source = output / 'detectron2-source'
    copy_tree(args.detectron_source,source,{'.git','__pycache__','build','.local','.private','.venv','node_modules'})
    shutil.copy2(args.detectron_source / 'LICENSE',site / 'detectron2/LICENSE')
    # Capture native build inputs alongside source, license and rebuild directions.
    provenance = {'version':'0.6+a2f4a877/windows-cp312-cpu','extension_sha256':sha(native),
        'abi':{'python':'3.12-x64','torch':'2.8.0+cpu','torchvision':'0.23.0+cpu'},
        'source_files':[{'path':p.relative_to(source).as_posix(),'sha256':sha(p)} for p in sorted(source.rglob('*')) if p.is_file()]}
    third_party = payload / 'third_party_source'
    third_party.mkdir()
    # Keep the complete source as an archive to avoid legacy Windows MAX_PATH.
    with zipfile.ZipFile(third_party / 'detectron2-source.zip','w',compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(source.rglob('*')):
            if path.is_file() and path.suffix.lower() not in {'.pyd','.dll','.exe','.lib','.obj'}:
                bundle.write(path,'detectron2/'+path.relative_to(source).as_posix())
    (third_party / 'detectron2-build.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    compiler = Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
    flags = ['/nologo','/target:winexe','/platform:x64','/reference:System.Windows.Forms.dll',
             '/reference:System.Drawing.dll','/reference:System.Web.Extensions.dll',
             '/reference:System.IO.Compression.dll','/win32manifest:'+str(ROOT / 'installer/windows.manifest')]
    subprocess.run([str(compiler),*flags,'/define:LAUNCHER','/out:'+str(payload / 'AiClimbing.exe'),str(ROOT / 'installer/WindowsApp.cs')],check=True)
    manifest = {'version':VERSION,'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                'files':[{'path':p.relative_to(payload).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
                         for p in sorted(payload.rglob('*')) if p.is_file()]}
    (payload / 'payload-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    archive = output / 'payload.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
        for path in sorted(payload.rglob('*')):
            if path.is_file():
                bundle.write(path,path.relative_to(payload).as_posix())
    executable = output / ('AiClimbing-Setup-'+VERSION+'.exe')
    subprocess.run([str(compiler),*flags,'/resource:'+str(archive)+',payload.zip','/out:'+str(executable),str(ROOT / 'installer/WindowsApp.cs')],check=True)
    executable.with_suffix('.exe.sha256').write_text(sha(executable)+'  '+executable.name+'\n',encoding='utf-8')
    print(json.dumps({'installer':str(executable),'bytes':executable.stat().st_size,'sha256':sha(executable),'payload_files':len(manifest['files'])}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--python',type=Path,required=True,help='PSF-licensed app-local CPython 3.12 x64 tree')
    parser.add_argument('--detectron',type=Path,required=True,help='Detectron2 package with compiled CPU extension')
    parser.add_argument('--detectron-source',type=Path,required=True,help='Exact corresponding full source')
    parser.add_argument('--pip-wheel',type=Path,required=True)
    parser.add_argument('--pip-sha256',required=True)
    build(parser.parse_args())
