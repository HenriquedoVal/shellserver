import os
import ctypes
import ctypes.wintypes
from typing import Any

__all__ = ['DiscardOutput', 'DirEntryWrapper', 'read_async']

FILE_FLAG_OVERLAPPED = 0x40000000
GENERIC_READ = 0x80000000
OPEN_EXISTING = 3


class DiscardOutput:
    def write(self, *args: Any, **kwargs: Any) -> None:
        return

    def flush(self) -> None:
        return


class OVERLAPPED(ctypes.Structure):
    _fields_ = [
        ('Internal', ctypes.c_ulong),
        ('InternalHigh', ctypes.c_ulong),
        ('Offset', ctypes.c_ulong),
        ('OffsetHigh', ctypes.c_ulong),
        ('hEvent', ctypes.c_void_p),
    ]


class DirEntryWrapper:
    counter = 0
    # os.DirEntry is a final class, can't be subclassed
    __slots__ = 'entry', 'name', 'path', 'relpath'

    def __init__(self, entry: os.DirEntry[Any], git_dir: str):
        self.entry = entry
        self.name = entry.name
        self.path = entry.path
        self.relpath = self.path.removeprefix(
            git_dir + '\\'
        ).replace('\\', '/', -1)
        DirEntryWrapper.counter += 1

    def stat(self) -> os.stat_result:
        try:
            return self.entry.stat()
        except OSError:
            return self.entry.stat(follow_symlinks=False)

    def is_file(self) -> bool:
        try:
            return self.entry.is_file()
        except OSError:
            return self.entry.is_file(follow_symlinks=False)

    def is_dir(self) -> bool:
        try:
            return self.entry.is_dir()
        except OSError:
            return self.entry.is_dir(follow_symlinks=False)

    def is_symlink(self) -> bool:
        return self.entry.is_symlink()


kernel32 = ctypes.windll.kernel32


def read_async(path: str, size: int) -> tuple[ctypes.Array[Any], OVERLAPPED]:
    """
    Thread will die if enters on 'alertable wait state'
    after this call.
    """
    file_handle = kernel32.CreateFileW(
        path,
        GENERIC_READ,
        0,
        None,
        OPEN_EXISTING,
        FILE_FLAG_OVERLAPPED,
        None,
    )

    buffer = ctypes.create_string_buffer(size)
    overlapped = OVERLAPPED()
    kernel32.ReadFileEx(
        file_handle,
        ctypes.byref(buffer),
        size,
        ctypes.byref(overlapped),
        0  # the callback
    )

    kernel32.CloseHandle(file_handle)
    return buffer, overlapped


PathMatchSpecW = ctypes.windll.shlwapi.PathMatchSpecW
PathMatchSpecW.argtypes = ctypes.wintypes.LPCWSTR, ctypes.wintypes.LPCWSTR
PathMatchSpecW.restype = ctypes.wintypes.BOOL
