"""
Testing `uptpy`.
What to test:
* delete files that are already deleted.
* create folders in sub-folders (making dir tree needs to work)
* simple file change
* add and delete files
* delete directory tree
* nothing-to-to
* ignoring uptpy-unknown remote files
* special characters in file and dir names
"""

import json
import os
import posixpath
import shutil
import subprocess
import sys
import unittest
import uuid

THIS_DIR = os.path.abspath(os.path.dirname(__file__))
TEST_DIR = os.path.join(THIS_DIR, 'local')
CREDENTIALS_NAME = '_ test_credentials.json'
CREDENTIALS_FILE = os.path.join(THIS_DIR, CREDENTIALS_NAME)
ERR_NEED_CREDENTIALS = f'Need credentials in file {CREDENTIALS_FILE} to perform tests!'
DATA_JSON = 'data.json'


if __name__ == '__main__':
    parent_path = os.path.dirname(THIS_DIR)
    if parent_path not in sys.path:
        sys.path.append(parent_path)
import uptpy


class Test(unittest.TestCase):
    def __init__(self, args):
        super().__init__(args)
        if not os.path.isfile(CREDENTIALS_FILE):
            self.skipTest(ERR_NEED_CREDENTIALS)
            return

        try:
            with open(CREDENTIALS_FILE, encoding='utf8') as file_obj:
                self.credentials = json.load(file_obj)
        except json.JSONDecodeError as error:
            raise RuntimeError(
                f'Could not load test credentials from "{CREDENTIALS_NAME}"!\n {error}'
            )

        self._rp = self.credentials['remote_path']
        self._usr = self.credentials['user']
        self._pw = self.credentials['passwd']
        self._hst = self.credentials['host']
        self._test_credentials = (self._hst, self._usr, self._pw)
        self._test_connection = (self._hst, self._usr, self._pw, TEST_DIR, self._rp)

    def test_manifest(self):
        # self.skipTest('')
        ftp = uptpy.get_ftp(*self._test_credentials)[0]
        current = uptpy.load_manifest(ftp, self._rp)

        remote = uptpy.scan_remote(ftp, self._rp)
        self.assertTrue(isinstance(remote, dict))
        self.assertTrue('' in remote)
        self.assertTrue(DATA_JSON in remote[''])
        self.assertTrue('size' in remote[''][DATA_JSON])

        self._ensure_deleted(ftp, self._rp, uptpy.REMOTE_MANIFEST)
        self.assertEqual(uptpy.load_manifest(ftp, self._rp), {})

        uptpy.update_manifest(ftp, current, TEST_DIR, self._rp)
        ftp.close()

    def test_delete(self):
        self.skipTest('')
        name = 'delete.me'
        # prepare
        ftp = uptpy.get_ftp(*self._test_credentials)[0]
        self._ensure_deleted(ftp, self._rp, name)

        new_file = os.path.join(TEST_DIR, name)
        with open(new_file, 'w', encoding='utf8') as file_obj:
            file_obj.write('1337')

        # sync
        uptpy.update(*self._test_connection)
        # delete remotely
        self._ensure_deleted(ftp, self._rp, name)
        # delete locally
        os.unlink(new_file)
        # re-sync (file is in manifest and should be tried to delete)
        num_changes = uptpy.update(*self._test_connection)
        self.assertEqual(num_changes, 0)

        ftp.close()

    def test_dirtree_add_create(self):
        self.skipTest('')
        prefix = '_random_'
        # remove old random dir locally
        for item in os.scandir(TEST_DIR):
            if item.is_dir() and item.name.startswith(prefix):
                shutil.rmtree(item.path)

        # create new local random dir
        dirname = prefix + str(uuid.uuid4())
        dirpath = os.path.join(TEST_DIR, dirname)
        os.mkdir(dirpath)
        subdir = os.path.join(dirpath, 'subdir')
        os.mkdir(subdir)
        subdir2 = os.path.join(subdir, 'subdir2')
        os.mkdir(subdir2)
        for i in range(3):
            subfile = os.path.join(subdir, f'file{i}.txt')
            with open(subfile, 'w', encoding='utf8') as file_obj:
                file_obj.write('chuckles')
            subfile2 = os.path.join(subdir2, f'file{i}.bin')
            with open(subfile2, 'wb') as file_obj:
                file_obj.write(b'\x00\x00\x00')

        num_changes = uptpy.update(*self._test_connection)

        ftp = uptpy.get_ftp(*self._test_credentials)[0]
        r_things = sorted(
            os.path.relpath(i, self._rp)
            for i in ftp.nlst(self._rp)
            if not i.endswith('.')
        )
        ftp.close()
        # l_things = sorted(i.name for i in os.scandir(TEST_DIR))
        self.assertTrue(dirname in r_things)
        self.assertEqual(len([i for i in r_things if i.startswith(prefix)]), 1)
        self.assertNotEqual(num_changes, 0)

    def test_change(self):
        local_data = _change_local_data()

        ftp = uptpy.get_ftp(*self._test_credentials)[0]
        uptpy.mk_dirs(ftp, self._rp, '')

        remote_data1 = self._get_remote_data(ftp)

        result = uptpy.update(*self._test_connection)
        self.assertTrue(result > 0)

        remote_data2 = self._get_remote_data(ftp)
        ftp.close()

        self.assertNotEqual(remote_data1.get('random'), remote_data2['random'])
        self.assertEqual(local_data['random'], remote_data2['random'])

    def test_cli_change(self):
        local_data = _change_local_data()

        ftp = uptpy.get_ftp(*self._test_credentials)[0]
        uptpy.mk_dirs(ftp, self._rp, '')

        remote_data1 = self._get_remote_data(ftp)

        subprocess.call(
            [sys.executable, 'uptpy.py'] + list(self._test_connection),
            cwd=os.path.dirname(THIS_DIR),
        )

        remote_data2 = self._get_remote_data(ftp)
        ftp.close()

        self.assertNotEqual(remote_data1.get('random'), remote_data2['random'])
        self.assertEqual(local_data['random'], remote_data2['random'])

    def test_non_ascii_names(self):
        # It's more complicated. I guess ftp-encoding `utf8` is alright when just
        # pushing and pulling dedicated files. Listing via `nlst()` will break on
        # e-acute `\u00e9` when using `utf8`, it works with `latin-1` tho!
        # but if you put smiley in names ONLY `utf8` encoding works :|
        smiley = '_\ud83e\udd17'.encode('utf-16', 'surrogatepass').decode('utf-16')
        file_name = f'_Str\u00ebu\u00dfel{smiley}br\u00f6tchen.txt'
        rel_path = posixpath.join(smiley, file_name)
        file_path = os.path.join(TEST_DIR, rel_path)
        content = _make_file(file_path)

        ftp = uptpy.get_ftp(*self._test_credentials)[0]
        uptpy.update(*self._test_connection, in_ftp=ftp)

        remote_content = uptpy.read_remote(ftp, posixpath.join(self._rp, rel_path))
        self.assertEqual(remote_content, content)
        ftp.close()

    def test_ignored_remotely(self):
        rel_path1 = 'DO_BE_IGNORED.nop'
        rel_path2 = posixpath.join('IGNORE_SUBDIR', 'DO_BE_IGNORED.nop')
        local_file1 = os.path.join(TEST_DIR, rel_path1)
        local_file2 = os.path.join(TEST_DIR, rel_path2)
        for path in local_file1, local_file2:
            if os.path.isfile(path):
                os.unlink(path)
            self.assertFalse(os.path.isfile(path))

        ftp = uptpy.get_ftp(*self._test_credentials)[0]
        uptpy.update(*self._test_connection, in_ftp=ftp)

        content1 = _make_file(local_file1)
        content2 = _make_file(local_file2)

        uptpy._upload(ftp, rel_path1, TEST_DIR, self._rp)
        uptpy.mk_dirs(ftp, self._rp, 'IGNORE_SUBDIR')
        uptpy._upload(ftp, rel_path2, TEST_DIR, self._rp)

        for path in local_file1, local_file2:
            os.unlink(path)
            self.assertFalse(os.path.isfile(path))

        result = uptpy.update(*self._test_connection, in_ftp=ftp)
        self.assertEqual(result, 0)

        for rel_path, content in ((rel_path1, content1), (rel_path2, content2)):
            remote_content = uptpy.read_remote(ftp, posixpath.join(self._rp, rel_path))
            self.assertEqual(remote_content, content)
        ftp.close()

    def _ensure_deleted(self, ftp, remote_root, name):
        remote_path = posixpath.join(remote_root, name)
        uptpy.mk_dirs(ftp, remote_root)
        things = ftp.nlst(remote_root)
        if remote_path in things:
            ftp.delete(remote_path)
            things = ftp.nlst(remote_root)
            self.assertFalse(remote_path in things)

    def _get_remote_data(self, ftp):
        try:
            content = uptpy.read_remote(ftp, posixpath.join(self._rp, DATA_JSON))
            return json.loads(content)
        except Exception as error:
            return {}


def _make_file(file_path, content=None):
    if os.path.isfile(file_path):
        with open(file_path, encoding='utf8') as file_obj:
            return file_obj.read()
    dir_path = os.path.dirname(file_path)
    if not os.path.isdir(dir_path):
        os.makedirs(dir_path)
    if content is None:
        content = str(uuid.uuid4())
    with open(file_path, 'w', encoding='utf8') as file_obj:
        file_obj.write(content)
    return content


def _change_local_data():
    data_json = os.path.join(TEST_DIR, DATA_JSON)
    if not os.path.isfile(data_json):
        local_data = {'nothing': None}
    else:
        with open(data_json, encoding='utf8') as file_obj:
            local_data = json.load(file_obj)
    local_data['random'] = str(uuid.uuid4())
    with open(data_json, 'w', encoding='utf8') as file_obj:
        json.dump(local_data, file_obj)
    return local_data


if __name__ == '__main__':
    unittest.main()
