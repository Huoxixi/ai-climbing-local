"""Prepare three unmodified pure-Python dependencies before building the EXE."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_one(directory, pin, entry):
    source, wheel = directory / pin['source'], directory / entry['wheel']
    if Path(entry['wheel']).name != entry['wheel'] or not wheel.name.endswith('-py3-none-any.whl'):
        raise RuntimeError('Only reviewed pure Python wheels are accepted')
    if sha(source) != pin['source_sha256'] or sha(wheel) != entry['wheel_sha256']:
        raise RuntimeError('Dependency checksum mismatch')
    expected = {}
    scripts = {}
    with tarfile.open(source) as archive:
        for member in archive.getmembers():
            relative = '/'.join(member.name.split('/')[1:])
            if relative.startswith('src/'):
                relative = relative[4:]
            if member.isfile() and relative.startswith(pin['module_prefix']) and relative.endswith('.py'):
                expected[relative] = hashlib.sha256(archive.extractfile(member).read()).hexdigest()
            if member.isfile() and relative in pin.get('scripts', []):
                scripts[relative.split('/')[-1]] = archive.extractfile(member).read().replace(b'\r\n', b'\n')
    if not expected:
        raise RuntimeError('Dependency source has no reviewed modules')
    actual = {}
    actual_scripts = {}
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            if name.endswith('/'):
                continue
            if '\\' in name or '..' in name.split('/') or ':' in name or name.startswith('/'):
                raise RuntimeError('Unexpected dependency archive path')
            if '.dist-info/' in name:
                continue
            parts = name.split('/')
            if len(parts) == 3 and parts[0].endswith('.data') and parts[1] == 'scripts' and parts[2] in scripts:
                actual_scripts[parts[2]] = archive.read(name).replace(b'\r\n', b'\n')
                continue
            if name not in expected:
                raise RuntimeError('Unreviewed file in dependency wheel: '+name)
            actual[name] = hashlib.sha256(archive.read(name)).hexdigest()
    if actual != expected:
        raise RuntimeError('Dependency code differs from the original PyPI source')
    if actual_scripts != scripts or len(scripts) != len(pin.get('scripts', [])):
        raise RuntimeError('Dependency scripts differ from the original PyPI source')


def validate(directory):
    directory = Path(directory).resolve()
    pins = json.loads((ROOT / 'installer/pure-wheels.json').read_text('utf-8'))
    entries = json.loads((directory / 'manifest.json').read_text('utf-8'))
    if {e['name'] for e in entries} != {p['name'] for p in pins} or len(entries) != len(pins):
        raise RuntimeError('Unexpected dependency manifest')
    for pin in pins:
        entry = next(e for e in entries if e['name'] == pin['name'])
        if entry['version'] != pin['version']:
            raise RuntimeError('Dependency version differs from reviewed pins')
        validate_one(directory, pin, entry)
        if sha(ROOT / 'installer/third_party_licenses' / pin['license_file']) != pin['license_sha256']:
            raise RuntimeError('Dependency license checksum mismatch')
    return pins, entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--python', type=Path, default=Path(sys.executable),
                        help='Python with setuptools 78.1.0 and wheel 0.45.1')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output == ROOT or ROOT in output.parents:
        raise RuntimeError('Choose a new short output path outside the source repository')
    output.mkdir(parents=True)
    pins = json.loads((ROOT / 'installer/pure-wheels.json').read_text('utf-8'))
    for pin in pins:
        if not pin['url'].startswith('https://files.pythonhosted.org/'):
            raise RuntimeError('Unexpected dependency source')
        with urllib.request.urlopen(pin['url'], timeout=60) as response, (output / pin['source']).open('wb') as out:
            import shutil
            shutil.copyfileobj(response, out)
        if sha(output / pin['source']) != pin['source_sha256']:
            raise RuntimeError('Original PyPI source checksum mismatch')
    temporary = output / 't'
    temporary.mkdir()
    env = os.environ.copy()
    env.update(TEMP=str(temporary), TMP=str(temporary), PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    subprocess.run([str(args.python), '-m', 'pip', '--isolated', 'wheel', '--no-deps',
                    '--no-build-isolation', '--no-cache-dir', '--wheel-dir', str(output),
                    *[str(output / pin['source']) for pin in pins]], env=env, check=True)
    entries = []
    for pin in pins:
        wheels = list(output.glob(pin['name'].replace('-', '_')+'-'+pin['version']+'-*.whl'))
        if len(wheels) != 1:
            raise RuntimeError('Unexpected wheel output')
        entries.append(dict(name=pin['name'], version=pin['version'], wheel=wheels[0].name,
                            wheel_sha256=sha(wheels[0])))
    (output / 'manifest.json').write_text(json.dumps(entries, indent=2)+'\n', encoding='utf-8')
    validate(output)
    print('Three pure Python wheels verified against original source; licenses retained.')


if __name__ == '__main__':
    main()
