from __future__ import annotations

"""
Module for functions with high level of abstraction
and/or complexity.
"""

from fnmatch import fnmatchcase
# import multiprocessing as mp
import os
# import pickle
import sys
import time
from typing import Any

from . import medium

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEvent
    observer = Observer()
    observer.start()
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

n = '\n\n'
if '--git-verbose' not in sys.argv:
    # sending to stderr would break tests
    # and I have already messed with sys.stdout in server.py
    def print(*args: Any, **kwargs: Any) -> None:
        pass


class DirEntryWrapper:
    counter = 0
    # os.DirEntry is a final class, can't be subclassed
    __slots__ = 'entry', 'name', 'path', 'relpath'

    def __init__(self, entry: os.DirEntry[Any], git_dir: str):
        self.entry = entry
        self.name = entry.name.lower()
        self.path = entry.path.lower()
        self.relpath = self.path.removeprefix(
            git_dir + '\\'
        ).replace('\\', '/', -1)
        DirEntryWrapper.counter += 1

    def stat(self) -> os.stat_result:
        try:
            return self.entry.stat()
        except PermissionError:
            return self.entry.stat(follow_symlinks=False)

    def is_file(self) -> bool:
        try:
            return self.entry.is_file()
        except PermissionError:
            return self.entry.is_file(follow_symlinks=False)

    def is_dir(self) -> bool:
        try:
            return self.entry.is_dir()
        except PermissionError:
            return self.entry.is_dir(follow_symlinks=False)
        except BaseException:
            raise

    def is_symlink(self) -> bool:
        return self.entry.is_symlink()


class EventHandler:
    __slots__ = (
        'obj_ref',
        'git_dir_copy',
        'ignore_event_paths',
        'flag'
    )

    def __init__(self, obj_ref: High):
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
        # starts as True because the first read touches files
        self.flag = True

    def dispatch(self, event: FileSystemEvent) -> None:
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


# def _subprocess_entry_point() -> None:
#     sys.__stdout__.write('dual-proc\n')
#     obj = High()
#     while 1:
#
#         prot, *data = obj.receive()
#
#         if prot == 0:
#             obj.init(*data)
#         elif prot == 1:
#             obj.index_tracked, obj.packs_list = data
#         elif prot == 2:
#             obj.set_full_status(*data)
#         elif prot == 3:
#             obj.send(
#                 obj.untracked, obj.staged, obj.modified, obj.deleted,
#                 to=MAIN_PORT
#             )
#             obj.untracked = 0
#             obj.staged = 0
#             obj.modified = 0
#             obj.deleted = 0


class High(medium.Medium):

    __slots__ = (
        'git_dir', 'branch',
        'untracked', 'staged', 'modified', 'deleted',
        'use_cr',
        # 'sock', 'is_main', 'switch', 'dual'
    )

    def __init__(self, raise_subprocess: bool = False) -> None:
        self.untracked = 0
        self.staged = 0
        self.modified = 0
        self.deleted = 0

        self.use_cr = True

        #                       hash : tree_items_list
        self.objects_cache: dict[str, list[tuple[str, str, str]]] = {}
        self.event_handlers: dict[str, EventHandler] = {}
        self.final_result_cache: dict[
            str, tuple[float | None, str | None]] = {}
        self.dirs_mtimes: dict[str, float] = {}

        # self.dual = '--dual-proc' in sys.argv
        # if not self.dual:
        #     return
        #
        # self.switch = True
        # self.is_main = raise_subprocess
        #
        # self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # if not self.is_main:
        #     self.sock.bind(('localhost', SUBPROCESS_PORT))
        # else:
        #     mp.Process(
        #         target=_subprocess_entry_point,
        #         daemon=True
        #     ).start()
        #
        #     self.sock.bind(('localhost', MAIN_PORT))

    def init(self, git_dir: str, branch: str) -> None:
        self.git_dir = git_dir.lower()
        self.branch = branch

        if HAS_WATCHDOG and '--no-watchdog' not in sys.argv:
            handler = self.event_handlers.get(self.git_dir)
            if handler is not None:
                return

            handler = EventHandler(self)
            self.event_handlers[self.git_dir] = handler

            observer.schedule(
                handler, self.git_dir, recursive=True
            )

        # if self.dual and self.is_main:
        #     self.send(0, self.git_dir, branch, to=SUBPROCESS_PORT)

    def status(self) -> str | None:
        """
        Do a inline version of 'git status' without any use of git.
        return: str | None: String with the status, None if there's
                            nothing to report.
        """

        print('\nGIT_DIR:', self.git_dir)
        print('Branch', self.branch, end=n)

        if HAS_WATCHDOG and '--no-watchdog' not in sys.argv:
            cache = self.get_cached_result()
            # valid values are None or str
            if not isinstance(cache, int):
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

        # if self.dual:
        #     self.send(
        #         1, self.index_tracked, self.packs_list, to=SUBPROCESS_PORT
        #     )

        last_cmmt = self.get_last_commit_hash()

        self.set_full_status(
            self.git_dir, last_cmmt, exclude_content=exclude_content
        )

        # if self.dual:
        #     self.send(3, to=SUBPROCESS_PORT)
        #
        #     unt, sta, mod, del_ = self.receive()
        #     self.untracked += unt
        #     self.staged += sta
        #     self.modified += mod
        #     self.deleted += del_

        status_string = self.get_status_string(
            (self.untracked, self.staged, self.modified, self.deleted)
        )

        self.untracked = 0
        self.staged = 0
        self.modified = 0
        self.deleted = 0

        if HAS_WATCHDOG and '--no-watchdog' not in sys.argv:
            self.save_status_in_cache(status_string)

        print('Entries classified:', DirEntryWrapper.counter)

        return status_string

    def load_balancer(
        self,
        dir_path: str,
        tree_hash: str,
        relpath: str,
        fixed_prev: list[str],
        relative_prev: list[str]
    ) -> None:

        # if self.dual:
        #     self.switch = not self.switch
        #     if self.is_main and self.switch:
        #         self.send(
        #             2, dir_path, tree_hash, fixed_prev, relative_prev,
        #             to=SUBPROCESS_PORT
        #         )
        #         return

        self.set_full_status(
            dir_path, tree_hash, relpath, fixed_prev, relative_prev
        )

    def set_full_status(
        self,
        dir_path: str,
        tree_hash: str | None,
        relpath: str | None =  None,
        fixed_prev: list[str] | None = None,
        relative_prev: list[str] | None = None,
        *,
        exclude_content: list[str] | None = None,
    ) -> None:
        """
        param `dir_path`: Initial path from which scan begins.
                Will be used recursively
        param `tree_hash`: For recursive use only.
        """

        first_call = exclude_content is not None

        fixed, relative, clean_fixed = self.get_ignored_lists(
            dir_path, relpath, fixed_prev, relative_prev, exclude_content
        )

        if '*' in relative:
            return

        # list[tuple[git_type, hash, filename]]
        tree_items_list: list[tuple[str, str, str]] = []

        if first_call and tree_hash is not None:
            tree_items_list = self.get_tree_items(tree_hash, True)
        elif tree_hash:
            tree_items_list = self.get_tree_items(tree_hash)

        # dict[filename, hash]
        tracked_directories = {
            i[2]: i[1]
            for i in tree_items_list
            if i[0] == '40000'
        }

        try:
            directory = os.scandir(dir_path)

        # NotADir: if symlink (a file) points to a dir
        except (PermissionError, NotADirectoryError):
            return

        # need to count every file that is found in tree
        # because we don't have a direct relationship
        # between the index and the commit tree
        found_in_tree = 0
        for dir_entry in directory:

            file = DirEntryWrapper(dir_entry, self.git_dir)

            # 100755(exe) is file
            if file.is_file():
                if file.relpath in self.index_tracked:
                    found_in_tree += self.handle_tracked_file(
                        file, tree_items_list, file.relpath
                    )

                elif not self.is_ignored(file, fixed, relative):
                    print('Untracked:', file.relpath)
                    self.untracked += 1

            if file.is_dir():
                if file.name == '.git':
                    continue  # or pass

                elif file.name in tracked_directories:
                    found_in_tree += 1
                    tree_hash = tracked_directories[file.name]

                    self.load_balancer(
                        file.path,
                        tree_hash,
                        file.relpath,
                        fixed_prev=clean_fixed,
                        relative_prev=relative
                    )

                elif self.is_ignored(file, fixed, relative):
                    pass

                # check if dir is a submodule
                elif file.name in (
                        i[2] for i in
                        filter(lambda x: x[0] == '160000', tree_items_list)
                ):
                    found_in_tree += 1

                else:
                    _, file_present = self.handle_untracked_dir(
                        file.path, file.relpath, clean_fixed, relative
                    )

                    if file_present:
                        print('Untracked:', file.relpath)
                        self.untracked += 1

        # endfor
        self.deleted += len(tree_items_list) - found_in_tree

    def handle_tracked_file(
        self,
        file: DirEntryWrapper,
        tree_items_list: list[tuple[str, str, str]],
        relpath: str
    ) -> int:
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

        # use_cr: interchangeably switch the use of crlf
        file_hash = self.get_hash_of_file(file.path, self.use_cr)
        file_hash_in_tree = item[1]

        if file_hash_in_tree == file_hash:
            return local_found_in_tree

        elif file_hash_in_tree == self.get_hash_of_file(
                file.path, not self.use_cr, True
        ):
            self.use_cr = not self.use_cr
            return local_found_in_tree

        print('Modified:', relpath)
        self.modified += 1
        return local_found_in_tree

    def handle_untracked_dir(
        self,
        dir_path: str,
        relpath: str,
        fixed_prev: list[str],
        relative_prev: list[str]
    ) -> tuple[int, bool]:
        """
        Handles when `set_full_status` finds untracked directory.
        param `dir_path`: The path of the untracked directory.
        """
        fixed, relative, clean_fixed = self.get_ignored_lists(
            dir_path, relpath, fixed_prev, relative_prev
        )

        if '*' in relative:
            return 0, False

        try:
            directory = os.scandir(dir_path)
        except (PermissionError, NotADirectoryError):
            return 0, False

        sub_dir = []
        for file in directory:
            if file.name == '.git':
                directory.close()
                return 0, False
            sub_dir.append(DirEntryWrapper(file, self.git_dir))

        file_present = False
        staged_flag = 0
        marked_dirs_to_classify: list[DirEntryWrapper] = []
        for sub_file in sub_dir:

            if sub_file.relpath in self.index_tracked:
                print('Staged:', sub_file.relpath)
                self.staged += 1
                staged_flag += 1
                file_present = True

            elif self.is_ignored(
                sub_file, fixed, relative
            ):
                continue

            elif sub_file.is_dir():
                ret = self.handle_untracked_dir(
                    sub_file.path, sub_file.relpath, clean_fixed, relative
                )

                staged_flag += ret[0]
                child_file_present = ret[1]

                if child_file_present:
                    file_present = True
                    marked_dirs_to_classify.append(sub_file)
            else:
                file_present = True

        if staged_flag:  # reiterate searching for untracked
            for sub_file in sub_dir:
                if (
                    sub_file.is_file()
                    and sub_file.relpath not in self.index_tracked
                    and not self.is_ignored(
                        sub_file, fixed, relative
                    )
                ):
                    print('Untracked:', sub_file.relpath)
                    self.untracked += 1

            for sub_file in marked_dirs_to_classify:
                print('Untracked:', sub_file.relpath)
                self.untracked += 1

            file_present = False

        return staged_flag, file_present

    def get_tree_items(
        self, hash_: str, is_cmmt: bool = False
    ) -> list[tuple[str, str, str]]:
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

    def is_ignored(
        self,
        file: DirEntryWrapper,
        fixed: list[str],
        relative: list[str]
    ) -> bool:
        is_dir = file.is_dir()
        for pattern in relative:
            if pattern[-1] == '/' and not is_dir:
                continue
            if fnmatchcase(
                file.name + '/' if pattern[-1] == '/' else file.name,
                pattern
            ):
                return True

        for pattern in fixed:
            if pattern[-1] == '/' and not is_dir:
                continue
            if fnmatchcase(
                file.relpath + '/' if pattern[-1] == '/' else file.relpath,
                pattern
            ):
                return True

        return False

    def get_cached_result(self) -> int | str | None:
        cache = self.final_result_cache.get(self.git_dir)
        mtime = self.dirs_mtimes.get(self.git_dir)

        if cache and mtime == cache[0]:
            result: str | None = cache[1]
            print('Gotten from cache:', result)
            return result

        print(f'No cache. {cache=}; {mtime=}')
        return 0

    def save_status_in_cache(self, status: str | None) -> None:
        observer.event_queue.join()
        # dont care if it's None
        mtime = self.dirs_mtimes.get(self.git_dir)
        self.final_result_cache[self.git_dir] = mtime, status
        self.event_handlers[self.git_dir].flag = False
        print('Cache saved')

    # def send(self, *data, to) -> None:
    #     actual_msg = pickle.dumps(data, protocol=5)
    #
    #     while actual_msg[50_000:]:
    #         msg_slice = b'1' + actual_msg[:50_000]
    #         self.sock.sendto(msg_slice, ('localhost', to))
    #         actual_msg = actual_msg[50_000:]
    #
    #     msg_slice = b'0' + actual_msg
    #
    #     self.sock.sendto(msg_slice, ('localhost', to))
    #
    # def receive(self) -> bytes:
    #     actual_msg = b''
    #     msg_slice = self.sock.recv(50_000)
    #
    #     while msg_slice[0] == b'1':
    #         actual_msg += msg_slice[1:]
    #         msg_slice = self.sock.recv(50_000)
    #
    #     actual_msg += msg_slice[1:]
    #
    #     return pickle.loads(actual_msg)
