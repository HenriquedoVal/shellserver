from __future__ import annotations

"""
Module with functions considered of medium level of abstraction
(functions here calls low functions and/or its siblings).
"""

import sys

from . import low
from . import packs

os = low.os

try:
    from ssd_checker import is_ssd  # fail fast

    # pywin32 is dep of ssd_checker
    from pythoncom import CoInitialize

    from ctypes import windll
    import string
    import threading as th

    DRIVE_SSD_MAP = {}

    def populate(letter):
        CoInitialize()
        DRIVE_SSD_MAP[letter] = is_ssd(letter)

    bitmask = windll.kernel32.GetLogicalDrives()
    for letter in string.ascii_uppercase:
        if bitmask & 1:
            letter = letter.lower() + ':'
            th.Thread(
                target=populate, args=(letter,), daemon=True
            ).start()
        bitmask >>= 1

    HAS_SSD_CHECKER = True

except ImportError:
    HAS_SSD_CHECKER = False


class IndexTooBigError(Exception):
    pass


class Medium(low.Low, packs.Packs):
    git_dir: str
    branch: str
    index_tracked: tuple | dict[str, float]

    def set_packs(self) -> None:
        """
        Sets the `packs_list` attribute.
        return: None.
        """
        # info/packs is not needed
        pack_def_path = '.git/objects/pack'

        packs_list = self.get_info_packs_content()
        if packs_list:
            self.packs_list = [
                os.path.join(
                    self.git_dir, pack_def_path, i
                ) for i in packs_list
            ]
            return

        packs = os.path.join(self.git_dir, pack_def_path)
        if not os.path.exists(packs):
            self.packs_list = []
            return

        dir_ = os.scandir(packs)
        self.packs_list = [
            i.path for i in dir_ if i.name.endswith('.pack')
        ]

    def set_index_tracked(self) -> None:
        """
        Sets `index_tracked` attribute.
        Modified and simpler version of gin.
        https://github.com/sbp/gin
        return: None.
        """
        max_entries = 1000
        if HAS_SSD_CHECKER:
            for drive in DRIVE_SSD_MAP:
                if self.git_dir.startswith(drive):
                    # if SSD: 2500 if HDD: 1000
                    max_entries = 2500 if DRIVE_SSD_MAP[drive] else 1000
                    break

        index_path = os.path.join(self.git_dir, '.git/index')
        if not os.path.exists(index_path):
            self.index_tracked = tuple()
            return

        with open(index_path, 'rb') as f:

            def read_str_until(delim):
                ret = []
                while True:
                    b = f.read(1)
                    if b == '' or b == delim:
                        return b"".join(ret).decode()

                    ret.append(b)

            constant = f.read(4)
            version = int.from_bytes(f.read(4), 'big')
            if constant != b'DIRC' or version not in (2, 3):
                self.index_tracked = tuple()

            entries = int.from_bytes(f.read(4), 'big')
            res = {}

            for entry in range(entries):
                f.read(8)
                # converted to float to keep type consistence
                mtime = float(int.from_bytes(f.read(4), 'big'))
                mtime += int.from_bytes(f.read(4), 'big') / 1000000000
                f.read(44)

                flags = int.from_bytes(f.read(2), 'big')
                namelen = flags & 0xfff
                extended = flags & (0b0100_0000 << 8)

                entrylen = 62

                if extended:
                    f.read(2)
                    entrylen += 2

                if namelen < 0xfff:
                    name = f.read(namelen).decode()
                    entrylen += namelen
                else:
                    name = read_str_until('\x00')
                    entrylen += 1

                res[name.lower()] = mtime

                give_up = '--wait' not in sys.argv
                if give_up and len(res) > max_entries:
                    raise IndexTooBigError

                padlen = (8 - (entrylen % 8)) or 8
                f.read(padlen)

        self.index_tracked = res

    def get_split_ignored(
        self, raw_ignored, prepend=None
    ) -> tuple[list, list]:
        """
        Returns two lists in this order: fixed and relative.
        """
        raw_ignored = [
            i.strip().lower()
            for i in raw_ignored
            if not i.strip().startswith('#')
        ]

        relative = [
            i for i in raw_ignored
            if '/' not in i[:-1]
        ]

        if prepend is None:
            fixed = [i.lstrip('/') for i in raw_ignored if i not in relative]

        else:
            relpath = prepend.removeprefix(
                self.git_dir + '\\'
            ).replace('\\', '/', -1)

            fixed = [
                f'{relpath}/{i}' for i in raw_ignored if i not in relative
            ]

        return fixed, relative

    def get_content_by_hash_packed(self, hash_: str) -> bytes | None:
        """
        Gets the content of an object by its hash in any packfiles present.
        param `hash_`: The hash to be searched in packfiles.
        return: bytes | None: The content of object, None if it was not Found.
        """
        content = None

        for pack in self.packs_list:
            idx = self.get_idx_of_pack(pack)
            offset = self.search_idx(idx, hash_, rt_offset=True)
            if offset is None:
                continue
            content = self.get_content_by_offset(pack, offset)
            if content:
                break

        return content

    def get_last_commit_packed(self) -> str | None:
        """
        Gets the last commit's hash of a git repo by a packed perspective.
        return: str | None: String of the last commit hash, None if there's no
                            last commit packed.
        """
        info_refs = self.get_info_refs_content()
        last_commt_hash = None

        for line in info_refs:
            a, b = line.strip().split()
            if b == f'refs/heads/{self.branch}':
                last_commt_hash = a
                break

        return last_commt_hash

    def get_last_commit_hash(self) -> str | None:
        """
        Gets the last commit's hash of a git repo.
        return: str | None: String of the last commit hash, None if there's no
                            last commit.
        """
        last_cmmt = self.get_last_commit_loose()

        if last_cmmt is None:
            last_cmmt = self.get_last_commit_packed()

        return last_cmmt
