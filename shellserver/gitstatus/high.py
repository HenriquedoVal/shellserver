from __future__ import annotations

"""
Module for functions with high level of abstraction
and/or complexity.
"""

from fnmatch import fnmatchcase
import time

from . import low
from . import medium

try:
    from watchdog.observers import Observer
    observer = Observer()
    observer.start()
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

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

    def __init__(self, entry):
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


class EventHandler:
    __slots__ = 'obj_ref', 'git_dir_copy', 'ignore_event_paths', 'flag'

    def __init__(self, obj_ref):
        self.obj_ref = obj_ref
        self.git_dir_copy = obj_ref.git_dir
        self.ignore_event_paths = (
            '.git\\index.lock',
            '.git\\index',
            '.git\\config',
            '.git\\packed-refs',
            '.git\\shallow'
        )

        # flags that dispatch has already been called
        # will be reseted by High obj
        self.flag = False

    def dispatch(self, event) -> None:
        if self.flag:
            return

        if event.is_directory:
            return

        if event.src_path.endswith(self.ignore_event_paths):
            return

        print(event)
        self.flag = True
        self.obj_ref.dirs_mtimes[self.git_dir_copy] = time.time()


class FallbackError(Exception):
    pass


class High(medium.Medium):

    __slots__ = (
        'git_dir', 'branch',
        'untracked', 'staged', 'modified', 'deleted',
    )

    def __init__(self) -> None:
        self.untracked = 0
        self.staged = 0
        self.modified = 0
        self.deleted = 0

        self.objects_cache: dict[str, list] = {}
        self.event_handlers: dict[str, EventHandler] = {}
        self.final_result_cache: dict[str, tuple[float, str]] = {}
        self.dirs_mtimes: dict[str, float] = {}

    def init(self, git_dir, branch) -> None:
        self.git_dir = git_dir.lower()
        self.branch = branch

        if HAS_WATCHDOG:
            handler = self.event_handlers.get(self.git_dir)
            if handler is not None:
                return

            handler = EventHandler(self)
            self.event_handlers[self.git_dir] = handler

            observer.schedule(
                handler, self.git_dir, recursive=True
            )

    def status(self) -> str | None:
        """
        Do a inline version of 'git status' without any use of git.
        return: str | None: String with the status, None if there's
                            nothing to report.
        """

        print('\nGIT_DIR:', self.git_dir)
        print('Branch', self.branch, end=n)

        if HAS_WATCHDOG:
            cache = self.get_cached_result()
            # valid values are None or str
            if cache != 0:
                return cache

        try:
            self.set_index_tracked()
        except medium.IndexTooBigError:
            print("Index too big, Fallback.")
            raise FallbackError

        print('Index len:', len(self.index_tracked))

        exclude_content = self.get_exclude_content()

        self.set_packs()
        print('List of packfiles:')
        for pat in self.packs_list:
            print(pat)
        print()

        self.get_full_status(self.git_dir, exclude_content=exclude_content)

        status_string = self.get_status_string(
            (self.untracked, self.staged, self.modified, self.deleted)
        )

        self.untracked = 0
        self.staged = 0
        self.modified = 0
        self.deleted = 0

        if HAS_WATCHDOG:
            self.save_status_in_cache(status_string)

        print(end=n)

        return status_string

    def get_full_status(
        self,
        recurse_path,
        tree_hash=None,
        exclude_content=None,
        fixed_prev=None,
        relative_prev=None
    ) -> None:
        """
        param `recurse_path`: Initial path from which scan begins.
                              Will be used recursively
        param `tree_hash`: For recursive use only.
        """

        raw_ignored = self.get_gitignore_content(recurse_path)
        if exclude_content is not None:
            raw_ignored += exclude_content

        fixed, relative = self.get_split_ignored(raw_ignored)
        if fixed_prev is not None and relative_prev is not None:
            fixed += fixed_prev
            relative += relative_prev

        if '*' in relative:
            return

        tree_items_list: list[tuple[str, str, str]] = []
        # will happen only in very first call
        if tree_hash is None:
            last_cmmt = self.get_last_commit_hash()
            if last_cmmt is not None:
                tree_items_list = self.get_tree_items(last_cmmt, True)
        # all recursive calls will fall here
        else:
            tree_items_list = self.get_tree_items(tree_hash)

        try:
            directory = os.scandir(recurse_path)

        # NotADir: if symlink (a file) points to a dir
        except (PermissionError, NotADirectoryError):
            return

        # need to count every file that is found in tree
        # because we don't have a direct relationship
        # between the index and the commit tree
        found_in_tree = 0
        for dir_entry in directory:

            file = DirEntryWrapper(dir_entry)

            relpath = file.path.removeprefix(
                self.git_dir + '\\'
            ).replace('\\', '/', -1)

            # 100755(exe) is file
            if file.is_file():
                if relpath in self.index_tracked:
                    found_in_tree += self.handle_tracked_file(
                        file, tree_items_list, relpath
                    )

                elif self.is_ignored(file, relpath, fixed, relative):
                    pass

                else:
                    print('Untracked:', relpath)
                    self.untracked += 1

            if file.is_dir():
                if file.name == '.git':
                    continue

                elif self.is_ignored(file, relpath, fixed, relative):
                    pass

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
                    self.handle_untracked_dir(file.path, fixed, relative)

                # is_dir and is in tree
                else:
                    found_in_tree += 1

                    # filter entries with type == 40000
                    trees = filter(lambda x: x[0] == '40000', tree_items_list)
                    matching_item = filter(lambda x: x[2] == file.name, trees)
                    item_tuple = tuple(matching_item)
                    tree_hash = item_tuple[0][1]

                    self.get_full_status(
                        file.path,
                        tree_hash,
                        fixed_prev=fixed,
                        relative_prev=relative
                    )

        # endfor
        self.deleted += len(tree_items_list) - found_in_tree

    def handle_tracked_file(self, file, tree_items_list, relpath) -> int:
        """Classifies the file, returns if file was found_in_tree"""
        local_found_in_tree = 0

        # get the item or it's staged
        for item in tree_items_list:
            if item[2] == file.name:
                break
        else:
            print('Staged:', relpath, "isn't under a commit.")
            self.staged += 1
            return local_found_in_tree

        local_found_in_tree = 1

        mtime = self.index_tracked[relpath]
        if file.stat().st_mtime != mtime:
            print('Modified:', relpath)
            self.modified += 1
            return local_found_in_tree

        file_hash = self.get_hash_of_file(file.path)
        file_hash_in_tree = item[1]

        if file_hash_in_tree == file_hash:
            return local_found_in_tree
        elif file_hash_in_tree == self.get_hash_of_file(file.path,
                                                        use_cr=True):
            return local_found_in_tree

        print('Modified:', relpath)
        self.modified += 1
        return local_found_in_tree

    def handle_untracked_dir(self, dir_path: str, fixed_prev, relative_prev) -> None:
        # although it is untracked, files here can be staged
        """
        Handles when `get_full_status` finds untracked directory.
        param `dir_path`: The path of the untracked directory.
        """
        raw_ignored = self.get_gitignore_content(dir_path)

        fixed, relative = self.get_split_ignored(raw_ignored)
        if fixed_prev is not None and relative_prev is not None:
            fixed += fixed_prev
            relative += relative_prev

        if '*' in relative:
            return

        try:
            directory = os.scandir(dir_path)
        except (PermissionError, NotADirectoryError):
            return

        sub_dir = []
        for file in directory:
            if file.name == '.git':
                directory.close()
                return
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

        if staged_flag:  # reiterate searching for untracked
            for sub_file in sub_dir:
                sub_relpath = sub_file.path.removeprefix(
                    self.git_dir + '\\'
                ).replace('\\', '/', -1)

                if (
                    sub_relpath not in self.index_tracked
                    and not self.is_ignored(
                        sub_file, sub_relpath, fixed, relative
                    )
                ):
                    print('Untracked:', sub_relpath)
                    self.untracked += 1

        for sub_file in sub_dir:
            if sub_file.is_dir():
                self.handle_untracked_dir(sub_file.path, fixed, relative)

        if not staged_flag:
            for sub_file in sub_dir:
                if sub_file.is_file():
                    sub_relpath = sub_file.path.removeprefix(
                        self.git_dir + '\\'
                    ).replace('\\', '/', -1)

                    if self.is_ignored(sub_file, sub_relpath, fixed, relative):
                        continue

                    print('Untracked:', file.path)  # parent file
                    self.untracked += 1
                    return

    def get_tree_items(self, hash_: str, is_cmmt=False) -> list:
        """
        Gets the last commit tree itens (type, hash and filename).
        param `last_cmmt`: The hash of the last commit.
        return: list: list of tuples with the type, hash and filenames,
                      empty list if git tree is empty
        """

        tree_items_list = self.objects_cache.get(hash_)

        if tree_items_list is not None:
            print(f'Gotten cached object for hash {hash_}',
                  *tree_items_list, sep='\n', end=n)
            return tree_items_list

        if is_cmmt:
            last_cmmt_obj = self.get_content_by_hash_loose(hash_)
            if last_cmmt_obj is None:
                last_cmmt_obj = self.get_content_by_hash_packed(hash_)

            if last_cmmt_obj is None:
                print("Couldn't get last commit object. Fallback.")
                raise FallbackError

            tree_hash = self.get_tree_hash_from_commit(last_cmmt_obj)
            print('Last commit tree hash:', tree_hash)
        else:
            tree_hash = hash_

        from_pack = False
        tree_obj = self.get_content_by_hash_loose(tree_hash)
        print('Searching loose', tree_hash)

        if tree_obj is None:
            from_pack = True
            tree_obj = self.get_content_by_hash_packed(tree_hash)
            print('Searching packed', tree_hash)

        if tree_obj is None:
            print('Not found. Fallback.')

            self.untracked = 0
            self.staged = 0
            self.modified = 0
            self.deleted = 0

            raise FallbackError

        tree_items_list = []

        # there is a tree object but the git worktree is empty.
        if tree_obj:
            tree_items_list = self.parse_tree_object(tree_obj, from_pack)
            print('Found:', *tree_items_list, sep='\n', end=n)

        self.objects_cache[tree_hash] = tree_items_list

        return tree_items_list

    def is_ignored(self, file, relpath, fixed, relative) -> bool:
        if any(fnmatchcase(file.name, pattern) for pattern in relative):
            return True

        for pattern in fixed:
            if fnmatchcase(
                relpath + '/' if pattern.endswith('/') else relpath, pattern
            ):
                fixed.remove(pattern)
                return True

        return False

    def get_cached_result(self) -> int | str | None:
        cache = self.final_result_cache.get(self.git_dir)
        mtime = self.dirs_mtimes.get(self.git_dir)

        if cache and mtime == cache[0]:
            result = cache[1]
            # status might be None or str
            print('Gotten from cache:', result)
            return result

        print(f'No cache. {cache=}; {mtime=}')
        return 0

    def save_status_in_cache(self, status: str | None) -> None:
        mtime = self.dirs_mtimes.get(self.git_dir)
        self.final_result_cache[self.git_dir] = mtime, status
        self.event_handlers.get(self.git_dir).flag = False
        print('Cache saved')
