from __future__ import annotations

"""
Low level operations on packfiles.
"""

import os
import zlib
from io import BytesIO
from collections import deque


class Packs:
    # {'path': (mtime, buffer)}
    bytes_io_cache: dict[str, tuple[float, BytesIO]] = {}
    # {'path': (mtime, {'hash': offset})}
    packs_index_cache: dict[str, tuple[float, dict[str, int]]] = {}

    def search_idx(
            self,
            idx_path: str,
            hash_: str,
            rt_offset: bool = False
    ) -> bool | int | None:
        """
        Searches given `idx_path` for `hash_`.
        param `idx_path`: The path of the pack index file.
        param `rt_offset`: Should this function return the offset of given file
                           if it's found?
        return: bool | int | None:
            If `rt_offset` is set to False, returns boolean value
            representing the presence of hash in the index.
            If `rt_offset` is set to True, returns the integer
            representing the offset of hash in the pack file.
            If `rt_offset` is set to True, but hash wasn't found in
            the index file, returns None.
        """

        mtime = os.stat(idx_path, follow_symlinks=False).st_mtime
        cache = self.packs_index_cache.get(idx_path)
        if cache and cache[0] == mtime:
            if not rt_offset:
                return hash_ in cache[1]
            return cache[1].get(hash_)

        hashes: deque[str] = deque()
        offsets: deque[int] = deque()

        with open(idx_path, 'rb') as file:

            file.seek(1028)
            total_files = int.from_bytes(file.read(4), 'big')

            file.seek(
                1032  # end of fanout_layer1
                # + 20 * files_before  # each will have 20 bytes
            )

            for _ in range(total_files):
                file_hash_bytes = file.read(20)
                file_hash = hex(
                    int.from_bytes(file_hash_bytes, 'big')
                )[2:].zfill(40)

                hashes.append(file_hash)

            file.seek(
                1032
                + 20 * total_files  # jump layer2
                + 4 * total_files  # jump layer3
            )

            for _ in range(total_files):
                offsets.append(int.from_bytes(file.read(4), 'big'))

        new_cache = dict(zip(hashes, offsets))
        self.packs_index_cache[idx_path] = mtime, new_cache

        if not rt_offset:
            return hash_ in new_cache
        return new_cache.get(hash_)

    def get_content_by_offset(
            self, pack_path: str, offset: int
    ) -> bytes | None:
        """
        Gets the content of object in given `pack_path` by its `offset`.
        param `pack_path`: The path to the pack file.
        param `offset`: The offset of the object.
        return: bytes | None: The content of the object,
                              None it is a delta object
        """

        file = self._get_buffer(pack_path)
        file.seek(offset)

        int_ = int.from_bytes(file.read(1), 'big')
        binary = f'{int_:b}'.zfill(8)
        type_ = binary[1:4]

        if type_ == '110':  # delta type
            return None

        obj_size = int_ & 0x0f
        bit_shift = 4
        msb = binary.startswith('1')
        # size = binary[4:]

        while msb:
            int_ = int.from_bytes(file.read(1), 'big')
            binary = f'{int_:b}'.zfill(8)
            obj_size |= (int_ & 0x7f) << bit_shift
            bit_shift += 7
            msb = binary.startswith('1')

        # why + 11? I don't know, it works
        return zlib.decompress(file.read(obj_size + 11))

    def get_idx_of_pack(self, pack: str) -> str:
        """
        return pack.removesuffix('pack') + 'idx'
        """
        return pack.removesuffix('pack') + 'idx'

    def _get_buffer(self, path: str) -> BytesIO:
        mtime = os.stat(path, follow_symlinks=False).st_mtime
        cache = self.bytes_io_cache.get(path)
        if cache and cache[0] == mtime:
            c = cache[1]
            c.seek(0)
            return c

        with open(path, 'rb') as raw:
            c = BytesIO(raw.read())

        self.bytes_io_cache[path] = mtime, c
        return c
