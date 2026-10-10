import io
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile

from installer.prepare_pure_wheels import sha, validate_one


class PureWheelTests(unittest.TestCase):
    def verify(self, replacements=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'demo.tar.gz'
            files = {'demo/module.py': b'value = 1\n', 'bin/run': b'#!python\nprint(1)\n'}
            with tarfile.open(source, 'w:gz') as archive:
                for name, content in files.items():
                    member = tarfile.TarInfo('demo-1/' + name)
                    member.size = len(content)
                    archive.addfile(member, io.BytesIO(content))
            wheel = root / 'demo-1-py3-none-any.whl'
            installed = {'demo/module.py': files['demo/module.py'],
                         'demo-1.data/scripts/run': files['bin/run'].replace(b'\n', b'\r\n'),
                         'demo-1.dist-info/METADATA': b'Name: demo\n'}
            installed.update(replacements or {})
            with zipfile.ZipFile(wheel, 'w') as archive:
                for name, content in installed.items():
                    archive.writestr(name, content)
            pin = dict(source=source.name, source_sha256=sha(source), module_prefix='demo/', scripts=['bin/run'])
            validate_one(root, pin, dict(wheel=wheel.name, wheel_sha256=sha(wheel)))

    def test_original_modules_and_windows_script_line_endings(self):
        self.verify()

    def test_modified_module_rejected_even_with_updated_wheel_checksum(self):
        with self.assertRaisesRegex(RuntimeError, 'code differs'):
            self.verify({'demo/module.py': b'value = 2\n'})

    def test_modified_script_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'scripts differ'):
            self.verify({'demo-1.data/scripts/run': b'#!python\nprint(2)\n'})

    def test_unreviewed_binary_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'Unreviewed file'):
            self.verify({'demo/native.dll': b'binary'})

    def test_traversal_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'archive path'):
            self.verify({'../escape.py': b'pass'})


if __name__ == '__main__':
    unittest.main()
