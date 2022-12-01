"""
Module with functions considered to be of low level,
that is, functions that doesn't call its siblings.
"""

import os
import re
import hashlib
import zlib


def get_dot_git(target_path: str) -> str | None:
    """
    Searches backwards for .git
    param `target_path`: The absolute path from which the search begins.
    return: str | None: The directory of .git. None if it was not found.
    """

    git = os.path.join(target_path, '.git')
    if os.path.exists(git):
        return target_path

    parent = os.path.dirname(target_path)
    if parent == target_path:
        return  # noqa

    return get_dot_git(parent)


def exists_head(git_dir: str) -> bool:
    """
    Checks if there are a 'HEAD' in git files.
    param `git_dir`: The path of .git.
    return: bool: Is there a 'HEAD' in .git?
    """

    head = os.path.join(git_dir, '.git/HEAD')
    return os.path.exists(head)


def exists_refs_heads_head(git_dir: str) -> bool:
    """
    Checks if there is a file with the name of head in .git/refs/heads.
    param `git_dir`: The path of .git.
    return: bool: Is there a file with the same name of head in refs/heads?
    """

    head = get_branch_on_head(git_dir)
    return os.path.exists(os.path.join(git_dir, f'.git/refs/heads/{head}'))


def exists_index(git_dir: str) -> bool:
    """
    Checks if there is a 'index' in git files.
    param `git_dir`: The path of .git.
    return: bool: Is there a 'index' in .git?
    """

    index_path = os.path.join(git_dir, '.git/index')
    return os.path.exists(index_path)


def exists_gitignore(git_dir: str) -> bool:
    """
    Checks the existence of a .gitignore in same level of .git
    param `git_dir`: The path of .git.
    return: bool: Is there a .gitignore in same level of .git?
    """

    gitignore = os.path.join(git_dir, '.gitignore')
    return os.path.exists(gitignore)


def exists_packs(git_dir: str) -> bool:
    """
    Checks the existence of a 'packs' file in git/objects
    param `git_dir`: The path of .git.
    return: bool: Is there a packs file in git/objects/info?
    """

    packs = os.path.join(git_dir, '.git/objects/info/packs')
    return os.path.exists(packs)


def get_branch_on_head(git_dir: str) -> str:
    """
    Parses 'HEAD' file to get the head branch.
    param `git_dir`: The path of .git.
    return: str: The name of the git branch.
    """

    head_path = os.path.join(git_dir, '.git/HEAD')

    with open(head_path, 'r') as head:
        content = head.read()
    return content[content.rindex('/')+1:].strip()


def get_ignore_patterns(git_dir: str) -> list:
    """
    Parses '.gitignore' and return valid patterns.
    param `git_dir`: The path of .git.
    return: list: valid patterns in .gitignore.
    """

    gitignore = os.path.join(git_dir, '.gitignore')
    with open(gitignore, 'r') as in_file:
        content = in_file.readlines()

    # remove empty lines
    content = [i for i in content if i]

    result = []
    for line in content:
        # remove comented lines
        if re.match(r'\s*[^\\#].*', line):
            result.append(line.strip())

        # git doc says only spaces will be accepted, not \s
        elif re.match(r'\s*\\[\ !#].*', line):
            result.append(line.strip()[1:])

        elif re.match(r'\s*!.*', line):
            try:
                result.remove(line.strip()[1:])
            except ValueError:
                pass  # noqa

        # TODO: add $GIT_DIR/info/exclude

    # adapt the git regex to python re
    int_mark = '[^/]'
    asterisk = int_mark + '*'
    doub_ast = '.*'

    result = [i.replace('?', int_mark, -1)
              .replace('**', doub_ast, -1)
              .replace('*', asterisk, -1)
              .replace('.', '\\.', -1)
              for i in result]

    return result


def get_hash(file_path: bytes | str) -> str:
    with open(file_path, 'rb') as in_file:
        content = in_file.read().replace(b'\r\n', b'\n', -1)

    size = len(content)
    string = f"blob {size}\x00"
    hash = hashlib.sha1(string.encode() + content).hexdigest()
    return hash


def get_content_by_hash(git_dir: str, hash: str) -> bytes:
    """
    Get the content of a git file by a object hash.
    param `git_dir`: The path of .git.
    param `hash`: The hash gotten from `get_hash` for files in repo
                  or in git files.
    return: str: The content of file.
    """

    path = os.path.join(git_dir, f'.git/objects/{hash[:2]}/{hash[2:]}')
    if not os.path.exists(path):
        return  # noqa

    with open(path, 'rb') as in_file:
        content = in_file.read()

    # cannot decode here
    # in blob we can take bytes or str
    # in tree, only bytes
    return zlib.decompress(content)
