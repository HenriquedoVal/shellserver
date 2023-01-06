import os
import random
import string
import subprocess
import tempfile
import unittest

from .__init__ import gitstatus
from . import low
from . import medium
from . import packs
from . import high


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
        cls.temp = tempfile.mkdtemp(prefix='shellserver_tests-')
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
        tested = low.get_info_packs_content(self.temp)
        self.assertEqual(tested, [])

    def test_empty_get_gitignore_content(self):
        tested = low.get_gitignore_content(self.temp)
        self.assertEqual(tested, [])

        text = 'some text'
        with open(self.temp + '/.gitignore', 'w') as f:
            print(text, file=f)
        tested = low.get_gitignore_content(self.temp)
        self.assertEqual(tested, [text])

    def test_empty_get_last_commit_loose(self):
        branch = low.get_branch_on_head(self.temp)
        tested = low.get_last_commit_loose(self.temp, branch)
        self.assertIsNone(tested)

    def test_empty_get_info_refs_content(self):
        tested = low.get_info_refs_content(self.temp)
        self.assertEqual(tested, [])

    def test_empty_get_exclude_content(self):
        tested = low.get_exclude_content(self.temp)
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
        tested = low.get_content_by_hash_loose(self.temp, 'any')
        self.assertIsNone(tested)

    def test_empty_get_tree_hash_from_commit(self):
        # supose and cmmt obj
        tree_hash = b'0123456789abcdf'
        cmmt_obj = b'may be more things tree ' + tree_hash + b'\n'
        tested = low.get_tree_hash_from_commit(cmmt_obj)
        self.assertEqual(tested, tree_hash.decode())

    def test_empty_get_status_string(self):
        sts = (0, 0, 0, 0)
        tested = low.get_status_string(sts)
        self.assertIsNone(tested)

        sts = (1, 0, 0, 0)
        tested = low.get_status_string(sts)
        self.assertEqual(tested, '?1')

        sts = (0, 1, 0, 0)
        tested = low.get_status_string(sts)
        self.assertEqual(tested, '+1')

        sts = (0, 0, 1, 0)
        tested = low.get_status_string(sts)
        self.assertEqual(tested, 'm1')

        sts = (0, 0, 0, 1)
        tested = low.get_status_string(sts)
        self.assertEqual(tested, 'x1')

        sts = (1, 1, 1, 1)
        tested = low.get_status_string(sts)
        self.assertEqual(tested, '?1 +1 m1 x1')

        sts = (1, 0, 1, 0)
        tested = low.get_status_string(sts)
        self.assertEqual(tested, '?1 m1')

        sts = (0, 1, 0, 1)
        tested = low.get_status_string(sts)
        self.assertEqual(tested, '+1 x1')

    def test_empty_exists_head(self):
        tested = low.exists_head(self.temp)
        path = os.path.join(self.temp, '.git/HEAD')
        local = os.path.exists(path)
        self.assertEqual(tested, local)

    def test_empty_parse_git_status(self):
        tested = low.parse_git_status(self.temp)
        # test_get_gitignore_content created .gitignore
        self.assertEqual(tested, '??1')


class TestGitstatusLowLoose(unittest.TestCase):
    """
    Tests for low module with git repo with files.
    """

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_tests-')
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
        branch = low.get_branch_on_head(self.temp)
        tested = low.get_last_commit_loose(self.temp, branch)
        master = os.path.join(self.temp, '.git/refs/heads/master')
        with open(master) as file:
            local = file.read()
        self.assertEqual(tested, local.strip())

    def test_loose_get_info_refs_content(self):
        # should only exists if there are packed files
        tested = low.get_info_refs_content(self.temp)
        self.assertEqual(tested, [])

    '''
    def test_loose_get_exclude_content(self):
        # no need to retest

    def test_loose_build_filtered_patterns(self):
        # no need to retest
    '''

    def test_loose_get_hash_of_file(self):
        file_hash = low.get_hash_of_file(self.temp + '/file.txt')
        git_hash = popen(
            f'git -C {self.temp} hash-object file.txt'
        ).strip().decode()
        self.assertEqual(file_hash, git_hash)

        file_hash = low.get_hash_of_file(
            self.temp + '/file_cr.txt'
        )
        git_hash = popen(
            f'git -C {self.temp} hash-object file_cr.txt'
        ).strip().decode()
        self.assertEqual(file_hash, git_hash)

    def test_loose_get_content_by_hash_loose(self):
        file_hash = low.get_hash_of_file(self.temp + '/file.txt')
        tested = low.get_content_by_hash_loose(self.temp, file_hash)
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
        tested = low.parse_git_status(self.temp)
        self.assertEqual(tested, '')


class TestGitstatusLowPacked(unittest.TestCase):
    """
    Tests for low module with git repo with packed files.
    """

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_tests-')
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
        branch = low.get_branch_on_head(self.temp)
        tested = low.get_last_commit_loose(self.temp, branch)
        self.assertIsNone(tested)

    def test_packed_get_info_refs_content(self):
        tested = low.get_info_refs_content(self.temp)
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
        file_hash = low.get_hash_of_file(self.temp + '/file.txt')
        tested = low.get_content_by_hash_loose(self.temp, file_hash)
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
        tested = low.parse_git_status(self.temp)
        self.assertEqual(tested, '')


class TestGitstatusMediumEmpty(unittest.TestCase):
    """
    Tests for medium module with just initialized git repo.
    """

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_tests-')
        popen(f'git init {cls.temp}')

    @classmethod
    def tearDownClass(cls):
        os.system(f'rmdir /s /q {cls.temp}')

    def test_empty_get_packs(self):
        tested = medium.get_packs(self.temp)
        self.assertEqual(tested, [])

    def test_empty_get_content_by_hash_packed(self):
        packs_list = medium.get_packs(self.temp)
        tested = medium.get_content_by_hash_packed('anyabcdf01234', packs_list)
        self.assertIsNone(tested)

    def test_empty_get_last_commit_packed(self):
        branch = low.get_branch_on_head(self.temp)
        tested = medium.get_last_commit_packed(self.temp, branch)
        self.assertIsNone(tested)

    def test_empty_get_last_commit(self):
        branch = low.get_branch_on_head(self.temp)
        tested = medium.get_last_commit_hash(self.temp, branch)
        self.assertIsNone(tested)


class TestGitstatusMediumLoose(unittest.TestCase):
    """
    Tests for medium module with git repo with files.
    """

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_tests-')
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
        branch = low.get_branch_on_head(self.temp)
        tested = medium.get_last_commit_hash(self.temp, branch)
        low_tested = low.get_last_commit_loose(self.temp, branch)
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
        tested = medium.get_index_tracked(self.temp)

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
        cls.temp = tempfile.mkdtemp(prefix='shellserver_tests-')
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
        os.system(f'rmdir /s /q {cls.temp}')

    def test_packed_get_packs(self):
        packs = os.path.join(self.temp, '.git/objects/pack')

        local = [packs + '\\' + i
                 for i in os.listdir(packs)
                 if i.endswith('pack')]
        tested = medium.get_packs(self.temp)
        self.assertEqual(tested, local)

    def test_packed_get_content_by_hash_packed(self):
        packs_list = medium.get_packs(self.temp)
        file_hash = low.get_hash_of_file(self.temp + '/file.txt')
        tested = medium.get_content_by_hash_packed(file_hash, packs_list)
        local = popen(f'git -C {self.temp} cat-file -p {file_hash}')
        self.assertIn(local, tested)

    def test_packed_get_last_commit_packed(self):
        # I can't test this with a git background
        branch = low.get_branch_on_head(self.temp)
        tested = medium.get_last_commit_packed(self.temp, branch)
        refs = low.get_info_refs_content(self.temp)
        self.assertEqual(len(tested), 40)
        self.assertTrue(int(tested, 16))
        self.assertEqual(tested, tested.strip())
        self.assertIn(tested, refs[0])

    def test_packed_get_last_commit(self):
        branch = low.get_branch_on_head(self.temp)
        tested = medium.get_last_commit_hash(self.temp, branch)
        other_tested = medium.get_last_commit_packed(self.temp, branch)
        self.assertEqual(tested, other_tested)


class TestGitstatusPacksPacked(unittest.TestCase):
    """
    Tests for packs module with git repo with packed files.
    """
    # makes no sense testing for other cases

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_tests-')
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
        os.system(f'rmdir /s /q {cls.temp}')

    def test_search_idx(self):
        idx_path = packs.get_idx_of_pack(
            medium.get_packs(self.temp)[0]
        )
        file_hash = low.get_hash_of_file(self.temp + '/file.txt')
        filecr_hash = low.get_hash_of_file(self.temp + '/file_cr.txt')

        tested = packs.search_idx(idx_path, file_hash)
        self.assertTrue(tested)
        tested = packs.search_idx(idx_path, filecr_hash)
        self.assertTrue(tested)

    def test_get_content_by_offset(self):
        pack = medium.get_packs(self.temp)[0]
        idx_path = packs.get_idx_of_pack(pack)

        file_hash = low.get_hash_of_file(self.temp + '/file.txt')
        filecr_hash = low.get_hash_of_file(self.temp + '/file_cr.txt')

        file_off = packs.search_idx(idx_path, file_hash, rt_offset=True)
        filecr_off = packs.search_idx(idx_path, filecr_hash, rt_offset=True)

        file_obj = packs.get_content_by_offset(pack, file_off)
        filecr_obj = packs.get_content_by_offset(pack, filecr_off)

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
        cls.temp = tempfile.mkdtemp(prefix='shellserver_tests-')
        popen(f'git init {cls.temp}')
        cls.branch = low.get_branch_on_head(cls.temp)

    @classmethod
    def tearDownClass(cls):
        os.system(f'rmdir /s /q {cls.temp}')

    def test_status(self):
        self.assertIsNone(high.status(self.temp, self.branch))

        file_path = self.temp + '/file.txt'
        with open(file_path, 'w') as file:
            file.write(get_random_string())
        git = low.parse_git_status(self.temp)
        self.assertEqual(git, '??1')
        tested = high.status(self.temp, self.branch)
        self.assertEqual(tested, '?1')

        popen(f'git -C {self.temp} add .')
        git = low.parse_git_status(self.temp)
        self.assertEqual(git, 'A1')
        tested = high.status(self.temp, self.branch)
        self.assertEqual(tested, '+1')

        popen(f'git -C {self.temp} commit -m "some"')
        git = low.parse_git_status(self.temp)
        self.assertEqual(git, '')
        self.assertIsNone(high.status(self.temp, self.branch))

        with open(file_path, 'a') as file:
            file.write(get_random_string())
        git = low.parse_git_status(self.temp)
        self.assertEqual(git, 'M1')
        tested = high.status(self.temp, self.branch)
        self.assertEqual(tested, 'm1')

        os.remove(file_path)
        git = low.parse_git_status(self.temp)
        self.assertEqual(git, 'D1')
        tested = high.status(self.temp, self.branch)
        self.assertEqual(tested, 'x1')

        popen(f'git -C {self.temp} add .')
        popen(f'git -C {self.temp} commit -m "other"')
        git = low.parse_git_status(self.temp)
        self.assertEqual(git, '')
        self.assertIsNone(high.status(self.temp, self.branch))

        popen(f'git -C {self.temp} gc')
        git = low.parse_git_status(self.temp)
        self.assertEqual(git, '')
        self.assertIsNone(high.status(self.temp, self.branch))


class TestGitstatusHighStatusIgnore(unittest.TestCase):
    """
    Tests for high module with just initialized git repo.
    """

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_tests-')
        popen(f'git init {cls.temp}')
        cls.branch = low.get_branch_on_head(cls.temp)

    @classmethod
    def tearDownClass(cls):
        os.system(f'rmdir /s /q {cls.temp}')

    def test_status_ignore(self):
        gitignore = self.temp + '/.gitignore'
        with open(gitignore, 'w') as ignore:
            tested = high.status(self.temp, self.branch)
            self.assertEqual(tested, '?1')
            git = low.parse_git_status(self.temp)
            self.assertEqual(git, '??1')

            ni(self.temp, 'ignored_dir/some')
            ignore.write('ignored_dir\n')
            ignore.flush()
            tested = high.status(self.temp, self.branch)
            self.assertEqual(tested, '?1')
            git = low.parse_git_status(self.temp)
            self.assertEqual(git, '??1')

            ni(self.temp, 'other/ignored.txt')
            ignore.write('other/ign\n')
            ignore.flush()
            tested = high.status(self.temp, self.branch)
            self.assertEqual(tested, '?2')
            git = low.parse_git_status(self.temp)
            self.assertEqual(git, '??2')

            ignore.write('other/ign*\n')
            ignore.flush()
            tested = high.status(self.temp, self.branch)
            self.assertEqual(tested, '?1')
            git = low.parse_git_status(self.temp)
            self.assertEqual(git, '??1')

            ni(self.temp, 'some/ignored.txt')
            tested = high.status(self.temp, self.branch)
            self.assertEqual(tested, '?2')
            git = low.parse_git_status(self.temp)
            self.assertEqual(git, '??2')

            ignore.write('some\n')
            ignore.flush()
            tested = high.status(self.temp, self.branch)
            self.assertEqual(tested, '?1')
            git = low.parse_git_status(self.temp)
            self.assertEqual(git, '??1')

            ni(self.temp, 'a/b/c/d')
            tested = high.status(self.temp, self.branch)
            self.assertEqual(tested, '?2')
            git = low.parse_git_status(self.temp)
            self.assertEqual(git, '??2')

            ignore.write('a/**/d\n')
            ignore.flush()
            tested = high.status(self.temp, self.branch)
            self.assertEqual(tested, '?1')
            git = low.parse_git_status(self.temp)
            self.assertEqual(git, '??1')

            ni(self.temp, 'interrog.txt')
            ignore.write('inter???.txt')
            ignore.flush()
            tested = high.status(self.temp, self.branch)
            self.assertEqual(tested, '?1')
            git = low.parse_git_status(self.temp)
            self.assertEqual(git, '??1')


class TestGitstatusInit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='shellserver_tests-')

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
