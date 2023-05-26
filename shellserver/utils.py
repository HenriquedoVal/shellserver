from __future__ import annotations

import ctypes
import json
import os
import pickle
import threading
import winreg
from ctypes import wintypes
from io import StringIO
from collections import OrderedDict

from .__init__ import CACHE_PATH, SEP


HIST_FILE = os.path.join(
    os.environ['APPDATA'],
    'Microsoft/Windows',
    'PowerShell/PSReadLine/ConsoleHost_history.txt'
)
BL_SUB_KEY = (
    'Software\\Microsoft\\Windows\\CurrentVersion\\CloudStore\\'
    'Store\\DefaultAccount\\Current\\'
    'default$windows.data.bluelightreduction.bluelightreductionstate\\'
    'windows.data.bluelightreduction.bluelightreductionstate'
)
SYS_THEME_SUB_KEY = (
    'SOFTWARE\\Microsoft\\Windows\\'
    'CurrentVersion\\Themes\\Personalize'
)
WT_SETTINGS_DEFAULT = os.path.join(
    os.environ['LOCALAPPDATA'],
    'Packages\\Microsoft.WindowsTerminal_8wekyb3d8bbwe',
    'LocalState\\settings.json'
)
WT_SETTINGS_PREVIEW = os.path.join(
    os.environ['LOCALAPPDATA'],
    'Packages\\Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe',
    'LocalState\\settings.json'
)
WT_SETTINGS_UNPACKAGED = os.path.join(
    os.environ['LOCALAPPDATA'],
    'Microsoft\\Windows Terminal\\settings.json'
)


version_dll = ctypes.windll.version


class VS_FIXEDFILEINFO(ctypes.Structure):
    _fields_ = [
        ("dwSignature", wintypes.DWORD),
        ("dwStrucVersion", wintypes.DWORD),
        ("dwFileVersionMS", wintypes.DWORD),
        ("dwFileVersionLS", wintypes.DWORD),
        ("dwProductVersionMS", wintypes.DWORD),
        ("dwProductVersionLS", wintypes.DWORD),
        ("dwFileFlagsMask", wintypes.DWORD),
        ("dwFileFlags", wintypes.DWORD),
        ("dwFileOS", wintypes.DWORD),
        ("dwFileType", wintypes.DWORD),
        ("dwFileSubtype", wintypes.DWORD),
        ("dwFileDateMS", wintypes.DWORD),
        ("dwFileDateLS", wintypes.DWORD),
    ]


def get_file_version(filename: str) -> str | None:

    # Get the file version information
    dwHandle = wintypes.DWORD()
    dwLen = version_dll.GetFileVersionInfoSizeW(
        filename, ctypes.byref(dwHandle)
    )
    if not dwLen:
        return

    lpData = ctypes.create_string_buffer(dwLen)
    success = version_dll.GetFileVersionInfoW(
        filename, dwHandle, dwLen, lpData
    )
    if not success:
        return

    pffi = ctypes.pointer(VS_FIXEDFILEINFO())
    uLen = wintypes.UINT(ctypes.sizeof(VS_FIXEDFILEINFO))
    success = version_dll.VerQueryValueW(
        lpData, '\\', ctypes.byref(pffi), ctypes.byref(uLen)
    )
    if not success:
        return

    dwFileVersionMS = pffi.contents.dwFileVersionMS
    dwFileVersionLS = pffi.contents.dwFileVersionLS
    dwFileVersion = (
        dwFileVersionMS >> 16,
        dwFileVersionMS & 0xFFFF,
        dwFileVersionLS >> 16,
        # dwFileVersionLS & 0xFFFF
    )
    return ".".join(map(str, dwFileVersion))


class DirCache:
    __slots__ = 'dirs', 'save_on_exit'

    # dirs = list[list[precedence: int, abs_path: str, short_path: str]]
    def __init__(self):
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, 'rb') as in_file:
                self.dirs = pickle.load(in_file)
            self._clear()
        else:
            self.dirs = []

            # Need to create file or cache will never save
            # if it doesn't exist.
            # Need to put something there or server might break
            # when pickle tries to read an empty file.
            with open(CACHE_PATH, 'wb') as in_file:
                pickle.dump([], in_file)

        self.save_on_exit = False  # New paths were added to cache?

    def add(self, path: str) -> None:
        for item in self.dirs:
            if item[1] == path:
                break
        else:
            out = path[path.rindex(SEP) + 1:].lower()
            if not out:
                out = path.strip(SEP).lower()

            self.dirs.append([0, path, out])

            # just want to set save_on_exit if it is false to start thread
            # that will capture WM_SAVE_YOURSELF
            if not self.save_on_exit:
                self.save_on_exit = True
                threading.Thread(target=self._signal_cap, daemon=True).start()

    def get(self, rel_path: str) -> str:
        for item in self.dirs:
            if item[2] == rel_path:
                return item[1]
        return ''

    def update_by_full_path(self, full_path: str) -> None:
        # get idx and item or return
        for idx, item in enumerate(self.dirs):
            if item[1] == full_path:
                break
        else:
            return

        # set every entry precedence with same last path name to zero
        last_path_name = item[2]
        idxs_with_same_last_path_name = [
            other_idx for other_idx, i in enumerate(self.dirs)
            if i[2] == last_path_name
        ]

        for other_idx in idxs_with_same_last_path_name:
            self.dirs[other_idx][0] = 0

        # update only given full_path to one
        self.dirs[idx][0] = 1

        self.save_on_exit = True

    def finish(self):
        self._clear()
        self._save()

    def sort(self) -> None:
        self.dirs.sort(key=lambda x: x[0], reverse=True)

    def _save(self) -> None:
        # if there were calls to clear the cache during this runtime
        if not os.path.exists(CACHE_PATH):
            return
        if self.save_on_exit:
            with open(CACHE_PATH, 'wb') as out:
                pickle.dump(self.dirs, out, protocol=5)

    def _clear(self) -> None:
        aux = [
            item for item in self.dirs
            if not os.path.exists(item[1])
        ]

        if aux:
            self.save_on_exit = True

        for item in aux:
            self.dirs.remove(item)

    def _signal_cap(self):
        import tkinter as tk

        def finish():
            self.finish()
            raise SystemExit

        root = tk.Tk()
        root.withdraw()
        root.protocol('WM_SAVE_YOURSELF', finish)
        root.mainloop()


class Dispatcher:
    """
    This class will hold the specifics convertions
    necessary to each shell, apply them and send
    data through socket.
    """
    __slots__ = 'addrs', 'funcs', 'buf_size'

    def __init__(self, buf_size: int):
        # afaik, udp header might be 20 or 40 bytes but none of these work
        # must be missing something because no value around it works
        self.buf_size = buf_size - 2000
        self.addrs = {}
        self.funcs = {'pwsh': self._pwsh_func}

    def register(self, addr: int, shell: str):
        self.addrs.update({addr: shell})

    def send_through(
        self, sock, data: str, addr: tuple[str, int], *, prepare=True
    ):

        shell = self.addrs.get(addr, 'pwsh')
        func = self.funcs.get(shell)

        if prepare and func is not None:
            data = func(data)

        while data[self.buf_size:]:
            msg = '1' + data[:self.buf_size]
            sock.sendto(msg.encode(), addr)
            data = data[self.buf_size:]

        msg = '0' + data

        sock.sendto(msg.encode(), addr)

    def _pwsh_func(self, data: str):
        return data.replace('$', '`$', -1)


def history_search(
    queries: list[str], width: int, height: int, opt: str = ''
) -> str:

    with open(HIST_FILE, 'r', encoding='utf-8') as history:
        content = history.read()

    content = content.splitlines()
    content = OrderedDict.fromkeys(content[-2::-1])
    height -= 4
    height = max(height, 5)
    res = StringIO()

    counter = 0
    printed = 0
    height_reached = False
    for item in content:

        # Checks the point when we're not printing anymore
        if not height_reached and counter >= height:
            printed = counter
            height_reached = True

        for query in queries:
            if 'c' not in opt:
                query, item = query.lower(), item.lower()

            if query not in item:
                continue

            # Check if isn't the first loop
            if counter and (not height_reached or 'a' in opt):
                res.write('\n')

            counter += 1
            if len(item) > width:
                counter += 1

            if not height_reached or 'a' in opt:
                res.write(
                    item.replace(query, f'\x1b[32m{query}\x1b[0m', -1)
                )
            break

    if height_reached and 'a' not in opt:
        res.write(' ' * 10 + f'\x1b[33m[and {counter - printed} more]\x1b[0m')

    return res.getvalue()


def _get_actual_value(subkey, name):

    read_handle_hkey = winreg.OpenKeyEx(
        winreg.HKEY_CURRENT_USER, subkey, 0, winreg.KEY_READ
    )

    actual_value = winreg.QueryValueEx(
        read_handle_hkey, name
    )[0]

    winreg.CloseKey(read_handle_hkey)

    return actual_value


def toggle_blue_light_reduction():
    # "translation" from:
    # https://github.com/inamozov/DisplayTest/blob/master/DisplayTest.cpp

    name = 'Data'
    value = bytearray(_get_actual_value(BL_SUB_KEY, name))

    on = value[18] == 21
    size = 41 if on else 43
    if on:
        for i in range(10, 15):
            if value[i] != 255:
                value[i] += 1
                break
        value[18] = 19
        for i in range(24, 22, -1):
            for j in range(i, size - 2):
                value[j] = value[j + 1]
    else:
        for i in range(10, 15):
            if value[i] != 255:
                value[i] += 1
                break
        value[18] = 21
        n = 0
        while n < 2:
            for i in range(size - 1, 23, -1):
                value[i] = value[i - 1]
            n += 1
        value[23] = 16
        value[24] = 0

    set_handle_hkey = winreg.OpenKeyEx(
        winreg.HKEY_CURRENT_USER, BL_SUB_KEY, 0, winreg.KEY_SET_VALUE
    )

    winreg.SetValueEx(
        set_handle_hkey, name, 0, winreg.REG_BINARY, value
    )
    winreg.CloseKey(set_handle_hkey)


def system_theme_change():
    name = "SystemUsesLightTheme"

    actual_value = _get_actual_value(SYS_THEME_SUB_KEY, name)

    target = 0 if actual_value == 1 else 1

    set_handle_hkey = winreg.OpenKeyEx(
        winreg.HKEY_CURRENT_USER, SYS_THEME_SUB_KEY, 0, winreg.KEY_SET_VALUE
    )

    winreg.SetValueEx(
        set_handle_hkey, name, 0, winreg.REG_DWORD, target
    )
    winreg.SetValueEx(
        set_handle_hkey, "AppsUseLightTheme", 0, winreg.REG_DWORD, target
    )

    winreg.CloseKey(set_handle_hkey)


def windows_terminal_change(config):

    for const in (
        WT_SETTINGS_DEFAULT,
        WT_SETTINGS_PREVIEW,
        WT_SETTINGS_UNPACKAGED
    ):
        if os.path.exists(const):
            path = const
            break
    else:
        return

    with open(path, 'r') as orig_file:
        file = json.load(orig_file)

    # settings should aways have profiles and defaults
    defaults = file.get('profiles').get('defaults')

    actual_scheme = defaults.get('colorScheme')
    if actual_scheme is None:
        name = "SystemUsesLightTheme"

        if _get_actual_value(SYS_THEME_SUB_KEY, name):  # is light?
            defaults['colorScheme'] = config.light_theme
        else:
            defaults['colorScheme'] = config.dark_theme

    elif actual_scheme == config.light_theme:
        defaults['colorScheme'] = config.dark_theme
    else:
        defaults['colorScheme'] = config.light_theme

    with open(path, 'w') as mod_file:
        json.dump(file, mod_file, indent=4)


def call_all_theme_funcs():
    system_theme_change()
    windows_terminal_change()
    toggle_blue_light_reduction()
