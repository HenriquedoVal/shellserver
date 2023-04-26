from __future__ import annotations

"""
Module for functions with high level of abstraction
and/or complexity.
"""

import ctypes
import io
import multiprocessing as mp
import os
import pickle
import time

from collections import deque
from mmap import mmap
from multiprocessing.shared_memory import SharedMemory
from typing import Any

from . import base
from . import plugins
from . import utils

OS_CPU_COUNT = os.cpu_count() or 1
n = '\n\n'


class EventHandler:
    __slots__ = (
        'obj_ref',
        'flag',
    )

    def __init__(self, obj_ref: High):
        self.obj_ref = obj_ref

        # flags that dispatch has already been called
        # will be reseted by High obj
        # starts as True because the first read touches files
        self.flag = True

    def dispatch(self, event: plugins.FileSystemEvent) -> None:
        if self.flag:
            return
        if event.is_directory:
            return
        self.obj_ref.output.write(f'{event}\n')

        self.flag = True
        self.obj_ref.dirs_mtimes[self.obj_ref.git_dir] = time.time()


class FallbackError(Exception):
    pass


class MemFlag:
    EMPTY = b'\x00'
    INIT = b'\xf1'
    STATUS = b'\xf2'
    TURN = b'\xf3'
    COLLECT = b'\xf4'
    WORKER_RES = b'\xf5'
    QUIT = b'\xf6'
    ERROR = b'\xf7'


def _workers_entry_point() -> None:
    obj = High(_is_worker=True)
    obj.worker_mainloop()


class High(base.Base):

    # dropped __slots__

    def __init__(
            self,
            *,
            multiproc: bool = False,
            workers: int = OS_CPU_COUNT - 1,
            linear: bool = False,
            read_async: bool = False,
            fallback: bool = True,
            watchdog: bool = True,
            output: io.TextIOWrapper | utils.DiscardOutput | None = None,
            _is_worker: bool = False,
            **kwargs,
    ) -> None:

        # config
        self.linear = linear
        self.read_async = read_async
        self.fallback = fallback
        self.watchdog = watchdog

        self.output: io.TextIOWrapper | utils.DiscardOutput
        if not isinstance(output, io.TextIOWrapper) or output is None:
            self.output = utils.DiscardOutput()
        else:
            self.output = output

        self.untracked = 0
        self.staged = 0
        self.modified = 0
        self.deleted = 0
        self.use_cr = True
        # {hash : tree_items_list}
        self.objects_cache: dict[str, list[tuple[str, str, str]]] = {}

        self.event_handlers: dict[str, EventHandler] = {}
        self.final_result_cache: dict[
            str, tuple[float | None, str | None]] = {}
        self.dirs_mtimes: dict[str, float] = {}

        self.files_readden: deque[tuple[ctypes.Array[Any], str]] = deque()

        self.mp_main = multiproc
        self.multiproc = (multiproc and workers) or _is_worker
        self.raised_exception = False

        if not self.multiproc:
            return

        self.workers = workers
        self.switch = 0
        self.orders_sent = 0

        self.shm = SharedMemory(
            name='shellserver_shared_memory',
            create=multiproc,
            size=1024 * 1024 * 2
        )

        assert isinstance(self.shm.buf.obj, mmap)
        self.mmap = self.shm.buf.obj

        if multiproc:
            for _ in range(workers):
                mp.Process(
                    target=_workers_entry_point, daemon=True
                ).start()

        if not self.mp_main:
            self.proc_num = int(mp.current_process().name[-1])

    def init(self, git_dir: str, branch: str) -> None:
        self.git_dir = git_dir.lower()
        self.branch = branch

        if self.multiproc and not self.mp_main:
            return

        if self.multiproc:
            self.write_shm(self.git_dir, branch, flag=MemFlag.INIT)

        if plugins.HAS_WATCHDOG and self.watchdog:
            handler = self.event_handlers.get(self.git_dir)
            if handler is not None:
                return

            handler = EventHandler(self)
            self.event_handlers[self.git_dir] = handler

            plugins.observer.schedule(
                handler, self.git_dir, recursive=True
            )

    def status(self) -> str | None:
        """
        Only MainProcess will call this.
        Do a inline version of 'git status' without any use of git.
        return: str | None: String with the status, None if there's
                            nothing to report.
        """

        self.output.write(f'\nGIT_DIR: {self.git_dir}\n')
        self.output.write(f'Branch {self.branch}{n}')

        if plugins.HAS_WATCHDOG and self.watchdog:
            cache = self.get_cached_result()
            # valid values are None or str
            if not isinstance(cache, int):
                return cache

        try:
            self.set_index_tracked()
        except base.IndexTooBigError:
            self.output.write('Index too big, Fallback.\n')
            if self.multiproc and self.mp_main:
                self.main_collect()
            raise FallbackError

        self.output.write(f'Index len: {len(self.index_tracked)}\n')

        exclude_content = self.get_exclude_content()

        self.set_packs()
        self.output.write('List of packfiles:\n')
        for pat in self.packs_list:
            self.output.write(pat + '\n')
        self.output.write('\n')

        if self.multiproc:
            self.write_shm(
                self.index_tracked, self.packs_list, flag=MemFlag.STATUS
            )

        last_cmmt = self.get_last_commit_hash()

        self.set_full_status(
            self.git_dir, last_cmmt, exclude_content=exclude_content
        )

        if not self.linear and self.read_async:
            self.handle_files_readden_async()
            self.files_readden.clear()

        if self.multiproc:
            err = self.main_collect()
            if err:
                raise FallbackError

        status_string = self.get_status_string(
            (self.untracked, self.staged, self.modified, self.deleted)
        )

        self.untracked = 0
        self.staged = 0
        self.modified = 0
        self.deleted = 0

        if plugins.HAS_WATCHDOG and self.watchdog:
            self.save_status_in_cache(status_string)

        if not self.multiproc:
            self.output.write(
                'Entries classified: '
                f'{utils.DirEntryWrapper.counter}'
            )
        utils.DirEntryWrapper.counter = 0

        return status_string

    def load_balancer(
        self,
        dir_path: str,
        tree_hash: str,
        relpath: str,
        fixed_prev: list[str],
        relative_prev: list[str]
    ) -> None:

        if self.multiproc and self.mp_main:
            self.switch += 1

            if self.switch <= self.workers:
                self.write_shm(
                    self.switch, dir_path, tree_hash,
                    relpath, fixed_prev, relative_prev,
                    flag=MemFlag.TURN
                )
                self.orders_sent += 1
                return

        self.set_full_status(
            dir_path, tree_hash, relpath, fixed_prev, relative_prev
        )

    def set_full_status(
        self,
        dir_path: str,
        tree_hash: str | None,
        relpath: str | None = None,
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

        # [(file_type, hash, filename)]
        tree_items_list: list[tuple[str, str, str]] | None = []

        if first_call and tree_hash is not None:
            tree_items_list = self.get_tree_items(tree_hash, True)
        elif tree_hash:
            tree_items_list = self.get_tree_items(tree_hash)

        if tree_items_list is None:
            return

        self.deleted += len(tree_items_list)

        # {filename: hash}
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

        for dir_entry in directory:

            if self.raised_exception:
                break

            file = utils.DirEntryWrapper(dir_entry, self.git_dir)

            # 100755(exe) is file
            if file.is_file():
                if file.relpath in self.index_tracked:
                    self.handle_tracked_file(
                        file, tree_items_list, file.relpath
                    )

                elif not self.is_ignored(file, fixed, relative):
                    self.output.write(f'Untracked: {file.relpath}\n')
                    self.untracked += 1

            if file.is_dir() and file.name != '.git':
                self.handle_dir(
                    file, fixed, relative, clean_fixed,
                    tracked_directories, tree_items_list
                )

    def handle_dir(
        self,
        file: utils.DirEntryWrapper,
        fixed: list[str],
        relative: list[str],
        clean_fixed: list[str],
        tracked_directories: dict[str, str],
        tree_items_list: list[tuple[str, str, str]]
    ) -> None:

        if file.name in tracked_directories:
            self.deleted -= 1
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
            self.deleted -= 1

        else:
            _, file_present = self.handle_untracked_dir(
                file.path, file.relpath, clean_fixed, relative
            )

            if file_present:
                self.output.write(f'Untracked: {file.relpath}\n')
                self.untracked += 1

    def handle_tracked_file(
        self,
        file: utils.DirEntryWrapper,
        tree_items_list: list[tuple[str, str, str]],
        relpath: str
    ) -> None:
        # get the item or it's staged
        for item in tree_items_list:
            if item[2] == file.name:
                break
        else:
            self.output.write(
                f"Staged: {relpath} isn't under a commit.\n"
            )
            self.staged += 1
            return

        self.deleted -= 1

        mtime = self.index_tracked[relpath]
        st = file.stat()
        st_mtime, st_size = st.st_mtime, st.st_size
        if st_mtime != mtime:
            self.output.write(f'Modified: {relpath}\n')
            self.modified += 1
            return

        file_hash_in_tree = item[1]
        if not self.linear and self.read_async:
            buffer = utils.read_async(file.path, st_size)
            self.files_readden.append((buffer, file_hash_in_tree))
            return

        # use_cr: interchangeably switch the use of crlf
        file_hash = self.get_hash_of_file(file.path, self.use_cr)

        if file_hash_in_tree == file_hash:
            return

        elif file_hash_in_tree == self.get_hash_of_file(
            file.path, not self.use_cr, True
        ):
            self.use_cr = not self.use_cr
            return

        self.output.write(f'Modified: {relpath}\n')
        self.modified += 1
        return

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
            sub_dir.append(utils.DirEntryWrapper(file, self.git_dir))

        file_present = False
        staged_flag = 0
        marked_dirs_to_classify: list[utils.DirEntryWrapper] = []
        for sub_file in sub_dir:

            if sub_file.relpath in self.index_tracked:
                self.output.write(f'Staged: {sub_file.relpath}\n')
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
                    self.output.write(f'Untracked: {sub_file.relpath}\n')
                    self.untracked += 1

            for sub_file in marked_dirs_to_classify:
                self.output.write(f'Untracked: {sub_file.relpath}\n')
                self.untracked += 1

            file_present = False

        return staged_flag, file_present

    def get_tree_items(
        self, hash_: str, is_cmmt: bool = False
    ) -> list[tuple[str, str, str]] | None:
        """
        Gets the last commit tree itens (type, hash and filename).
        param `last_cmmt`: The hash of the last commit.
        return: list: list of tuples with the type, hash and filenames,
                      empty list if git tree is empty
        """

        tree_items_list = self.objects_cache.get(hash_)

        if tree_items_list is not None:
            self.output.write(f'Gotten cached object for hash {hash_}\n')
            for i in tree_items_list:
                self.output.write(f'{i}\n')
            self.output.write(n)
            return tree_items_list

        if is_cmmt:
            last_cmmt_obj = self.get_content_by_hash_loose(hash_)
            if last_cmmt_obj is None:
                last_cmmt_obj = self.get_content_by_hash_packed(hash_)

            if last_cmmt_obj is None:
                self.output.write(
                    "Couldn't get last commit object. Fallback.\n"
                )
                if not self.multiproc:
                    raise FallbackError
                else:
                    self.raised_exception = True
                    return None

            tree_hash = self.get_tree_hash_from_commit(last_cmmt_obj)
            self.output.write(f'Last commit tree hash: {tree_hash}\n')
        else:
            tree_hash = hash_

        from_pack = False
        tree_obj = self.get_content_by_hash_loose(tree_hash)
        self.output.write(f'Searching loose {tree_hash}\n')

        if tree_obj is None:
            from_pack = True
            tree_obj = self.get_content_by_hash_packed(tree_hash)
            self.output.write(f'Searching packed {tree_hash}\n')

        if tree_obj is None:
            self.output.write('Not found. Fallback.\n')

            self.untracked = 0
            self.staged = 0
            self.modified = 0
            self.deleted = 0

            if not self.multiproc:
                raise FallbackError
            else:
                self.raised_exception = True
                return None

        tree_items_list = []

        # there is a tree object but the git worktree is empty.
        if tree_obj:
            tree_items_list = self.parse_tree_object(tree_obj, from_pack)
            self.output.write('Found:\n')
            for i in tree_items_list:
                self.output.write(f'{i}\n')
            self.output.write(n)

        self.objects_cache[tree_hash] = tree_items_list

        return tree_items_list

    def is_ignored(
        self,
        file: utils.DirEntryWrapper,
        fixed: list[str],
        relative: list[str]
    ) -> bool:
        is_dir = file.is_dir()
        for pattern in relative:
            if pattern[-1] == '/' and not is_dir:
                continue
            if utils.PathMatchSpecA(
                (file.name + '/' if pattern[-1] == '/'
                    else file.name).encode(),
                pattern.encode()
            ):
                return True

        for pattern in fixed:
            if pattern[-1] == '/' and not is_dir:
                continue
            if utils.PathMatchSpecA(
                (file.relpath + '/' if pattern[-1] == '/'
                    else file.relpath).encode(),
                pattern.encode()
            ):
                return True

        return False

    def get_cached_result(self) -> int | str | None:
        cache = self.final_result_cache.get(self.git_dir)
        mtime = self.dirs_mtimes.get(self.git_dir)

        if cache and mtime == cache[0]:
            result: str | None = cache[1]
            self.output.write(f'Gotten from cache: {result}\n')
            return result

        self.output.write(f'No cache. {cache=}; {mtime=}\n')
        return 0

    def save_status_in_cache(self, status: str | None) -> None:
        plugins.observer.event_queue.join()
        # dont care if it's None
        mtime = self.dirs_mtimes.get(self.git_dir)
        self.final_result_cache[self.git_dir] = mtime, status
        self.event_handlers[self.git_dir].flag = False
        self.output.write('Cache saved\n')

    def handle_files_readden_async(self) -> None:
        # TODO: sync before going on, bug on busy cpu
        # maybe a lot of ReadFileEx calls?

        for buffer, hash_ in self.files_readden:
            content = buffer.raw
            file_hash = self.get_hash_of_file(
                content, self.use_cr, is_buf=True
            )

            if hash_ == file_hash:
                continue

            elif hash_ == self.get_hash_of_file(
                '', use_cr=not self.use_cr, use_prev_read=True
            ):
                self.use_cr = not self.use_cr
                continue

            self.modified += 1

    #
    # multiproc
    #

    #                 main                                             workers
    #      __________________________________________________ ___________________________  # noqa
    #      |                                                | |                         |  # noqa
    # shm: I init args S status args T set_full_status args C W . . . . W . . . . W . . .  # noqa
    #

    def main_collect(self) -> int:
        # avoid worker infinite loop
        pos = self.mmap.tell()
        self.mmap.seek(0)
        self.mmap.write(MemFlag.EMPTY)
        self.mmap.seek(pos)

        # collect
        self.mmap.write(MemFlag.COLLECT)
        err = self.main_get_result()
        if self.raised_exception:
            err = 1
        length = self.mmap.tell()

        kb = round(length / 1024, 1)
        self.output.write(f'Memory used: {kb}kb\n')

        # clear memory
        self.mmap.seek(0)
        self.mmap.write(b'\x00' * length)
        self.mmap.seek(0)

        self.switch = 0
        self.orders_sent = 0
        self.raised_exception = False

        return err

    def shm_get_flag(self) -> bytes:
        # TODO: implement semaphores
        pos = self.mmap.tell()
        flag = self.mmap.read(1)
        while flag == MemFlag.EMPTY:
            self.mmap.seek(pos)
            flag = self.mmap.read(1)
            time.sleep(4e-5)

        return flag

    def main_get_result(self) -> int:
        err = 0
        for _ in range(self.workers):  # orders_sent
            flag = self.shm_get_flag()
            if flag == MemFlag.ERROR:
                err = 1

            if err:
                self.mmap.read(8)
                continue

            self.untracked += int.from_bytes(
                self.mmap.read(2), byteorder='little'
            )
            self.staged += int.from_bytes(
                self.mmap.read(2), byteorder='little'
            )
            self.modified += int.from_bytes(
                self.mmap.read(2), byteorder='little'
            )
            # -32768 -> 32767
            self.deleted += int.from_bytes(
                self.mmap.read(2), 'little', signed=True
            )

        return err

    def write_shm(self, *objs: Any, flag: bytes) -> None:
        """One call for init, one by load_balancer"""
        pos = self.mmap.tell()
        written = 0
        self.mmap.read(1)

        for obj in objs:
            obj_bytes = pickle.dumps(obj, protocol=-1)
            length = len(obj_bytes)
            self.mmap.write(length.to_bytes(3, 'little'))
            self.mmap.write(obj_bytes)
            written += length + 3

        self.mmap.seek(pos)
        self.mmap.write(flag)
        self.mmap.seek(pos + written + 1)

    # workers only

    def worker_write_shm_result(self) -> None:
        self.mmap.read((self.proc_num - 1) * 9)

        if self.raised_exception:
            self.mmap.write(MemFlag.ERROR)
            return

        pos = self.mmap.tell()
        self.mmap.read(1)

        for i in (self.untracked, self.staged, self.modified):
            self.mmap.write(
                i.to_bytes(length=2, byteorder='little')
            )

        self.mmap.write(
            self.deleted.to_bytes(length=2, byteorder='little', signed=True)
        )

        self.mmap.seek(pos)
        self.mmap.write(MemFlag.WORKER_RES)

    def worker_init(self) -> None:
        for it in range(2):

            length = int.from_bytes(self.mmap.read(3), 'little')
            recv = pickle.loads(self.mmap.read(length))

            if it == 0:
                self.git_dir = recv
            elif it == 1:
                self.branch = recv

    def worker_status(self) -> None:
        for it in range(2):

            length = int.from_bytes(self.mmap.read(3), 'little')
            recv = pickle.loads(self.mmap.read(length))

            if it == 0:
                self.index_tracked = recv
            elif it == 1:
                self.packs_list = recv

    def worker_handle_turn(self) -> None:
        for it in range(6):

            length = int.from_bytes(self.mmap.read(3), 'little')
            recv = pickle.loads(self.mmap.read(length))

            if it == 0:
                turn = recv
                if turn != self.proc_num:
                    # exhaust loop to keep mmaps sync without pickling
                    for _ in range(5):
                        length = int.from_bytes(self.mmap.read(3), 'little')
                        self.mmap.read(length)
                    return

            elif it == 1:
                dir_path = recv
            elif it == 2:
                tree_hash = recv
            elif it == 3:
                relpath = recv
            elif it == 4:
                fixed_prev = recv
            elif it == 5:
                relative_prev = recv

        self.set_full_status(
            dir_path, tree_hash, relpath, fixed_prev, relative_prev
        )

    def worker_clear(self) -> None:
        self.untracked = 0
        self.staged = 0
        self.modified = 0
        self.deleted = 0
        self.raised_exception = False
        self.mmap.seek(0)
        self.output.flush()

    def worker_mainloop(self) -> None:
        while 1:
            flag = self.shm_get_flag()

            if flag == MemFlag.INIT:
                self.worker_init()
            elif flag == MemFlag.STATUS:
                self.worker_status()
            elif flag == MemFlag.TURN:
                self.worker_handle_turn()
            elif flag == MemFlag.COLLECT:
                self.worker_write_shm_result()
                self.worker_clear()
            elif flag == MemFlag.QUIT:
                return
            else:
                raise RuntimeError('Unreachable')
