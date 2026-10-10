import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from installer.engine import download, safe_extract, InstallError, install, remaining_space, INSTALL_PEAK_BYTES


class Response(io.BytesIO):
    status = 200
    def __init__(self, body, status=200, headers=None):
        super().__init__(body)
        self.status = status
        self.headers = headers or {'Content-Length':str(len(body))}
    def geturl(self):
        return 'https://official.example/model'


class InstallerTests(unittest.TestCase):
    def test_retry_space_accounts_for_prepared_files_but_not_invalid_downloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload, stage, cache = root/'payload',root/'stage',root/'cache'
            for directory in (payload, stage, cache):
                directory.mkdir()
            initial = remaining_space(payload, stage, cache)
            (stage/'prepared.bin').write_bytes(b'x'*1024)
            (cache/'unknown.zip.invalid').write_bytes(b'x'*2048)
            self.assertEqual(initial, INSTALL_PEAK_BYTES)
            self.assertEqual(remaining_space(payload, stage, cache), initial-1024)

    def test_resume_uses_exact_range_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'model.zip'
            target.with_suffix('.zip.part').write_bytes(b'first')
            response = Response(b'second',206,{'Content-Range':'bytes 5-10/11'})
            with patch('urllib.request.urlopen',return_value=response) as request:
                download('https://official.example/model',target,hashlib.sha256(b'firstsecond').hexdigest())
                self.assertEqual(request.call_args[0][0].get_header('Range'),'bytes=5-')
            self.assertEqual(target.read_bytes(),b'firstsecond')

    def test_server_ignoring_range_restarts_without_appending(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'model.zip'
            target.with_suffix('.zip.part').write_bytes(b'old')
            with patch('urllib.request.urlopen',return_value=Response(b'complete')):
                download('https://official.example/model',target,hashlib.sha256(b'complete').hexdigest())
            self.assertEqual(target.read_bytes(),b'complete')

    def test_wrong_range_does_not_corrupt_partial_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'model.zip'
            partial = target.with_suffix('.zip.part')
            partial.write_bytes(b'first')
            with patch('urllib.request.urlopen',return_value=Response(b'bad',206,{'Content-Range':'bytes 0-2/3'})):
                with self.assertRaises(InstallError):
                    download('https://official.example/model',target)
            self.assertEqual(partial.read_bytes(),b'first')

    def test_checksum_failure_never_publishes_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'model.zip'
            with patch('urllib.request.urlopen',return_value=Response(b'corrupt')):
                with self.assertRaises(InstallError):
                    download('https://official.example/model',target,'0'*64)
            self.assertFalse(target.exists())
            self.assertTrue(target.with_suffix('.zip.part.invalid').exists())

    def test_verified_download_is_reused_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'model.zip'
            target.write_bytes(b'good')
            with patch('urllib.request.urlopen') as request:
                download('https://official.example/model',target,hashlib.sha256(b'good').hexdigest())
                request.assert_not_called()

    def test_source_unavailable_has_chinese_recovery(self):
        from urllib.error import HTTPError
        with tempfile.TemporaryDirectory() as tmp:
            with patch('urllib.request.urlopen',side_effect=HTTPError('https://official.example',403,'forbidden',{},None)):
                with self.assertRaisesRegex(InstallError,'暂时不能访问'):
                    download('https://official.example',Path(tmp) / 'model')

    def test_archive_rejects_escape_and_symlink_before_writing(self):
        for name in ('../outside','/absolute','C:/Windows/outside','nested/../../outside','..\\outside','link'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                archive = Path(tmp) / 'payload.zip'
                with zipfile.ZipFile(archive,'w') as bundle:
                    bundle.writestr('safe','good')
                    item = zipfile.ZipInfo(name)
                    if name == 'link':
                        item.external_attr = (0o120777 << 16)
                    bundle.writestr(item,'bad')
                with self.assertRaises(InstallError):
                    safe_extract(archive,Path(tmp) / 'target')
                self.assertFalse((Path(tmp) / 'target/safe').exists())

    def test_install_rejects_personal_data_directory_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / 'AiClimbingCommunity'
            base.mkdir()
            sentinel = base / 'saved-photo.txt'
            sentinel.write_text('preserve')
            with self.assertRaises(InstallError):
                install(Path(tmp) / 'payload',base,Path(tmp) / 'cache')
            self.assertEqual(sentinel.read_text(),'preserve')
            self.assertEqual(list(base.iterdir()),[sentinel])

    def test_torch_filter_keeps_runtime_and_license_updates_record(self):
        from installer.torch_runtime import filter_wheel
        import csv
        with tempfile.TemporaryDirectory() as tmp:
            source,target = Path(tmp)/'original.whl',Path(tmp)/'runtime.whl'
            names = ['torch/lib/torch_cpu.dll','torch/lib/dnnl.lib','torch/include/header.h','torch-2.8.0.dist-info/licenses/LICENSE']
            with zipfile.ZipFile(source,'w') as bundle:
                for name in names:
                    bundle.writestr(name,'same-content')
                bundle.writestr('torch-2.8.0.dist-info/RECORD',''.join(name+',,12\n' for name in names)+'torch-2.8.0.dist-info/RECORD,,\n')
            filter_wheel(source,target)
            with zipfile.ZipFile(target) as bundle:
                self.assertEqual(bundle.read(names[0]),b'same-content')
                self.assertEqual(bundle.read(names[3]),b'same-content')
                self.assertNotIn(names[1],bundle.namelist())
                self.assertNotIn(names[2],bundle.namelist())
                records = [row[0] for row in csv.reader(io.StringIO(bundle.read('torch-2.8.0.dist-info/RECORD').decode()))]
                self.assertEqual(set(records),set(bundle.namelist()))


if __name__ == '__main__':
    unittest.main()
