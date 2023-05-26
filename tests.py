#!python

import os
import random
import string
import subprocess
import tempfile
import unittest

from shellserver.gitstatus import interface, plugins


# TODO: solve this
plugins.HAS_WATCHDOG = False

interface.init()
obj = interface._Globals.obj


def popen(cmd: str) -> bytes:
    out, err = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW
    ).communicate()
    return out


def get_random_string() -> str:
    return ''.join(random.choice(string.ascii_letters) for _ in range(200))


def ni(temp, x: str) -> None:
    dir = os.path.dirname(x)
    if dir != x:
        os.makedirs(os.path.join(temp, dir), exist_ok=True)
    with open(temp + '/' + x, 'w') as _:
        pass


class TestGitstatusLowEmpty(unittest.TestCase):
    """
    Tests for low module with just initialized git repo.
    """

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_test_')
        popen(f'git init {cls.temp}')

    @classmethod
    def tearDownClass(cls):
        obj._write_buffer()
        os.system(f'rmdir /s /q {cls.temp}')

    def test_empty_get_dot_git(self):
        path = os.path.join(self.temp, '.git/objects')
        git_dir = interface._get_dot_git(path)
        self.assertEqual(git_dir, self.temp)

    def test_empty_get_branch_on_head(self):
        branch = interface._get_branch_on_head(self.temp)
        self.assertEqual(branch, 'master')

        popen(f'git -C {self.temp} branch -M main')
        branch = interface._get_branch_on_head(self.temp)
        self.assertEqual(branch, 'main')


class TestGitstatusLowEmpty2(unittest.TestCase):
    """
    Tests for low module with just initialized git repo
    whithout changing branch name
    """

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_test_')
        popen(f'git init {cls.temp}')
        obj.init(cls.temp, 'master')

    @classmethod
    def tearDownClass(cls):
        obj._write_buffer()
        os.system(f'rmdir /s /q {cls.temp}')

    def test_empty_get_info_packs_content(self):
        tested = obj.get_info_packs_content()
        self.assertEqual(tested, [])

    def test_empty_get_gitignore_content(self):
        tested = obj.get_gitignore_content(self.temp)
        self.assertEqual(tested, [])

        text = 'some text'
        with open(self.temp + '/.gitignore', 'w') as f:
            print(text, file=f)
        tested = obj.get_gitignore_content(self.temp)
        self.assertEqual(tested, [text])

    def test_empty_get_last_commit_loose(self):
        tested = obj.get_last_commit_loose()
        self.assertIsNone(tested)

    def test_empty_get_info_refs_content(self):
        tested = obj.get_info_refs_content()
        self.assertEqual(tested, [])

    def test_empty_get_exclude_content(self):
        tested = obj.get_exclude_content()
        exc = os.path.join(self.temp, '.git/info/exclude')
        with open(exc) as f:
            local = f.readlines()
        local = [i.strip() for i in local if i.strip()]
        self.assertEqual(tested, local)

    # commet the ones not really testing
    # so we don't fake the number of ran tests
    '''
    def test_empty_get_hash_of_file(self):
        # can't test for empty repo
    '''

    def test_empty_get_content_by_hash_loose(self):
        tested = obj.get_content_by_hash_loose('any')
        self.assertIsNone(tested)

    def test_empty_get_tree_hash_from_commit(self):
        # supose and cmmt obj
        tree_hash = b'0123456789abcdf'
        cmmt_obj = b'may be more things tree ' + tree_hash + b'\n'
        tested = obj.get_tree_hash_from_commit(cmmt_obj)
        self.assertEqual(tested, tree_hash.decode())

    def test_empty_get_status_string(self):
        sts = (0, 0, 0, 0)
        tested = obj.get_status_string(sts)
        self.assertIsNone(tested)

        sts = (1, 0, 0, 0)
        tested = obj.get_status_string(sts)
        self.assertEqual(tested, '?1')

        sts = (0, 1, 0, 0)
        tested = obj.get_status_string(sts)
        self.assertEqual(tested, '+1')

        sts = (0, 0, 1, 0)
        tested = obj.get_status_string(sts)
        self.assertEqual(tested, 'm1')

        sts = (0, 0, 0, 1)
        tested = obj.get_status_string(sts)
        self.assertEqual(tested, 'x1')

        sts = (1, 1, 1, 1)
        tested = obj.get_status_string(sts)
        self.assertEqual(tested, '?1 +1 m1 x1')

        sts = (1, 0, 1, 0)
        tested = obj.get_status_string(sts)
        self.assertEqual(tested, '?1 m1')

        sts = (0, 1, 0, 1)
        tested = obj.get_status_string(sts)
        self.assertEqual(tested, '+1 x1')

    def test_empty_exists_head(self):
        tested = interface._exists_head(self.temp)
        path = os.path.join(self.temp, '.git/HEAD')
        local = os.path.exists(path)
        self.assertEqual(tested, local)

    def test_empty_parse_git_status(self):
        tested = obj.parse_git_status()
        # test_get_gitignore_content created .gitignore
        self.assertEqual(tested, '??1')


class TestGitstatusLowLoose(unittest.TestCase):
    """
    Tests for low module with git repo with files.
    """

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_test_')
        popen(f'git init {cls.temp}')
        with open(f'{cls.temp}/file.txt', 'wb') as file:
            file.write(get_random_string().encode() + b'\n')
        with open(f'{cls.temp}/file_cr.txt', 'wb') as file:
            file.write(get_random_string().encode() + b'\r\n')
        popen(f'git -C {cls.temp} add .')
        popen(f'git -C {cls.temp} commit -m "some"')
        obj.init(cls.temp, 'master')

    @classmethod
    def tearDownClass(cls):
        obj._write_buffer()
        os.system(f'rmdir /s /q {cls.temp}')

    '''
    def test_loose_get_dot_git(self):
        # no need to retest

    def test_loose_get_branch_on_head(self):
        # no need to retest

    def test_loose_get_info_packs_content(self):
        # no need to retest

    def test_loose_get_gitignore_content(self):
        # no need to retest
    '''

    def test_loose_get_last_commit_loose(self):
        tested = obj.get_last_commit_loose()
        master = os.path.join(self.temp, '.git/refs/heads/master')
        with open(master) as file:
            local = file.read()
        self.assertEqual(tested, local.strip())

    def test_loose_get_info_refs_content(self):
        # should only exists if there are packed files
        tested = obj.get_info_refs_content()
        self.assertEqual(tested, [])

    '''
    def test_loose_get_exclude_content(self):
        # no need to retest

    def test_loose_build_filtered_patterns(self):
        # no need to retest
    '''

    def test_loose_get_hash_of_file(self):
        file_hash = obj.get_hash_of_file(self.temp + '/file.txt')
        git_hash = popen(
            f'git -C {self.temp} hash-object file.txt'
        ).strip().decode()
        self.assertEqual(file_hash, git_hash)

        file_hash = obj.get_hash_of_file(
            self.temp + '/file_cr.txt'
        )
        git_hash = popen(
            f'git -C {self.temp} hash-object file_cr.txt'
        ).strip().decode()
        self.assertEqual(file_hash, git_hash)

    def test_loose_get_content_by_hash_loose(self):
        file_hash = obj.get_hash_of_file(self.temp + '/file.txt')
        tested = obj.get_content_by_hash_loose(file_hash)
        local = popen(
            f'git -C {self.temp} cat-file -p {file_hash}'
        ).strip()
        self.assertIn(local, tested)

    '''
    def test_loose_get_tree_hash_from_commit(self):
        # no need to retest

    def test_loose_get_status_string(self):
        # no need to retest

    def test_loose_exists_head(self):
        # no need to retest
    '''

    def test_loose_parse_git_status(self):
        tested = obj.parse_git_status()
        self.assertIsNone(tested)


class TestGitstatusLowPacked(unittest.TestCase):
    """
    Tests for low module with git repo with packed files.
    """

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_test_')
        popen(f'git init {cls.temp}')
        with open(f'{cls.temp}/file.txt', 'wb') as file:
            file.write(get_random_string().encode() + b'\n')
        with open(f'{cls.temp}/file_cr.txt', 'wb') as file:
            file.write(get_random_string().encode() + b'\r\n')
        popen(f'git -C {cls.temp} add .')
        popen(f'git -C {cls.temp} commit -m "some"')
        popen(f'git -C {cls.temp} gc')
        obj.init(cls.temp, 'master')

    @classmethod
    def tearDownClass(cls):
        obj._write_buffer()
        os.system(f'rmdir /s /q {cls.temp}')

    '''
    def test_packed_get_dot_git(self):
        # no need to retest

    def test_packed_get_branch_on_head(self):
        # no need to retest

    def test_packed_get_info_packs_content(self):
        # no need to retest

    def test_packed_get_gitignore_content(self):
        # no need to retest
    '''

    def test_packed_get_last_commit_loose(self):
        tested = obj.get_last_commit_loose()
        self.assertIsNone(tested)

    def test_packed_get_info_refs_content(self):
        tested = obj.get_info_refs_content()
        refs = os.path.join(self.temp, '.git/info/refs')
        with open(refs) as file:
            local = file.readlines()
        local = [i.strip() for i in local if i.strip()]
        self.assertEqual(tested, local)

    '''
    def test_packed_get_exclude_content(self):
        # no need to retest

    def test_packed_get_hash_of_file(self):
        # no need to retest
    '''

    def test_packed_get_content_by_hash_loose(self):
        file_hash = obj.get_hash_of_file(self.temp + '/file.txt')
        tested = obj.get_content_by_hash_loose(file_hash)
        self.assertIsNone(tested)

    '''
    def test_packed_get_tree_hash_from_commit(self):
        # no need to retest

    def test_packed_get_status_string(self):
        # no need to retest

    def test_packed_exists_head(self):
        # no need to retest
    '''

    def test_packed_parse_git_status(self):
        tested = obj.parse_git_status()
        self.assertIsNone(tested)


class TestGitstatusMediumEmpty(unittest.TestCase):
    """
    Tests for medium module with just initialized git repo.
    """

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_test_')
        popen(f'git init {cls.temp}')
        obj.init(cls.temp, 'master')

    @classmethod
    def tearDownClass(cls):
        obj._write_buffer()
        os.system(f'rmdir /s /q {cls.temp}')

    def test_empty_get_packs(self):
        obj.set_packs()
        self.assertEqual(obj.packs_list, [])

    def test_empty_get_content_by_hash_packed(self):
        obj.set_packs()
        tested = obj.get_content_by_hash_packed('anyabcdf01234')
        self.assertIsNone(tested)

    def test_empty_get_last_commit_packed(self):
        tested = obj.get_last_commit_packed()
        self.assertIsNone(tested)

    def test_empty_get_last_commit(self):
        tested = obj.get_last_commit_hash()
        self.assertIsNone(tested)


class TestGitstatusMediumLoose(unittest.TestCase):
    """
    Tests for medium module with git repo with files.
    """

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_tests_')
        popen(f'git init {cls.temp}')
        with open(f'{cls.temp}/file.txt', 'wb') as file:
            file.write(get_random_string().encode() + b'\n')
        with open(f'{cls.temp}/file_cr.txt', 'wb') as file:
            file.write(get_random_string().encode() + b'\r\n')
        popen(f'git -C {cls.temp} add .')
        popen(f'git -C {cls.temp} commit -m "some"')
        obj.init(cls.temp, 'master')

    @classmethod
    def tearDownClass(cls):
        obj._write_buffer()
        os.system(f'rmdir /s /q {cls.temp}')

    """
    def test_loose_get_packs(self):
        # no need to retest

    def test_loose_get_content_by_hash_packed(self):
        # no need to retest

    def test_loose_get_last_commit_packed(self):
        # no need to retest
    """

    def test_loose_get_last_commit(self):
        tested = obj.get_last_commit_hash()
        low_tested = obj.get_last_commit_loose()
        self.assertEqual(tested, low_tested)

        master = os.path.join(self.temp, '.git/refs/heads/master')
        with open(master) as file:
            local = file.read()
        self.assertEqual(tested, local.strip())

    def test_loose_get_index_tracked(self):
        ni(self.temp, 'file')
        ni(self.temp, 'other')
        ni(self.temp, 'some')
        ni(self.temp, 'dir/file')
        popen(f'git -C {self.temp} add .')

        obj.set_index_tracked()
        tested = obj.index_tracked

        self.assertGreaterEqual(len(tested), 3)
        self.assertIn('file', tested)
        self.assertIn('other', tested)
        self.assertIn('some', tested)
        self.assertIn('dir/file', tested)

        # setUpClass created two files
        self.assertEqual(len(tested), 6)


class TestGitstatusMediumPacked(unittest.TestCase):
    """
    Tests for medium module with git repo with packed files.
    """

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_test_')
        popen(f'git init {cls.temp}')
        with open(f'{cls.temp}/file.txt', 'wb') as file:
            file.write(get_random_string().encode() + b'\n')
        with open(f'{cls.temp}/file_cr.txt', 'wb') as file:
            file.write(get_random_string().encode() + b'\r\n')
        popen(f'git -C {cls.temp} add .')
        popen(f'git -C {cls.temp} commit -m "some"')
        popen(f'git -C {cls.temp} gc')
        obj.init(cls.temp, 'master')

    @classmethod
    def tearDownClass(cls):
        obj._write_buffer()
        os.system(f'rmdir /s /q {cls.temp}')

    def test_packed_get_packs(self):
        obj.set_packs()

        packs = os.path.join(self.temp, '.git/objects/pack')
        local = [packs + '\\' + i
                 for i in os.listdir(packs)
                 if i.endswith('pack')]
        tested = obj.packs_list
        self.assertEqual(tested, local)

    def test_packed_get_content_by_hash_packed(self):
        obj.set_packs()
        file_hash = obj.get_hash_of_file(self.temp + '/file.txt')
        tested = obj.get_content_by_hash_packed(file_hash)
        local = popen(f'git -C {self.temp} cat-file -p {file_hash}')
        self.assertIn(local, tested)

    def test_packed_get_last_commit_packed(self):
        # I can't test this with a git background
        obj.set_packs()

        tested = obj.get_last_commit_packed()
        refs = obj.get_info_refs_content()
        self.assertEqual(len(tested), 40)
        self.assertTrue(int(tested, 16))
        self.assertEqual(tested, tested.strip())
        self.assertIn(tested, refs[0])

    def test_packed_get_last_commit(self):
        obj.set_packs()

        tested = obj.get_last_commit_hash()
        other_tested = obj.get_last_commit_packed()
        self.assertEqual(tested, other_tested)


class TestGitstatusPacksPacked(unittest.TestCase):
    """
    Tests for packs module with git repo with packed files.
    """
    # makes no sense testing for other cases

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_test_')
        popen(f'git init {cls.temp}')
        with open(f'{cls.temp}/file.txt', 'wb') as file:
            file.write(get_random_string().encode() + b'\n')
        with open(f'{cls.temp}/file_cr.txt', 'wb') as file:
            file.write(get_random_string().encode() + b'\r\n')
        popen(f'git -C {cls.temp} add .')
        popen(f'git -C {cls.temp} commit -m "some"')
        popen(f'git -C {cls.temp} gc')
        obj.init(cls.temp, 'master')
        obj.set_packs()

    @classmethod
    def tearDownClass(cls):
        obj._write_buffer()
        os.system(f'rmdir /s /q {cls.temp}')

    def test_search_idx(self):
        idx_path = obj.get_idx_of_pack(
            obj.packs_list[0]
        )
        file_hash = obj.get_hash_of_file(self.temp + '/file.txt')
        filecr_hash = obj.get_hash_of_file(self.temp + '/file_cr.txt')

        tested = obj.search_idx(idx_path, file_hash)
        self.assertTrue(tested)
        tested = obj.search_idx(idx_path, filecr_hash)
        self.assertTrue(tested)

    def test_get_content_by_offset(self):
        pack = obj.packs_list[0]
        idx_path = obj.get_idx_of_pack(pack)

        file_hash = obj.get_hash_of_file(self.temp + '/file.txt')
        filecr_hash = obj.get_hash_of_file(self.temp + '/file_cr.txt')

        file_off = obj.search_idx(idx_path, file_hash)
        filecr_off = obj.search_idx(idx_path, filecr_hash)

        file_obj = obj.get_content_by_offset(pack, file_off)
        filecr_obj = obj.get_content_by_offset(pack, filecr_off)

        local1 = popen(f'git -C {self.temp} cat-file -p {file_hash}')
        local2 = popen(f'git -C {self.temp} cat-file -p {filecr_hash}')

        self.assertEqual(local1, file_obj)
        self.assertEqual(local2, filecr_obj)


class TestGitstatusHighStatus(unittest.TestCase):
    """
    Tests for high module with just initialized git repo.
    """

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_test_')
        popen(f'git init {cls.temp}')
        obj.init(cls.temp, 'master')

    @classmethod
    def tearDownClass(cls):
        obj._write_buffer()
        os.system(f'rmdir /s /q {cls.temp}')

    def test_status(self):
        self.assertIsNone(obj.status())

        file_path = self.temp + '/file.txt'
        with open(file_path, 'w') as file:
            file.write(get_random_string())
        git = obj.parse_git_status()
        self.assertEqual(git, '??1')
        tested = obj.status()
        self.assertEqual(tested, '?1')

        popen(f'git -C {self.temp} add .')
        git = obj.parse_git_status()
        self.assertEqual(git, 'A1')
        tested = obj.status()
        self.assertEqual(tested, '+1')

        popen(f'git -C {self.temp} commit -m "some"')
        git = obj.parse_git_status()
        self.assertIsNone(git)
        self.assertIsNone(obj.status())

        with open(file_path, 'a') as file:
            file.write(get_random_string())
        git = obj.parse_git_status()
        self.assertEqual(git, 'M1')
        tested = obj.status()
        self.assertEqual(tested, 'm1')

        os.remove(file_path)
        git = obj.parse_git_status()
        self.assertEqual(git, 'D1')
        tested = obj.status()
        self.assertEqual(tested, 'x1')

        popen(f'git -C {self.temp} add .')
        popen(f'git -C {self.temp} commit -m "other"')
        git = obj.parse_git_status()
        self.assertIsNone(git)
        self.assertIsNone(obj.status())

        popen(f'git -C {self.temp} gc')
        git = obj.parse_git_status()
        self.assertIsNone(git)
        self.assertIsNone(obj.status())


class TestGitstatusHighStatusIgnore(unittest.TestCase):
    """
    Tests for high module with just initialized git repo.
    """

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_test_')
        popen(f'git init {cls.temp}')
        obj.init(cls.temp, 'master')

    @classmethod
    def tearDownClass(cls):
        obj._write_buffer()
        os.system(f'rmdir /s /q {cls.temp}')

    def test_status_ignore(self):
        gitignore = self.temp + '/.gitignore'
        with open(gitignore, 'w') as ignore:
            pass
        tested = obj.status()
        self.assertEqual(tested, '?1')
        git = obj.parse_git_status()
        self.assertEqual(git, '??1')

        ni(self.temp, 'ignored_dir/some')
        with open(gitignore, 'w') as ignore:
            ignore.write('ignored_dir\n')
        tested = obj.status()
        self.assertEqual(tested, '?1')
        git = obj.parse_git_status()
        self.assertEqual(git, '??1')

        ni(self.temp, 'other/ignored.txt')
        with open(gitignore, 'a') as ignore:
            ignore.write('other/ign\n')
        git = obj.parse_git_status()
        self.assertEqual(git, '??2')
        tested = obj.status()
        self.assertEqual(tested, '?2')

        with open(gitignore, 'a') as ignore:
            ignore.write('other/ign*\n')
        tested = obj.status()
        self.assertEqual(tested, '?1')
        git = obj.parse_git_status()
        self.assertEqual(git, '??1')

        ni(self.temp, 'some/ignored.txt')
        tested = obj.status()
        self.assertEqual(tested, '?2')
        git = obj.parse_git_status()
        self.assertEqual(git, '??2')

        with open(gitignore, 'a') as ignore:
            ignore.write('some\n')
        tested = obj.status()
        self.assertEqual(tested, '?1')
        git = obj.parse_git_status()
        self.assertEqual(git, '??1')

        ni(self.temp, 'interrog.txt')
        with open(gitignore, 'a') as ignore:
            ignore.write('inter???.txt\n')
        tested = obj.status()
        self.assertEqual(tested, '?1')
        git = obj.parse_git_status()
        self.assertEqual(git, '??1')


class TestGitstatusInit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_test_')

    @classmethod
    def tearDownClass(cls):
        obj._write_buffer()
        os.system(f'rmdir /s /q {cls.temp}')

    def test_gitstatus(self):
        tested = interface.gitstatus(self.temp)
        self.assertEqual(tested, (None, None))

        popen(f'git init {self.temp}')
        tested = interface.gitstatus(self.temp)
        self.assertEqual(tested, ('master', None))

        popen(f'git -C {self.temp} branch -M main')
        tested = interface.gitstatus(self.temp)
        self.assertEqual(tested, ('main', None))

        ni(self.temp, 'file.txt')
        tested = interface.gitstatus(self.temp)
        self.assertEqual(tested, ('main', '?1'))


class TestGitstatusPygit2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_test_')
        popen(f'git init {cls.temp}')
        obj.init(cls.temp, 'master')

    @classmethod
    def tearDownClass(cls):
        obj._write_buffer()
        os.system(f'rmdir /s /q {cls.temp}')

    def test_pygit2_full_routine(self):
        ni(self.temp, 'file0')
        self.assertEqual(obj.parse_pygit2(), '?1')
        ni(self.temp, 'dir0/file0')
        self.assertEqual(obj.parse_pygit2(), '?2')
        ni(self.temp, 'n_dir/n_dir/n_dir/file0')
        self.assertEqual(obj.parse_pygit2(), '?3')

        popen(f'git -C {self.temp} add .')
        self.assertEqual(obj.parse_pygit2(), '+3')
        ni(self.temp, 'other')
        self.assertEqual(obj.parse_pygit2(), '?1 +3')

        popen(f'git -C {self.temp} add .')
        self.assertEqual(obj.parse_pygit2(), '+4')
        popen(f'git -C {self.temp} commit -m "some"')
        self.assertIsNone(obj.parse_pygit2())

        with open(self.temp + '/file0', 'w') as file:
            print(get_random_string(), file=file)
        self.assertEqual(obj.parse_pygit2(), 'm1')

        os.remove(self.temp + '/dir0/file0')
        self.assertEqual(obj.parse_pygit2(), 'm1 x1')


class TestGitstatusTDD0(unittest.TestCase):
    """
    Another test for status
    """

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_test_')
        popen(f'git init {cls.temp}')
        obj.init(cls.temp, 'master')

    @classmethod
    def tearDownClass(cls):
        obj._write_buffer()
        os.system(f'rmdir /s /q {cls.temp}')

    def test_status(self):
        ni(self.temp, 'some/file.txt')
        popen(f'git -C {self.temp} add .')
        git = obj.parse_git_status()
        self.assertEqual(git, 'A1')
        tested = obj.status()
        self.assertEqual(tested, '+1')


class TestGitstatusTDD1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_test_')
        popen(f'git init {cls.temp}')
        obj.init(cls.temp, 'master')

    @classmethod
    def tearDownClass(cls):
        obj._write_buffer()
        os.system(f'rmdir /s /q {cls.temp}')

    def test_status_ignore(self):
        gitignore = self.temp + '/.gitignore'
        with open(gitignore, 'w') as ignore:
            # case of string
            ignore.write('Third\n')
        ni(self.temp, 'third/file')
        git = obj.parse_git_status()
        self.assertEqual(git, '??1')
        tested = obj.status()
        self.assertEqual(tested, '?1')


class TestGitstatusTDD2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_test_')
        popen(f'git init {cls.temp}')
        obj.init(cls.temp, 'master')

    @classmethod
    def tearDownClass(cls):
        obj._write_buffer()
        os.system(f'rmdir /s /q {cls.temp}')

    def test_status_ignore(self):
        gitignore = self.temp + '/.gitignore'
        with open(gitignore, 'w') as ignore:
            # ending slash
            ignore.write('some/\n')
        ni(self.temp, 'some/file.txt')
        ni(self.temp, 'other/some')
        git = obj.parse_git_status()
        self.assertEqual(git, '??2')
        tested1 = obj.status()

        with open(gitignore, 'a') as ignore:
            # initial slash
            ignore.write('/other\n')
        git = obj.parse_git_status()
        self.assertEqual(git, '??1')
        tested2 = obj.status()

        with open(gitignore, 'a') as ignore:
            ignore.write('other/\n')
        ni(self.temp, 'dira/dirb/other/anything.txt')
        git = obj.parse_git_status()
        self.assertEqual(git, '??1')
        tested3 = obj.status()

        with open(gitignore, 'a') as ignore:
            ignore.write('anya/anyb/\n')
        ni(self.temp, 'random/anya/anyb/anything.txt')
        git = obj.parse_git_status()
        self.assertEqual(git, '??2')
        tested4 = obj.status()

        # created new file but whole tree is ignored
        # thats why there is no new untracked
        nest_ign_path = self.temp + '/random/anya/.gitignore'
        with open(nest_ign_path, 'w') as f:
            f.write('/anything.txt\n')
        git = obj.parse_git_status()
        self.assertEqual(git, '??2')
        tested5 = obj.status()

        with open(nest_ign_path, 'a') as f:
            f.write('/.gitignore\n')
        git = obj.parse_git_status()
        self.assertEqual(git, '??2')
        tested6 = obj.status()

        with open(nest_ign_path, 'a') as f:
            f.write('/anya\n')
        git = obj.parse_git_status()
        self.assertEqual(git, '??2')
        tested7 = obj.status()

        self.assertEqual(tested1, '?2')
        self.assertEqual(tested2, '?1')
        self.assertEqual(tested3, '?1')
        self.assertEqual(tested4, '?2')
        self.assertEqual(tested5, '?2')
        self.assertEqual(tested6, '?2')
        self.assertEqual(tested7, '?2')


class TestGitstatusTDD3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_test_')
        popen(f'git init {cls.temp}')
        obj.init(cls.temp, 'master')

    @classmethod
    def tearDownClass(cls):
        obj._write_buffer()
        os.system(f'rmdir /s /q {cls.temp}')

    def test_status_ignore(self):
        gitignore = self.temp + '/.gitignore'
        with open(gitignore, 'w') as ignore:
            ni(self.temp, 'a/b/c/d')
            ignore.write('a/**/d\n')

        git = obj.parse_git_status()
        self.assertEqual(git, '??1')
        tested = obj.status()
        self.assertEqual(tested, '?1')


class TestGitstatusTDD4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_test_')
        popen(f'git init {cls.temp}')
        obj.init(cls.temp, 'master')

    @classmethod
    def tearDownClass(cls):
        obj._write_buffer()
        os.system(f'rmdir /s /q {cls.temp}')

    def test_modified_after_commit(self):
        gitignore = self.temp + '/.gitignore'
        with open(gitignore, 'w') as ignore:
            ignore.write('anything')
        popen(f'git -C {self.temp} add .')
        popen(f'git -C {self.temp} commit -m "other"')
        with open(gitignore, 'a') as ignore:
            ignore.write('anything')
        popen(f'git -C {self.temp} add .')
        git = obj.parse_git_status()
        self.assertEqual(git, 'M1')
        tested = obj.status()
        self.assertEqual(tested, 'm1')


class TestGitstatusTDD5(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_test_')
        popen(f'git init {cls.temp}')
        obj.init(cls.temp, 'master')

    @classmethod
    def tearDownClass(cls):
        obj._write_buffer()
        os.system(f'rmdir /s /q {cls.temp}')

    def test_status_handle_untracked_dir(self):
        ni(self.temp, 'dir/file')
        ni(self.temp, 'dir/other')
        popen(f'git -C {self.temp} add dir\\file')

        git = obj.parse_git_status()
        git = set(git.split())
        self.assertEqual(git, {'A1', '??1'})
        tested = obj.status()
        self.assertEqual(tested, '?1 +1')

        ni(self.temp, 'dir/dir/sub/some')
        tested = obj.status()
        self.assertEqual(tested, '?2 +1')
        git = obj.parse_git_status()
        git = set(git.split())
        self.assertEqual(git, {'??2', 'A1'})


class TestGitstatusTDD6(unittest.TestCase):
    "Test nested .gitignore files"

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_test_')
        popen(f'git init {cls.temp}')
        obj.init(cls.temp, 'master')

    @classmethod
    def tearDownClass(cls):
        obj._write_buffer()
        os.system(f'rmdir /s /q {cls.temp}')

    def test_nested_gitignore(self):
        ni(self.temp, 'some/.gitignore')
        with open(self.temp + '/some/.gitignore', 'w') as f:
            f.write('*\n')
        git = obj.parse_git_status()
        self.assertIsNone(git)
        self.assertIsNone(obj.status())

        ni(self.temp, 'other/dir/abcd/.gitignore')
        with open(self.temp + '/other/dir/abcd/.gitignore', 'w') as f:
            f.write('*\n')
        git = obj.parse_git_status()
        self.assertIsNone(git)
        self.assertIsNone(obj.status())


if __name__ == "__main__":
    unittest.main()
