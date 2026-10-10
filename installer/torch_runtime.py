"""Prepare official CPU wheel locally, omitting static libraries/headers.

No modified wheel is redistributed. Kept files and all licenses are unchanged;
RECORD is updated to describe omitted development files. The compiled Detectron2
extension only needs Torch DLLs, which are retained.
"""
import csv
from html.parser import HTMLParser
import io
import json
from pathlib import Path
from urllib.parse import unquote, urlparse, urldefrag
import urllib.request
import zipfile

FILENAME = 'torch-2.8.0+cpu-cp312-cp312-win_amd64.whl'
URL = 'https://download-r2.pytorch.org/whl/cpu/torch-2.8.0%2Bcpu-cp312-cp312-win_amd64.whl'
SHA256 = '2be20b2c05a0cce10430cc25f32b689259640d273232b2de357c35729132256d'


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.extend(value for key,value in attrs if key == 'href')


def source():
    with urllib.request.urlopen('https://download.pytorch.org/whl/cpu/torch/',timeout=60) as response:
        page = response.read().decode('utf-8')
    links = Links(); links.feed(page)
    candidates = [link for link in links.links if Path(unquote(urlparse(link).path)).name == FILENAME]
    if len(candidates) != 1:
        raise RuntimeError('Official CPU wheel metadata changed')
    url, fragment = urldefrag(candidates[0])
    if urlparse(url).hostname not in {'download.pytorch.org','download-r2.pytorch.org'} or not url.startswith('https://') or not fragment.startswith('sha256=') or len(fragment) != 71:
        raise RuntimeError('CPU wheel source/hash missing')
    return url,fragment[7:]


def keep(name):
    return not (name.startswith('torch/include/') or name.endswith('.lib'))


def filter_wheel(original, target):
    target = Path(target)
    partial = target.with_suffix('.part')
    removed = 0
    with zipfile.ZipFile(original) as src, zipfile.ZipFile(partial,'w',compression=zipfile.ZIP_DEFLATED) as dst:
        records = [name for name in src.namelist() if name.endswith('.dist-info/RECORD')]
        if len(records) != 1:
            raise RuntimeError('Wheel RECORD missing')
        record = records[0]
        for item in src.infolist():
            if not keep(item.filename):
                removed += item.file_size
                continue
            if item.filename == record:
                continue
            with src.open(item) as input, dst.open(item,'w') as output:
                import shutil
                shutil.copyfileobj(input,output,1024*1024)
        rows = list(csv.reader(io.StringIO(src.read(record).decode('utf-8'))))
        text = io.StringIO(newline='')
        csv.writer(text,lineterminator='\n').writerows(row for row in rows if keep(row[0]))
        dst.writestr(record,text.getvalue())
    partial.replace(target)
    return removed


def prepare(cache, download, sha, report=None):
    cache = Path(cache) / 'torch-runtime'
    cache.mkdir(parents=True,exist_ok=True)
    url,digest = URL,SHA256
    target, stamp = cache / FILENAME, cache / 'prepared.json'
    if target.is_file() and stamp.is_file():
        previous = json.loads(stamp.read_text('utf-8'))
        if previous.get('source') == digest and previous.get('runtime') == sha(target):
            return target
    original = download(url,cache / ('original-'+FILENAME),digest,report=report)
    removed = filter_wheel(original,target)
    stamp.write_text(json.dumps({'source':digest,'runtime':sha(target),'omitted_bytes':removed}),encoding='utf-8')
    original.unlink()  # Only this validated installer cache file; never user data.
    return target


if __name__ == '__main__':
    print(json.dumps(source()))
