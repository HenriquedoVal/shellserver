from __future__ import annotations

"""
Low level operations on packfiles.
"""

import mmap
import zlib


# dict[str path, mmap.mmap]
MAPPED_CACHE = {}


def _get_buffer(path) -> mmap.mmap:
    if path in MAPPED_CACHE and not MAPPED_CACHE[path].closed:
        return MAPPED_CACHE[path]

    with open(path, 'rb') as raw:
        m = mmap.mmap(raw.fileno(), 0, access=mmap.ACCESS_READ)

    MAPPED_CACHE[path] = m
    return m


class Packs:
    def search_idx(
            self,
            idx_path: str,
            hash_: str,
            rt_offset=False
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

        layer1_idx = int(hash_[:2], 16) - 1
        found = False

        file = _get_buffer(idx_path)

        if layer1_idx > 0:
            file.seek(8 + 4 * layer1_idx)
            files_before = int.from_bytes(file.read(4), 'big')
        else:
            files_before = 0

        file.seek(1028)
        total_files = int.from_bytes(file.read(4), 'big')

        file.seek(
            1032  # end of fanout_layer1
            + 20 * files_before  # each will have 20 bytes
        )

        while not found:
            file_hash_bytes = file.read(20)
            file_hash = hex(
                int.from_bytes(file_hash_bytes, 'big')
            )[2:].zfill(40)

            if hash_ == file_hash:
                found = True
                break

            elif int(file_hash[:2], 16) > layer1_idx + 1:
                break

            elif file.tell() >= 1032 + 20 * total_files:
                break

            files_before += 1

        if not rt_offset:
            return found

        if found:
            file.seek(
                1032
                + 20 * total_files  # jump layer2
                + 4 * total_files  # jump layer3
                + 4 * files_before
            )
            return int.from_bytes(file.read(4), 'big')

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

        file = _get_buffer(pack_path)
        file.seek(offset)

        int_ = int.from_bytes(file.read(1), 'big')
        binary = f'{int_:b}'.zfill(8)
        type_ = binary[1:4]
        obj_size = int_ & 0x0f
        bit_shift = 4

        if type_ == '110':  # delta type
            return

        msb = binary.startswith('1')
        # size = binary[4:]

        while msb:
            int_ = int.from_bytes(file.read(1), 'big')
            binary = f'{int_:b}'.zfill(8)
            obj_size |= (int_ & 0x7f) << bit_shift
            bit_shift += 7
            msb = binary.startswith('1')

        return zlib.decompress(file.read(obj_size + 11))

    def get_idx_of_pack(self, pack: str) -> str:
        """
        return pack.removesuffix('pack') + 'idx'
        """
        return pack.removesuffix('pack') + 'idx'
