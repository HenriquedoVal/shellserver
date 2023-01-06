"""
Module with functions considered of medium level of abstraction
(functions here calls low functions and/or its siblings).
"""

from . import low
from . import packs

os = low.os


def get_packs(git_dir) -> list[str]:
    """
    Get the path of packfiles.
    param `git_dir`: The directory in which .git resides.
    return: list: The paths of packfiles.
    """
    # info/packs is not needed
    pack_def_path = '.git/objects/pack'

    packs_list = low.get_info_packs_content(git_dir)
    if not packs_list:
        packs = os.path.join(git_dir, pack_def_path)
        if not os.path.exists(packs):
            return []
        packs_list = os.scandir(packs)
        return [i.path for i in packs_list if i.name.endswith('.pack')]

    packs_list = [
        os.path.join(
            git_dir, pack_def_path, i
        ) for i in packs_list
    ]

    return packs_list


def get_content_by_hash_packed(hash_: str, packs_list: list) -> bytes | None:
    """
    Get the content of an object by its hash in any packfiles present.
    param `hash_`: The hash to be searched in packfiles.
    return: bytes | None: The content of object, None if it was not Found.
    """
    content = None

    for pack in packs_list:
        idx = packs.get_idx_of_pack(pack)
        offset = packs.search_idx(idx, hash_, rt_offset=True)
        if offset is None:
            continue
        content = packs.get_content_by_offset(pack, offset)
        if content:
            break

    return content


def get_last_commit_packed(git_dir: str, branch: str) -> str | None:
    """
    Gets the last commit's hash of a git repo by a packed perspective.
    param `git_dir`: The path of .git.
    return: str | None: String of the last commit hash, None if there's no
                        last commit packed.
    """
    info_refs = low.get_info_refs_content(git_dir)
    last_commt_hash = None

    for line in info_refs:
        a, b = line.strip().split()
        if b == f'refs/heads/{branch}':
            last_commt_hash = a
            break

    return last_commt_hash


def get_last_commit_hash(git_dir: str, branch: str) -> str | None:
    """
    Gets the last commit's hash of a git repo.
    param `git_dir`: The path of .git.
    return: str | None: String of the last commit hash, None if there's no
                        last commit.
    """
    last_cmmt = low.get_last_commit_loose(git_dir, branch)

    if last_cmmt is None:
        last_cmmt = get_last_commit_packed(git_dir, branch)

    return last_cmmt


def get_index_tracked(git_dir: str) -> list[str] | None:
    """
    Modified and simpler version of gin.
    https://github.com/sbp/gin
    param `git_dir`: The path of .git.
    return: list[str] | None: List containing the paths of tracked files,
                              None if index file is unsuported.
    """
    index_path = os.path.join(git_dir, '.git/index')
    if not os.path.exists(index_path):
        return []

    with open(index_path, 'rb') as f:

        def readStrUntil(delim):
            ret = []
            while True:
                b = f.read(1)
                if b == '' or b == delim:
                    return b"".join(ret).decode("utf-8", "replace")

                ret.append(b)

        constant = f.read(4)
        version = int.from_bytes(f.read(4))
        if constant != b'DIRC' or version not in (2, 3):
            return

        entries = int.from_bytes(f.read(4))
        res = []

        for entry in range(entries):
            f.read(60)

            flags = int.from_bytes(f.read(2))
            namelen = flags & 0xfff
            extended = flags & (0b0100_0000 << 8)

            entrylen = 62

            if extended:
                f.read(2)
                entrylen += 2

            if namelen < 0xfff:
                name = f.read(namelen).decode("utf-8", "replace")
                entrylen += namelen
            else:
                name = readStrUntil('\x00')
                entrylen += 1

            res.append(name)

            padlen = (8 - (entrylen % 8)) or 8
            f.read(padlen)

    return res


def get_split_ignored(git_dir: str) -> tuple[list[str], list[str]]:
    """
    Gets the content of both 'exclude' and '.gitignore' files,
    splits the content by patterns of full paths and relative paths.
    param `git_dir`: The path of .git.
    return: tuple[list[str], list[str]]: tuple of full path patterns and
                relative path patterns.
    """
    raw_ignored = low.get_exclude_content(git_dir)
    raw_ignored += low.get_gitignore_content(git_dir)

    # raw_ignored will become the the 'fixed', return[0]
    every_time = []
    counter = 0
    while counter < len(raw_ignored):
        if raw_ignored[counter].strip().startswith('#'):
            del raw_ignored[counter]
            continue

        if '/' not in raw_ignored[counter]:
            every_time.append(raw_ignored[counter])
            del raw_ignored[counter]
            continue

        counter += 1

    return raw_ignored, every_time
