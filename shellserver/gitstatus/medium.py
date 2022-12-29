import os

from . import low
from . import packs


def get_packs(git_dir):
    packs_list = low.get_info_packs_content(git_dir)
    packs_list = [
        os.path.join(
            git_dir, '.git/objects/pack', i
        ) for i in packs_list
    ]
    return packs_list


def get_content_by_hash_packed(hash_, packs_list) -> bytes:
    content = None

    for pack in packs_list:
        idx = low.get_idx_of_pack(pack)
        offset = packs.search_idx(idx, hash_, rt_offset=True)
        if offset is None:
            continue
        content = packs.get_content_by_offset(pack, offset)
        if content:
            break

    return content


def get_last_commit_packed(git_dir, branch):
    info_refs: list = low.get_info_refs_content(git_dir)

    if not info_refs:
        return

    last_commt_hash = ''
    for line in info_refs:
        a, b = line.strip().split()
        if b == f'refs/heads/{branch}':
            last_commt_hash = a

    return last_commt_hash


def get_last_commit(git_dir, branch):
    loose = True
    last_cmmt = low.get_last_commit_loose(git_dir, branch)

    if not last_cmmt:
        last_cmmt = get_last_commit_packed(git_dir, branch)
        loose = False

    return last_cmmt, loose
