from __future__ import annotations

"""
Module for functions with high level of abstraction
and/or complexity.
"""

import time
from fnmatch import fnmatchcase
# fnmatch.fnmatch would unnecessarily replace path.sep

from . import low
from . import medium

os = low.os  # os module
sys = medium.sys

n = '\n\n'
if '--git-verbose' not in sys.argv:
    # sending to stderr would break tests
    # and I have already messed with sys.stdout in server.py
    def print(*args, **kwargs):
        pass


class DirEntryWrapper:
    # os.DirEntry is a final class, can't be subclassed
    __slots__ = 'entry', 'name', 'path'

    def __init__(self, entry: os.DirEntry):
        self.entry = entry
        self.name = entry.name.lower()
        self.path = entry.path.lower()

    def stat(self):
        try:
            return self.entry.stat()
        except PermissionError:
            return self.entry.stat(follow_symlinks=False)

    def is_file(self):
        try:
            return self.entry.is_file()
        except PermissionError:
            return self.entry.is_file(follow_symlinks=False)

    def is_dir(self):
        try:
            return self.entry.is_dir()
        except PermissionError:
            return self.entry.is_dir(follow_symlinks=False)

    def is_symlink(self):
        return self.entry.is_symlink()


class FallbackError(Exception):
    pass


class High(medium.Medium):

    __slots__ = ('git_dir', 'branch', 'fixed', 'ignored', 'packs_list'
                 'untracked', 'staged', 'modified', 'deleted')

    def __init__(self) -> None:
        self.untracked = 0
        self.staged = 0
        self.modified = 0
        self.deleted = 0

    def init(self, git_dir, branch):
        self.git_dir = git_dir.lower()
        self.branch = branch

    def status(self):
        """
        Do a inline version of 'git status' without any use of git.
        return: str | None: String with the status, None if there's
                            nothing to report.
        """

        print('GIT_DIR:', self.git_dir)
        print('Branch', self.branch, end=n)

        try:
            self.set_index_tracked()
        except medium.IndexTooBigError:
            print("Index too big, Fallback.")
            raise FallbackError

        self.set_split_ignored()
        self.set_packs()
        print('Ignored patterns:')
        for pat in self.ignored:
            print(pat)
        for pat in self.fixed:
            print(pat)
        print()

        print('List of packfiles:')
        for pat in self.packs_list:
            print(pat)
        print()

        self.get_full_status(recurse_path=self.git_dir)

        status_string = self.get_status_string(
            (self.untracked, self.staged, self.modified, self.deleted)
        )

        self.untracked = 0
        self.staged = 0
        self.modified = 0
        self.deleted = 0

        return status_string

    def get_full_status(
        self,
        recurse_path,
        tree_hash=None
    ) -> tuple[int, int, int, int]:
        """
        Carries all the workload of getting a status.
        param `recurse_path`: For recursive use.
        param `tree_hash`: For recursive use.
        return: tuple: tuple of four integer numbers representing the number of
                        untracked, staged, modified and deleted files.
        """

        tree_items_list = []
        # will happen only in very first call
        if tree_hash is None:
            last_cmmt = self.get_last_commit_hash()
            if last_cmmt is not None:
                res = self.get_tree_items(last_cmmt)
                if res is not None:
                    tree_items_list = res
                    print('Found:', *tree_items_list, sep='\n', end=n)
        # all recursive calls will fall here
        else:
            tree_items_list = self.get_tree_items_from_hash(tree_hash)

        try:
            directory = os.scandir(recurse_path)
        # if symlink (a file) points to a dir
        except (PermissionError, NotADirectoryError):
            return

        # index will have only the full path of blobs
        # trees have everything
        found_in_tree = 0
        for file in directory:

            file = DirEntryWrapper(file)

            relpath = file.path.removeprefix(
                self.git_dir + '\\'
            ).replace('\\', '/', -1)

            # 100755(exe) is file
            if file.is_file() and relpath in self.index_tracked:
                found_in_tree += self.handle_tracked_file(
                    file, tree_items_list, relpath
                )

            elif any(fnmatchcase(file.name, pattern)
                     for pattern in self.ignored):
                pass
            elif any(fnmatchcase(
                    relpath + '/' if pattern.endswith('/') else relpath,
                    pattern) for pattern in self.fixed):
                pass

            elif file.is_file():  # and relpath not in index
                print('Untracked:', relpath)
                self.untracked += 1

            elif file.name == '.git':
                continue

            # check if dir is a submodule
            elif file.name in (
                    i[2] for i in
                    filter(lambda x: x[0] == '160000', tree_items_list)
            ):
                found_in_tree += 1

            # if dir isn't in tree_items_list
            elif file.name not in (
                    i[2] for i in
                    filter(lambda x: x[0] == '40000', tree_items_list)
            ):
                # untrack must be setted only if any children is not ignored
                result = self.handle_untracked_dir(file.path)
                if result:
                    print('Untracked:', relpath)
                    self.untracked += result

            # is_dir and is in tree
            else:
                found_in_tree += 1

                # filter entries with type == 40000
                trees = filter(lambda x: x[0] == '40000', tree_items_list)
                file_name_tuple = filter(lambda x: x[2] == file.name, trees)
                item_tuple = tuple(file_name_tuple)
                tree_hash = item_tuple[0][1]

                self.get_full_status(
                    file.path,
                    tree_hash
                )

        # endfor
        self.deleted += len(tree_items_list) - found_in_tree

    def handle_tracked_file(self, file, tree_items_list, relpath):
        local_found_in_tree = 0

        # get the item or it's staged
        for item in tree_items_list:
            if item[2] == file.name:
                break
        else:
            print('Staged:', relpath, "isn't under a commit.")
            self.staged += 1
            return 0  # or local_found_in_tree

        local_found_in_tree = 1

        mtime = self.index_tracked[relpath]
        if file.stat().st_mtime != mtime:
            print('Modified:', relpath)
            self.modified += 1
            return local_found_in_tree

        file_hash = self.get_hash_of_file(file.path)
        file_hash_in_tree = item[1]

        if file_hash_in_tree == file_hash:
            os.utime(file.path, (time.time(), mtime))
            return local_found_in_tree
        elif file_hash_in_tree == self.get_hash_of_file(file.path,
                                                        use_cr=True):
            os.utime(file.path, (time.time(), mtime))
            return local_found_in_tree

        print('Modified:', relpath)
        self.modified += 1
        return local_found_in_tree

    def handle_untracked_dir(self, dir_path: str) -> int:
        # although it is untracked, files here can be staged
        """
        Handles when `get_full_status` finds untracked directory.
        param `dir_name`: The path of the untracked directory.
        return: int: 1 if there was at least one not ignored file in directory.
                     0 if there was none.
        """
        try:
            directory = os.scandir(dir_path)
        except (PermissionError, NotADirectoryError):
            return 0

        sub_dir = []
        for file in directory:
            if file.name == '.git':
                return 0
            sub_dir.append(DirEntryWrapper(file))

        # if sub_file is in tracked, dont flag untracked dir
        staged_flag = False
        for sub_file in sub_dir:
            sub_relpath = sub_file.path.removeprefix(
                self.git_dir + '\\'
            ).replace('\\', '/', -1)

            if sub_relpath in self.index_tracked:
                print('Staged:', sub_relpath)
                self.staged += 1
                staged_flag = True

        if staged_flag:
            return 0

        local_untracked = 0
        for sub_file in sub_dir:
            if sub_file.is_dir():
                local_untracked += self.handle_untracked_dir(sub_file.path)

            if local_untracked:
                return 1

            if sub_file.is_file():
                if any(fnmatchcase(sub_file.name, pattern)
                       for pattern in self.ignored):
                    continue

                sub_relpath = sub_file.path.removeprefix(
                    self.git_dir + '\\'
                ).replace('\\', '/', -1)

                if any(fnmatchcase(
                        sub_relpath + '/'
                        if pattern.endswith('/') else sub_relpath,
                        pattern) for pattern in self.fixed):
                    continue
                return 1

        return 0

    def get_tree_items(self, last_cmmt: str) -> list | None:
        """
        Gets the last commit tree itens (type, hash and filename).
        param `last_cmmt`: The hash of the last commit.
        return: list | None: list of tuples with the type, hash and filenames,
                    None if tree is empty.
        """

        last_cmmt_obj = self.get_content_by_hash_loose(last_cmmt)
        if last_cmmt_obj is None:
            last_cmmt_obj = self.get_content_by_hash_packed(last_cmmt)

        if last_cmmt_obj is None:
            print("Couldn't get last commit object. Fallback.")
            raise FallbackError

        tree_hash = self.get_tree_hash_from_commit(last_cmmt_obj)
        print('Last commit tree hash:', tree_hash)

        from_pack = False
        tree_obj = self.get_content_by_hash_loose(tree_hash)
        if tree_obj is None:
            from_pack = True
            tree_obj = self.get_content_by_hash_packed(tree_hash)

        if tree_obj is None:
            print("Couldn't get last commit tree. Fallback.")
            raise FallbackError

        # there is a tree object but the git worktree is empty.
        if not tree_obj:
            return

        return self.parse_tree_object(tree_obj, from_pack)

    def get_tree_items_from_hash(self, tree_hash: str) -> list:
        """
        Gets the tree itens searching for its hash.
        param `tree_hash`: The hash of tree.
        return: list: list of tuples with the type, hash and filenames.
        """
        from_pack = False
        tree_obj = self.get_content_by_hash_loose(tree_hash)
        print('Searching loose', tree_hash)

        if tree_obj is None:
            from_pack = True
            tree_obj = self.get_content_by_hash_packed(tree_hash)
            print('Searching packed', tree_hash)

        if tree_obj is None:
            print('Not found. Fallback.')
            raise FallbackError

        tree_items_list = self.parse_tree_object(tree_obj, from_pack)
        print('Found:', *tree_items_list, sep='\n', end=n)

        return tree_items_list
