"""
This is a mess.
It was built with a linear approach, avoindig repetitive
iterations for performance benefits in detriment of
a better readability.
"""

import os
import re

from . import low
from . import medium

n = '\n\n'


class FallbackError(Exception):
    pass


def status(git_dir: str, branch: str) -> str:
    """
    Higher level function that searches the whole directory in
    which git resides returning the count of untracked, staged,
    modified and deleted files.
    param `git_dir`: The directory that contains '.git'.
    return: tuple containing the count of untracked, staged,
           modified and deleted files
    """

    print('GIT_DIR:', git_dir)
    print('Branch', branch, end=n)

    ignored = low.get_exclude_content(git_dir)
    ignored += low.get_gitignore_content(git_dir)
    print('Raw content of ignored patterns:', *ignored, sep='\n', end=n)

    valid = low.get_valid_patterns(ignored)
    patterns = low.adapt_regex(valid)
    print('List of regular expressions to ignore:',
          *patterns, sep='\n', end=n)

    untracked, tracked = get_untracked_and_tracked(
        git_dir, patterns
    )
    print('Untracked:', untracked, end=n)
    print('List of tracked paths:', *tracked, sep='\n', end=n)

    res_paths = []
    res_hashes = []

    last_cmmt, loose = medium.get_last_commit(git_dir, branch)
    print('Last commit:', last_cmmt)
    print('Packed?', not loose, end=n)

    packs_list = medium.get_packs(git_dir)
    print('List of packfiles:', *packs_list, sep='\n', end=n)

    tree_items_list = get_tree_items(git_dir, branch, last_cmmt, packs_list)
    print('Commit tree:', *tree_items_list, sep='\n', end=n)

    recusively_build_tree(
        git_dir, res_paths, res_hashes,
        tree_items_list, packs_list, level_path=git_dir
    )

    staged, modified, deleted = confront_git_tracked(
        res_paths, res_hashes, tracked
    )

    status = low.stringfy_status((untracked, staged, modified, deleted))

    return status


def get_tree_items(git_dir, branch, last_cmmt, packs_list) -> str:

    last_cmmt_obj = low.get_content_by_hash_loose(git_dir, last_cmmt)
    loose = True
    if last_cmmt_obj is None:
        loose = False
        last_cmmt_obj = medium.get_content_by_hash_packed(
            last_cmmt, packs_list
        )

    if not last_cmmt_obj:
        print("Couldn't get last commit object. Fallback.")
        raise FallbackError

    print('Last commit is loose?', loose)

    tree_hash = low.get_tree_hash_from_commit(last_cmmt_obj)

    loose = True
    tree_obj = low.get_content_by_hash_loose(git_dir, tree_hash)
    if tree_obj is None:
        loose = False
        tree_obj = medium.get_content_by_hash_packed(tree_hash, packs_list)

    tree_items_list = parse_tree_object(tree_obj)
    print('Last commit tree is loose?', loose)

    return tree_items_list


def recusively_build_tree(
        git_dir: str,
        res_paths: list,
        res_hashes: list,
        tree_items_list: list,
        packs_list: list,
        level_path: str
) -> None:

    for item in tree_items_list:
        type_, hash_, filename = item
        full_path = os.path.abspath(level_path + '/' + filename)

        if type_ == '100644':
            res_paths.append(full_path)
            res_hashes.append(hash_)

        elif type_ == '40000':
            from_pack = False
            tree_obj = low.get_content_by_hash_loose(git_dir, hash_)
            print('Searching loose', hash_)

            if not tree_obj:
                from_pack = True
                tree_obj = medium.get_content_by_hash_packed(hash_, packs_list)
                print('Searching packed', hash_)

            if not tree_obj:
                print('Not found. Fallback.')
                raise FallbackError

            tree_items_list = parse_tree_object(tree_obj, from_pack)

            if tree_items_list:
                print('Found:', *tree_items_list, sep='\n', end=n)
                recusively_build_tree(
                    git_dir, res_paths, res_hashes,
                    tree_items_list, packs_list, full_path
                )


def confront_git_tracked(
    res_paths, res_hashes, tracked
) -> tuple[int, int, int]:

    staged = modified = deleted = 0

    for path, hash_ in zip(res_paths, res_hashes, strict=True):
        if path not in tracked:
            print(path, 'not in tracked.')
            deleted += 1

        elif (low.get_hash(path) == hash_
              or low.get_hash(path, use_cr=True) == hash_):
            pass

        else:
            print(path, 'has different sha1.')
            modified += 1

    for file in tracked:
        if file not in res_paths:
            print(file, 'is not associated with a commit.')
            staged += 1

    return staged, modified, deleted


def get_untracked_and_tracked(
    git_dir: str,
    patterns: list,
    index_content=None,
    recurse_path=None
) -> tuple[int, list[str]]:
    """
    Searches for every file in local repository for
    untracked files
    param `git_dir`: The str path of .git.
    param `patterns`: List of patters gotten from `get_ignored_patterns()`.
    param `index_content`: For recurse use.
    param `recurse_path`: For recurse use.
    return: tuple[int, list[str]]: A tuple containing the number of untracked
           files and a list of full paths of tracked files.
    """
    # Has to be just one function that does both works
    # for performance benefits

    tracked = []
    untracked = 0

    if recurse_path is None:
        recurse_path = git_dir

    if index_content is None:
        index_content = low.get_index_content(git_dir)

    re_funcs = (re.search, re.match)

    try:
        with os.scandir(recurse_path) as directory:
            for file in directory:

                path = os.path.relpath(
                    file.path, git_dir
                ).replace('\\', '/', -1)

                # must add slash so it can be matched
                path = '/' + path
                if file.is_dir():
                    path += '/'

                match = False
                for pat in patterns:
                    # if there is a '/' in pat[:-1] i want re.match
                    # but then we'll need to remove the first '/' from path
                    chk = int(bool(re.match('[^\^]*/.*', pat[:-1])))
                    fun = re_funcs[chk]
                    if fun(pat, path[chk:]):
                        match = True
                        break

                if match:
                    print(f"re.{fun.__name__}('{pat}') matches {path}")
                    continue

                path = path.removeprefix('/').removesuffix('/')

                if file.is_file() and path.encode() not in index_content:
                    untracked += 1
                    continue

                elif file.is_file() and path.encode() in index_content:
                    tracked.append(file.path)

                elif file.is_dir() and file.name != '.git':
                    untracked_aux, tracked_aux = get_untracked_and_tracked(
                        git_dir,
                        patterns,
                        index_content,
                        os.path.abspath(file.path)
                    )
                    untracked += untracked_aux
                    tracked += tracked_aux

                tracked = [i.removeprefix('/') for i in tracked]
    except OSError:
        pass

    return untracked, tracked


def parse_tree_object(
        data: bytes, from_pack: bool = False
) -> list[tuple[str, str, str]]:
    """
    Parses the content of a git tree object and returns a list
    of its values
    param `data`: The content decompressed of tree object
    return: list of tuples containing the type, hash and the filename
    """

    if not from_pack:
        if not data[data.index(b'\x00') + 1:]:
            return

        # first remove everything before first null byte
        start = data.index(b'\x00') + 1
    else:
        start = 0

    res = []

    while True:
        # cant split(b'\x00), hash might have it
        # cant split(' '), filename might have it
        stop = data.index(b'\x00', start)

        piece = data[start: stop]
        sep = piece.index(b' ')

        type_ = piece[:sep]
        filename = piece[sep + 1:]

        start = stop + 21  # next start

        hexa = data[stop + 1:start]
        hexa = f'{int.from_bytes(hexa):x}'.zfill(40)

        res.append((type_.decode(), hexa, filename.decode()))

        if not data[start + 1:]:
            break

    return res
