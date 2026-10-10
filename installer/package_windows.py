"""Wrap the reviewed setup EXE with a short Chinese guide for ordinary users."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installer', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    installer, output = args.installer.resolve(), args.output.resolve()
    if output.exists() or output == ROOT or ROOT in output.parents:
        raise RuntimeError('Choose a new output outside the source repository')
    if not installer.is_file() or installer.suffix != '.exe':
        raise RuntimeError('A built Windows setup EXE is required')
    if any(p.casefold() in {'.local', '.private'} for p in installer.parts):
        raise RuntimeError('Private inputs are forbidden')
    with installer.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if installer.with_suffix('.exe.sha256').read_text('utf-8').split()[0] != digest:
        raise RuntimeError('Setup EXE checksum does not match')
    manifest = json.loads((installer.parent / 'payload/payload-manifest.json').read_text('utf-8'))
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if manifest['source_commit'] != commit:
        raise RuntimeError('Rebuild the EXE from the current reviewed source commit')
    output.parent.mkdir(parents=True, exist_ok=True)
    # No confusing source tree or runtime folders at the user's extraction root.
    with zipfile.ZipFile(output, 'w') as archive:
        guide = (ROOT / 'installer/安装说明.txt').read_text('utf-8')
        archive.writestr('安装说明.txt', guide.encode('utf-8-sig'), compress_type=zipfile.ZIP_DEFLATED)
        archive.write(installer, '安装攀岩助手.exe', compress_type=zipfile.ZIP_STORED)
    with output.open('rb') as stream:
        archive_digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    output.with_suffix('.zip.sha256').write_text(archive_digest+'  '+output.name+'\n', encoding='utf-8')
    print(json.dumps({'package': str(output), 'bytes': output.stat().st_size,
                      'sha256': archive_digest, 'source_commit': commit}, ensure_ascii=False))


if __name__ == '__main__':
    main()
