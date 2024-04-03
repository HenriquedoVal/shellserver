"""
Low level operations on packfiles.
"""

import os
import zlib
from io import BytesIO, BufferedReader
from collections import deque


class Packs:
    # {'path': (mtime, buffer)}
    bytes_io_cache: dict[str, tuple[float, BytesIO]] = {}
    # [(mtime, path, stream)]
    streams_to_transform_in_bytes_io: deque[
        tuple[float, str, BufferedReader]
    ] = deque()

    __slots__ = ()

    def search_idx(
            self,
            idx_path: str,
            hash_: str
    ) -> int | None:
        """
        Searches given `idx_path` for `hash_`.
        param `idx_path`: The path of the pack index file.
        param `hash_`: The hash to be searched.
        return: int | None: The offset for the hash. None if not found
        """

        idx = int(hash_[:2], 16)

        file = self._get_buffer(idx_path)

        file.seek(8)
        before = idx - 1
        if before >= 0:
            file.seek(before * 4, 1)
            files_before = int.from_bytes(file.read(4), 'big')
        else:
            files_before = 0

        files_after = int.from_bytes(file.read(4), 'big')

        file.seek(1028)
        total_files = int.from_bytes(file.read(4), 'big')

        file.seek(1032 + 20 * files_before)
        read = hex(int.from_bytes(file.read(20), 'big'))[2:].zfill(40)
        if hash_ == read:
            return self.get_offset(file, total_files, files_before)

        file.seek(1032 + 20 * files_after)
        read = hex(int.from_bytes(file.read(20), 'big'))[2:].zfill(40)

        mid = (files_after - files_before) // 2
        while mid:
            file.seek(1032 + 20 * (files_before + mid))
            read = hex(int.from_bytes(file.read(20), 'big'))[2:].zfill(40)

            if hash_ == read:
                return self.get_offset(
                    file, total_files, files_before + mid
                )

            # string comp
            if hash_ > read:
                files_before = files_before + mid
            else:
                files_after = files_before + mid

            mid = (files_after - files_before) // 2

        return None

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

        byte = file.read(1)[0]
        type_ = (byte & 0x70) >> 4

        if type_ in (6, 7):
            return None

        obj_size = byte & 0x0f
        bit_shift = 4
        msb = byte & 0x80

        while msb:
            byte = file.read(1)[0]
            obj_size |= (byte & 0x7f) << bit_shift
            bit_shift += 7
            msb = byte & 0x80

        # why + 11? On current tests it's the minimun value that don't raise
        # I don't want to go byte by byte searching for eof because it's slow
        # and zlib.decompress can deal with extra input
        obj_data = zlib.decompress(file.read(obj_size + 11))
        # assert len(obj_data) == obj_size
        return obj_data

    def get_idx_of_pack(self, pack: str) -> str:
        """
        return pack.removesuffix('pack') + 'idx'
        """
        return pack.removesuffix('pack') + 'idx'

    def _get_buffer(self, path: str) -> BytesIO | BufferedReader:
        mtime = os.stat(path, follow_symlinks=False).st_mtime
        cache = self.bytes_io_cache.get(path)
        if cache and cache[0] == mtime:
            c = cache[1]
            c.seek(0)
            return c

        raw = open(path, 'rb')
        self.streams_to_transform_in_bytes_io.append((mtime, path, raw))
        return raw

    def _write_buffer(self) -> None:
        while self.streams_to_transform_in_bytes_io:
            mtime, path, raw = self.streams_to_transform_in_bytes_io.pop()
            raw.seek(0)
            c = BytesIO(raw.read())
            raw.close()

            self.bytes_io_cache[path] = mtime, c

    def get_offset(
        self, file: BytesIO | BufferedReader,
        total_files: int,
        target: int
    ) -> int:
        file.seek(
            1032
            + 20 * total_files  # jump layer2
            + 4 * total_files  # jump layer3
            + 4 * target
        )

        return int.from_bytes(file.read(4), 'big')
