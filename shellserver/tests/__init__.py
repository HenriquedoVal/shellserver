import os
import random
import string
import subprocess
import tempfile
import unittest

from ..gitstatus.__init__ import gitstatus
from ..gitstatus import low
from ..gitstatus import medium
from ..gitstatus import high
from ..gitstatus.packs import MAPPED_CACHE


def clear_cache():
    for mmap in MAPPED_CACHE.values():
        mmap.close()


# maybe will be relevant:    
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
        os.system(f'rmdir /s /q {cls.temp}')

    def test_empty_get_dot_git(self):
        path = os.path.join(self.temp, '.git/objects')
        git_dir = low.get_dot_git(path)
        self.assertEqual(git_dir, self.temp)

    def test_empty_get_branch_on_head(self):
        branch = low.get_branch_on_head(self.temp)
        self.assertEqual(branch, 'master')

        popen(f'git -C {self.temp} branch -M main')
        branch = low.get_branch_on_head(self.temp)
        self.assertEqual(branch, 'main')

    def test_empty_get_info_packs_content(self):
        obj = low.Low()
        obj.git_dir = self.temp
        obj.branch = 'main'
        tested = obj.get_info_packs_content()
        self.assertEqual(tested, [])

    def test_empty_get_gitignore_content(self):
        obj = low.Low()
        obj.git_dir = self.temp
        obj.branch = 'main'
        tested = obj.get_gitignore_content()
        self.assertEqual(tested, [])

        text = 'some text'
        with open(self.temp + '/.gitignore', 'w') as f:
            print(text, file=f)
        tested = obj.get_gitignore_content()
        self.assertEqual(tested, [text])

    def test_empty_get_last_commit_loose(self):
        obj = low.Low()
        obj.git_dir = self.temp
        obj.branch = 'main'
        tested = obj.get_last_commit_loose()
        self.assertIsNone(tested)

    def test_empty_get_info_refs_content(self):
        obj = low.Low()
        obj.git_dir = self.temp
        obj.branch = 'main'
        tested = obj.get_info_refs_content()
        self.assertEqual(tested, [])

    def test_empty_get_exclude_content(self):
        obj = low.Low()
        obj.git_dir = self.temp
        obj.branch = 'main'
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
        obj = low.Low()
        obj.git_dir = self.temp
        obj.branch = 'main'
        tested = obj.get_content_by_hash_loose('any')
        self.assertIsNone(tested)

    def test_empty_get_tree_hash_from_commit(self):
        obj = low.Low()
        obj.git_dir = self.temp
        obj.branch = 'main'
        # supose and cmmt obj
        tree_hash = b'0123456789abcdf'
        cmmt_obj = b'may be more things tree ' + tree_hash + b'\n'
        tested = obj.get_tree_hash_from_commit(cmmt_obj)
        self.assertEqual(tested, tree_hash.decode())

    def test_empty_get_status_string(self):
        obj = low.Low()
        obj.git_dir = self.temp
        obj.branch = 'main'
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
        tested = low.exists_head(self.temp)
        path = os.path.join(self.temp, '.git/HEAD')
        local = os.path.exists(path)
        self.assertEqual(tested, local)

    def test_empty_parse_git_status(self):
        obj = low.Low()
        obj.git_dir = self.temp
        obj.branch = 'main'
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

    @classmethod
    def tearDownClass(cls):
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
        obj = low.Low()
        obj.git_dir = self.temp
        obj.branch = 'master'
        tested = obj.get_last_commit_loose()
        master = os.path.join(self.temp, '.git/refs/heads/master')
        with open(master) as file:
            local = file.read()
        self.assertEqual(tested, local.strip())

    def test_loose_get_info_refs_content(self):
        # should only exists if there are packed files
        obj = low.Low()
        obj.git_dir = self.temp
        obj.branch = 'master'
        tested = obj.get_info_refs_content()
        self.assertEqual(tested, [])

    '''
    def test_loose_get_exclude_content(self):
        # no need to retest

    def test_loose_build_filtered_patterns(self):
        # no need to retest
    '''

    def test_loose_get_hash_of_file(self):
        obj = low.Low()
        obj.git_dir = self.temp
        obj.branch = 'master'
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
        obj = low.Low()
        obj.git_dir = self.temp
        obj.branch = 'master'
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
        obj = low.Low()
        obj.git_dir = self.temp
        obj.branch = 'master'
        tested = obj.parse_git_status()
        self.assertEqual(tested, '')


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

    @classmethod
    def tearDownClass(cls):
        clear_cache()
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
        obj = low.Low()
        obj.git_dir = self.temp
        obj.branch = 'master'
        tested = obj.get_last_commit_loose()
        self.assertIsNone(tested)

    def test_packed_get_info_refs_content(self):
        obj = low.Low()
        obj.git_dir = self.temp
        obj.branch = 'master'
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
        obj = low.Low()
        obj.git_dir = self.temp
        obj.branch = 'master'
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
        obj = low.Low()
        obj.git_dir = self.temp
        obj.branch = 'master'
        tested = obj.parse_git_status()
        self.assertEqual(tested, '')


class TestGitstatusMediumEmpty(unittest.TestCase):
    """
    Tests for medium module with just initialized git repo.
    """

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_test_')
        popen(f'git init {cls.temp}')

    @classmethod
    def tearDownClass(cls):
        os.system(f'rmdir /s /q {cls.temp}')

    def test_empty_get_packs(self):
        obj = medium.Medium()
        obj.git_dir = self.temp
        obj.branch = 'master'
        obj.set_packs()
        self.assertEqual(obj.packs_list, [])

    def test_empty_get_content_by_hash_packed(self):
        obj = medium.Medium()
        obj.git_dir = self.temp
        obj.branch = 'master'
        obj.set_packs()
        tested = obj.get_content_by_hash_packed('anyabcdf01234')
        self.assertIsNone(tested)

    def test_empty_get_last_commit_packed(self):
        obj = medium.Medium()
        obj.git_dir = self.temp
        obj.branch = 'master'
        tested = obj.get_last_commit_packed()
        self.assertIsNone(tested)

    def test_empty_get_last_commit(self):
        obj = medium.Medium()
        obj.git_dir = self.temp
        obj.branch = 'master'
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

    @classmethod
    def tearDownClass(cls):
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
        obj = medium.Medium()
        obj.git_dir = self.temp
        obj.branch = 'master'
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

        obj = medium.Medium()
        obj.git_dir = self.temp
        obj.branch = 'master'
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

    @classmethod
    def tearDownClass(cls):
        clear_cache()
        os.system(f'rmdir /s /q {cls.temp}')

    def test_packed_get_packs(self):
        obj = medium.Medium()
        obj.git_dir = self.temp
        obj.branch = 'master'
        obj.set_packs()

        packs = os.path.join(self.temp, '.git/objects/pack')
        local = [packs + '\\' + i
                 for i in os.listdir(packs)
                 if i.endswith('pack')]
        tested = obj.packs_list
        self.assertEqual(tested, local)

    def test_packed_get_content_by_hash_packed(self):
        obj = medium.Medium()
        obj.git_dir = self.temp
        obj.branch = 'master'
        obj.set_packs()

        file_hash = obj.get_hash_of_file(self.temp + '/file.txt')
        tested = obj.get_content_by_hash_packed(file_hash)
        local = popen(f'git -C {self.temp} cat-file -p {file_hash}')
        self.assertIn(local, tested)

    def test_packed_get_last_commit_packed(self):
        # I can't test this with a git background
        obj = medium.Medium()
        obj.git_dir = self.temp
        obj.branch = 'master'
        obj.set_packs()

        tested = obj.get_last_commit_packed()
        refs = obj.get_info_refs_content()
        self.assertEqual(len(tested), 40)
        self.assertTrue(int(tested, 16))
        self.assertEqual(tested, tested.strip())
        self.assertIn(tested, refs[0])

    def test_packed_get_last_commit(self):
        obj = medium.Medium()
        obj.git_dir = self.temp
        obj.branch = 'master'
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

    @classmethod
    def tearDownClass(cls):
        clear_cache()
        os.system(f'rmdir /s /q {cls.temp}')

    def test_search_idx(self):
        obj = high.High(self.temp, 'master')
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
        obj = high.High(self.temp, 'master')
        pack = obj.packs_list[0]
        idx_path = obj.get_idx_of_pack(pack)

        file_hash = obj.get_hash_of_file(self.temp + '/file.txt')
        filecr_hash = obj.get_hash_of_file(self.temp + '/file_cr.txt')

        file_off = obj.search_idx(idx_path, file_hash, rt_offset=True)
        filecr_off = obj.search_idx(idx_path, filecr_hash, rt_offset=True)

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
        cls.branch = low.get_branch_on_head(cls.temp)

    @classmethod
    def tearDownClass(cls):
        clear_cache()
        os.system(f'rmdir /s /q {cls.temp}')

    def test_status(self):
        obj = high.High(self.temp, 'master')
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
        obj = high.High(self.temp, 'master')
        tested = obj.status()
        self.assertEqual(tested, '+1')

        popen(f'git -C {self.temp} commit -m "some"')
        git = obj.parse_git_status()
        self.assertEqual(git, '')
        obj = high.High(self.temp, 'master')
        self.assertIsNone(obj.status())

        with open(file_path, 'a') as file:
            file.write(get_random_string())
        git = obj.parse_git_status()
        self.assertEqual(git, 'M1')
        obj = high.High(self.temp, 'master')
        tested = obj.status()
        self.assertEqual(tested, 'm1')

        os.remove(file_path)
        git = obj.parse_git_status()
        self.assertEqual(git, 'D1')
        obj = high.High(self.temp, 'master')
        tested = obj.status()
        self.assertEqual(tested, 'x1')

        popen(f'git -C {self.temp} add .')
        popen(f'git -C {self.temp} commit -m "other"')
        git = obj.parse_git_status()
        self.assertEqual(git, '')
        obj = high.High(self.temp, 'master')
        self.assertIsNone(obj.status())

        popen(f'git -C {self.temp} gc')
        git = obj.parse_git_status()
        self.assertEqual(git, '')
        obj = high.High(self.temp, 'master')
        self.assertIsNone(obj.status())


class TestGitstatusHighStatusIgnore(unittest.TestCase):
    """
    Tests for high module with just initialized git repo.
    """

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_test_')
        popen(f'git init {cls.temp}')
        cls.branch = low.get_branch_on_head(cls.temp)

    @classmethod
    def tearDownClass(cls):
        os.system(f'rmdir /s /q {cls.temp}')

    def test_status_ignore(self):
        obj = high.High(self.temp, 'master')
        gitignore = self.temp + '/.gitignore'
        with open(gitignore, 'w') as ignore:
            tested = obj.status()
            self.assertEqual(tested, '?1')
            git = obj.parse_git_status()
            self.assertEqual(git, '??1')

            ni(self.temp, 'ignored_dir/some')
            ignore.write('ignored_dir\n')
            ignore.flush()
            obj = high.High(self.temp, 'master')
            tested = obj.status()
            self.assertEqual(tested, '?1')
            git = obj.parse_git_status()
            self.assertEqual(git, '??1')

            ni(self.temp, 'other/ignored.txt')
            ignore.write('other/ign\n')
            ignore.flush()
            obj = high.High(self.temp, 'master')
            tested = obj.status()
            self.assertEqual(tested, '?2')
            git = obj.parse_git_status()
            self.assertEqual(git, '??2')

            ignore.write('other/ign*\n')
            ignore.flush()
            obj = high.High(self.temp, 'master')
            tested = obj.status()
            self.assertEqual(tested, '?1')
            git = obj.parse_git_status()
            self.assertEqual(git, '??1')

            ni(self.temp, 'some/ignored.txt')
            obj = high.High(self.temp, 'master')
            tested = obj.status()
            self.assertEqual(tested, '?2')
            git = obj.parse_git_status()
            self.assertEqual(git, '??2')

            ignore.write('some\n')
            ignore.flush()
            obj = high.High(self.temp, 'master')
            tested = obj.status()
            self.assertEqual(tested, '?1')
            git = obj.parse_git_status()
            self.assertEqual(git, '??1')

            ni(self.temp, 'a/b/c/d')
            obj = high.High(self.temp, 'master')
            tested = obj.status()
            self.assertEqual(tested, '?2')
            git = obj.parse_git_status()
            self.assertEqual(git, '??2')

            ignore.write('a/**/d\n')
            ignore.flush()
            obj = high.High(self.temp, 'master')
            tested = obj.status()
            self.assertEqual(tested, '?1')
            git = obj.parse_git_status()
            self.assertEqual(git, '??1')

            ni(self.temp, 'interrog.txt')
            ignore.write('inter???.txt')
            ignore.flush()
            obj = high.High(self.temp, 'master')
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
        os.system(f'rmdir /s /q {cls.temp}')

    def test_gitstatus(self):
        tested = gitstatus(self.temp)
        self.assertEqual(tested, (None, None))

        popen(f'git init {self.temp}')
        tested = gitstatus(self.temp)
        self.assertEqual(tested, ('master', None))

        popen(f'git -C {self.temp} branch -M main')
        tested = gitstatus(self.temp)
        self.assertEqual(tested, ('main', None))

        ni(self.temp, 'file.txt')
        tested = gitstatus(self.temp)
        self.assertEqual(tested, ('main', '?1'))