"""
This is a mess.
It was built with a linear approach, avoindig repetitive
iterations for performance benefits in detriment of
a better readability.
"""

import os
import re

from . import low


def get_untracked_count_and_tracked_path(
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
    # Have to be just one function that does both works
    # for performance benefits

    tracked = []
    untracked = 0

    if recurse_path is None:
        recurse_path = git_dir

    if index_content is None:
        if low.exists_index(git_dir):
            index_path = os.path.join(git_dir, '.git/index')
            with open(index_path, 'rb') as index:
                index_content = index.read()
        else:
            # any value that nothing will be True to contain
            index_content = b''

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
                        break  # noqa

                if match:
                    continue  # noqa

                # remove slashes
                path = path.removeprefix('/').removesuffix('/')

                if file.is_file() and path.encode() not in index_content:
                    untracked += 1
                    continue  # noqa

                elif file.is_file() and path.encode() in index_content:
                    tracked.append(file.path)

                elif file.is_dir() and file.name != '.git':
                    untracked_aux, tracked_aux = get_untracked_count_and_tracked_path(  # noqa: E501
                        git_dir,
                        patterns,
                        index_content,
                        os.path.abspath(file.path)
                    )
                    untracked += untracked_aux
                    tracked += tracked_aux

                tracked = [i.removeprefix('/') for i in tracked]
    except OSError:
        pass  # noqa

    return untracked, tracked


def parse_tree_object(data: bytes) -> list[tuple[str, str, str]]:
    """
    Parses the content of a git tree object and returns a list
    of its values
    param `data`: The content decompressed of tree object
    return: list of tuples containing the type, hash and the filename
    """

    if not data[data.index(b'\x00') + 1:]:
        return  # noqa

    res = []

    # first remove everything before first null byte
    start = data.index(b'\x00') + 1

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
        hexa = f'{int.from_bytes(hexa, "big"):x}'
        hexa = hexa.zfill(40)

        res.append((type_.decode(), hexa, filename.decode()))

        if not data[start + 1:]:
            break  # noqa

    return res


def get_values_of_tree(
    git_dir,
    tree: list,
    tracked: list,
    prepend_path=''
) -> tuple[int, int]:
    """
    Function to be called recursively whenever is found a tree
    param `git_dir`: The directory that contains '.git'
    param `tree`: List of parsed items gotten from 'parse_tree_object()'
    param `tracked`: List of full paths of tracked files gotten from
                    'get_untracked_count_and_tracked_path()'
    param `prepend_path`: For recurse use
    return: tuple containing modified and deleted files.
    """

    modified = 0
    deleted = 0

    level_path = git_dir + '/' + prepend_path

    for tup in tree:
        # blob = 100644, tree = 40000, syml =
        type_, hash_, name = tup

        if type_ == '100644':
            # need to transform in os specific path
            file_path = os.path.abspath(level_path + '/' + name)
            if file_path in tracked:
                tracked.remove(file_path)
                aux = low.get_hash(file_path)
                if hash_ != aux:
                    cr = low.get_hash(file_path, use_cr=True)
                    if cr == hash_:
                        pass
                    else:
                        modified += 1
            else:
                deleted += 1

        if type_ == '40000':
            content = low.get_content_by_hash(git_dir, hash_)
            if content is None:
                continue  # do something on packs here

            tree_items_list = parse_tree_object(content)

            if tree_items_list is not None:
                mod, del_ = get_values_of_tree(
                    git_dir, tree_items_list, tracked, f'{prepend_path}/{name}'
                )

                modified += mod
                deleted += del_

    return modified, deleted


def status(git_dir: str) -> tuple[int, int, int, int]:
    """
    Higher level function that searches the whole directory in
    which git resides returning the count of untracked, staged,
    modified and deleted files.
    param `git_dir`: The directory that contains '.git'.
    return: tuple containing the count of untracked, staged,
           modified and deleted files
    """

    staged = modified = deleted = 0

    if low.exists_gitignore(git_dir):
        patterns = low.get_ignore_patterns(git_dir)
    else:
        patterns = []

    untracked, tracked = get_untracked_count_and_tracked_path(
        git_dir, patterns
    )

    if low.exists_head(git_dir) and low.exists_refs_heads_head(git_dir):
        branch = low.get_branch_on_head(git_dir)

        path = os.path.join(git_dir, f'.git/refs/heads/{branch}')
        with open(path, 'r') as in_file:
            last_cmmt_hash = in_file.read().strip()

        # the tree in last_cmmt hasn't the general tree logic of parsing
        tree_h = low.get_content_by_hash(
            git_dir, last_cmmt_hash
        ).splitlines()[0].decode()
        tree_h = tree_h[tree_h.index('tree') + 5:].strip()

        tree_items_list = parse_tree_object(
            low.get_content_by_hash(git_dir, tree_h)
        )

        if tree_items_list:
            mod, del_ = get_values_of_tree(git_dir, tree_items_list, tracked)
            modified += mod
            deleted += del_

    # 'tracked' items will be deleted as its files are classified
    # what remais can only be staged
    staged = len(tracked)

    return untracked, staged, modified, deleted
