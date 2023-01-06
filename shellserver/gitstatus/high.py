"""
Module for functions with high level of abstraction
and/or complexity.
"""

from fnmatch import fnmatch
import sys

from . import low
from . import medium

os = low.os  # os module

n = '\n\n'
if '--verbose' not in sys.argv:
    sys.stdout = None


# instead of raising fallback, it should build the deltas
class FallbackError(Exception):
    pass


def status(git_dir: str, branch: str) -> str | None:
    """
    Do a inline version of 'git status' without any use of git.
    param `git_dir`: The directory where .git resides.
    param `branch`: The name of the branch to get status.
    return: str | None: String with the status, None if there's
                        nothing to report.
    """

    print('GIT_DIR:', git_dir)
    print('Branch', branch, end=n)

    fixed, ignored = medium.get_split_ignored(git_dir)

    index_tracked = medium.get_index_tracked(git_dir)

    packs_list = medium.get_packs(git_dir)
    print('List of packfiles:', *packs_list, sep='\n', end=n)

    untracked, staged, modified, deleted = get_full_status(
        git_dir, branch, fixed, ignored, index_tracked, packs_list
    )

    return low.get_status_string((untracked, staged, modified, deleted))


def get_full_status(
    git_dir: str,
    branch: str,
    fixed: list,
    ignored: list,
    index_tracked: list,
    packs_list: list,
    recurse_path=None,
    tree_hash=None
) -> tuple[int, int, int, int]:
    """
    Carries all the workload of getting a status.
    param `git_dir`: The directory where .git resides.
    param `branch`: The actual branch of git.
    param `fixed`: list of full paths in both '.gitignore' and 'exclude'.
    param `ignored`: list of relative paths in both '.gitignore' and 'exclude'.
    param `index_tracked`: list of files tracked in git index.
    param `packs_list`: list of full paths of packfiles.
    param `recurse_path`: For recursive use.
    param `tree_hash`: For recursive use.
    return: tuple: tuple of four integer numbers representing the number of
                    untracked, staged, modified and deleted files.
    """

    untracked = staged = modified = deleted = 0

    if recurse_path is None:
        recurse_path = git_dir

    tree_items_list = []
    # will happen only in very first call
    if tree_hash is None:
        last_cmmt = medium.get_last_commit_hash(git_dir, branch)
        if last_cmmt is not None:
            res = get_tree_items(git_dir, last_cmmt, packs_list)
            if res is not None:
                tree_items_list = res
    # all recursive calls must fall here
    else:
        tree_items_list = get_tree_items_from_hash(
            git_dir, tree_hash, packs_list
        )

    try:
        directory = os.scandir(recurse_path)
    except PermissionError:
        return untracked, staged, modified, deleted

    # index will have only the full path of blobs
    # trees have everything
    found_in_tree = 0
    for file in directory:

        relpath = os.path.relpath(
            file.path, git_dir
        ).replace('\\', '/', -1)

        if file.is_file() and relpath in index_tracked:
            if file.name not in (i[2] for i in tree_items_list):
                print('Staged:', file.name, "isn't under a commit.")
                staged += 1
                continue

            found_in_tree += 1
            if ('100644', low.get_hash_of_file(file.path), file.name) in tree_items_list:  # noqa
                continue
            elif ('100644', low.get_hash_of_file(file.path, use_cr=True), file.name) in tree_items_list:  # noqa
                continue
            print('Modified:', file.name, "has different sha1.")
            modified += 1

        elif file.name == '.git':
            pass

        elif any(fnmatch(file.name, pat) for pat in ignored):
            pass
        elif any(fnmatch(relpath, pat) for pat in fixed):
            pass

        elif file.is_file():  # and relpath not in index
            print('Untracked:', relpath)
            untracked += 1

        # if dir is not in tree_items_list
        elif file.name not in (
                i[2] for i in
                filter(lambda x: x[0] == '40000', tree_items_list)
        ):
            # untrack must be setted only if any children is not ignored
            result = handle_untracked_dir(
                git_dir, file.path, fixed, ignored
            )
            if result:
                untracked += result
                print('Untracked:', relpath)

        else:
            found_in_tree += 1

            trees = filter(lambda x: x[0] == '40000', tree_items_list)
            file_name_tuple = filter(lambda x: x[2] == file.name, trees)
            item_tuple = tuple(file_name_tuple)
            tree_hash = item_tuple[0][1]

            unt, sta, mod, del_ = get_full_status(
                git_dir,
                branch,
                fixed,
                ignored,
                index_tracked,
                packs_list,
                file.path,
                tree_hash
            )
            untracked += unt
            staged += sta
            modified += mod
            deleted += del_

    # endfor
    deleted += len(tree_items_list) - found_in_tree

    return untracked, staged, modified, deleted


def handle_untracked_dir(
        git_dir: str, dir_name: str, fixed: list, ignored: list
) -> int:
    """
    Handles when `get_full_status` finds untracked directory.
    param `git_dir`: The directory where .git resides.
    param `dir_name`: The path of the untracked directory.
    param `fixed`: list of full paths in both '.gitignore' and 'exclude'.
    param `ignored`: list of relative paths in both '.gitignore' and 'exclude'.
    return: int: 1 if there was at least one not ignored file in directory.
                 0 if there was none.
    """
    try:
        with os.scandir(dir_name) as sub_dir:

            untracked = 0
            for sub_file in sub_dir:
                if sub_file.is_dir():
                    untracked += handle_untracked_dir(
                        git_dir, sub_file.path, fixed, ignored
                    )

                if untracked:
                    return 1

                if sub_file.is_file():
                    if any(fnmatch(sub_file.name, pat)
                           for pat in ignored):
                        continue

                    sub_relpath = os.path.relpath(
                        sub_file.path, git_dir
                    ).replace('\\', '/', -1)

                    if any(fnmatch(sub_relpath, pat)
                           for pat in fixed):
                        continue
                    return 1

            return 0
    except PermissionError:
        return 0


def get_tree_items(
        git_dir: str, last_cmmt: str, packs_list: list
) -> list | None:
    """
    Gets the last commit tree itens (type, hash and filename).
    param `git_dir`: The directory where .git resides.
    param `last_cmmt`: The hash of the last commit.
    param `packs_list`: list of full paths of packfiles.
    return: list | None: list of tuples with the type, hash and filenames,
                None if tree is empty.
    """

    last_cmmt_obj = low.get_content_by_hash_loose(git_dir, last_cmmt)
    if last_cmmt_obj is None:
        last_cmmt_obj = medium.get_content_by_hash_packed(
            last_cmmt, packs_list
        )

    if last_cmmt_obj is None:
        print("Couldn't get last commit object. Fallback.")
        raise FallbackError

    tree_hash = low.get_tree_hash_from_commit(last_cmmt_obj)
    print('Last commit tree hash:', tree_hash)

    tree_obj = low.get_content_by_hash_loose(git_dir, tree_hash)
    if tree_obj is None:
        tree_obj = medium.get_content_by_hash_packed(tree_hash, packs_list)

    if tree_obj is None:
        print("Couldn't get last commit tree. Fallback.")
        raise FallbackError

    # there is a tree object but the git worktree is empty.
    if not tree_obj:
        return

    return low.parse_tree_object(tree_obj)


def get_tree_items_from_hash(
        git_dir: str, tree_hash: str, packs_list: list
) -> list:
    """
    Gets the tree itens searching for its hash.
    param `git_dir`: The directory where .git resides.
    param `tree_hash`: The hash of tree.
    param `packs_list`: list of full paths of packfiles.
    return: list: list of tuples with the type, hash and filenames.
    """
    from_pack = False
    tree_obj = low.get_content_by_hash_loose(git_dir, tree_hash)
    print('Searching loose', tree_hash)

    if tree_obj is None:
        from_pack = True
        tree_obj = medium.get_content_by_hash_packed(tree_hash, packs_list)
        print('Searching packed', tree_hash)

    if tree_obj is None:
        print('Not found. Fallback.')
        raise FallbackError

    tree_items_list = low.parse_tree_object(tree_obj, from_pack)
    print('Found:', *tree_items_list, sep='\n', end=n)

    return tree_items_list
