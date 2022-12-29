"""
Module with functions considered to be of low level,
that is, functions that doesn't call its siblings.
"""

import os
import re
import hashlib
import subprocess
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
        return

    return get_dot_git(parent)


def exists_head(git_dir: str) -> bool:
    """
    Checks if there are a 'HEAD' in git files.
    param `git_dir`: The path of .git.
    return: bool: Is there a 'HEAD' in .git?
    """

    head = os.path.join(git_dir, '.git/HEAD')
    return os.path.exists(head)


def get_index_content(git_dir: str) -> bytes:
    """
    Checks if there is a 'index' in git files.
    param `git_dir`: The path of .git.
    return: bool: Is there a 'index' in .git?
    """

    index_path = os.path.join(git_dir, '.git/index')
    if not os.path.exists(index_path):
        return b''

    with open(index_path, 'rb') as file:
        content = file.read()

    return content


def get_info_packs_content(git_dir: str) -> list:
    """
    Checks the existence of a 'packs' file in git/objects
    and return its content.
    param `git_dir`: The path of .git.
    return: list: Content of packs by line
    """

    packs = os.path.join(git_dir, '.git/objects/info/packs')
    if os.path.exists(packs):
        with open(packs, 'r') as in_file:
            content = in_file.readlines()
            content = [i[2:].strip() for i in content][::-1]
            content = [i for i in content if i]
    else:
        content = []

    return content


def get_gitignore_content(git_dir: str) -> list:
    """
    Checks the existence of a .gitignore in same level of .git
    and return its content
    param `git_dir`: The path of .git.
    return: list: Content of .gitignore by line.
    """

    gitignore = os.path.join(git_dir, '.gitignore')
    if os.path.exists(gitignore):
        with open(gitignore, 'r') as in_file:
            content = in_file.readlines()
            content = [i.strip() for i in content if i.strip()]
    else:
        content = []

    return content


def get_last_commit_loose(git_dir: str, branch) -> str:
    """
    Checks if there is a file with the name of head in .git/refs/heads.
    param `git_dir`: The path of .git.
    return: bool: Is there a file with the same name of head in refs/heads?
    """

    head_path = os.path.join(git_dir, f'.git/refs/heads/{branch}')

    if not os.path.exists(head_path):
        return ''

    with open(head_path) as file:
        return file.read().strip()


def get_info_refs_content(git_dir) -> str:
    """
    Checks the existence of a 'refs' file in .git/info
    and return its content
    param `git_dir`: The path of .git.
    return: list: Content of .gitignore by line.
    """

    refs = os.path.join(git_dir, '.git/info/refs')
    if os.path.exists(refs):
        with open(refs, 'r') as in_file:
            content = in_file.readlines()
    else:
        content = []

    return content


def get_exclude_content(git_dir: str) -> list:
    """
    Checks the existence of a 'exclude' file inside .git/info
    and return its content.
    param `git_dir`: The path of .git.
    return: list: Content of exclude by line.
    """
    exclude = os.path.join(git_dir, '.git/info/exclude')
    if os.path.exists(exclude):
        with open(exclude, 'r') as in_file:
            content = in_file.readlines()
            content = [i.strip() for i in content if i.strip()]
    else:
        content = []

    return content


def get_branch_on_head(git_dir: str) -> str:
    """
    Parses 'HEAD' file to get the head branch.
    param `git_dir`: The path of .git.
    return: str: The name of the git branch.
    """

    head_path = os.path.join(git_dir, '.git/HEAD')

    with open(head_path, 'r') as head:
        content = head.read()
    return content[content.rindex('/') + 1:].strip()


def adapt_regex(x: list) -> list:
    """
    Adapts the Git's regex to Python's re module.
    param `x`: list of valid patterns.
    return: list: Each pattern adapted to re.
    """

    int_mark = '[^/]'
    asterisk = int_mark + '*'
    doub_ast = '.*'

    result = [i.replace('?', int_mark, -1)
              .replace('**', doub_ast, -1)
              .replace('*', asterisk, -1)
              .replace('.', '\\.', -1)
              for i in x]

    return result


def get_valid_patterns(content: list) -> list:
    """
    Goes through a list of content from .gitignore and/or exclude
    to get the valid patterns.
    return: list: valid patterns in .gitignore and/or exclude.
    """

    result = []
    for line in content:
        # TODO: sigle match that does all of the below
        # if line isn't commented or comment is escaped
        if re.match(r'\s*[^\\#].*', line):
            result.append(line.strip())

        # git doc says only spaces will be accepted, not \s
        elif re.match(r'\s*\\[\ !#].*', line):
            result.append(line.strip()[1:])

        # deal with !important feature in git
        elif re.match(r'\s*!.*', line):
            try:
                result.remove(line.strip()[1:])
            except ValueError:
                pass

    return result


def get_hash(file_path: bytes | str, use_cr: bool = False) -> str:
    with open(file_path, 'rb') as in_file:
        content = in_file.read()

    if not use_cr:
        content = content.replace(b'\r\n', b'\n', -1)

    size = len(content)
    string = f"blob {size}\x00"
    hash_ = hashlib.sha1(string.encode() + content).hexdigest()

    return hash_


def get_content_by_hash_loose(git_dir: str, hash_: str) -> bytes:
    """
    Get the content of a git file by a object hash.
    param `git_dir`: The path of .git.
    param `hash`: The hash gotten from `get_hash` for files in repo
                  or in git files.
    return: str: The content of file.
    """

    path = os.path.join(git_dir, f'.git/objects/{hash_[:2]}/{hash_[2:]}')
    if not os.path.exists(path):
        return

    with open(path, 'rb') as in_file:
        content = in_file.read()

    # cannot decode here
    # in blob we can take bytes or str
    # in tree, only bytes
    return zlib.decompress(content)


def parse_git_status(git_dir: str) -> str:
    """
    Parses `git status -s` returning tuple of untracked, staged,
    modified and deleted sums.
    """
    data, err = subprocess.Popen(
        f'git -C {git_dir} status -s --porcelain',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW
    ).communicate()

    data = data.decode().splitlines()
    data = [line[:2].strip() for line in data]

    possibles = list(set(data))

    res = [mark + str(data.count(mark)) for mark in possibles]

    return ' '.join(res)


def get_idx_of_pack(pack: str) -> str:
    return pack.removesuffix('pack') + 'idx'


def get_tree_hash_from_commit(commt_obj: bytes) -> str:
    first_line = commt_obj.splitlines()[0].decode()
    tree_hash = first_line[first_line.index('tree') + 5:].strip()

    return tree_hash


def stringfy_status(status: tuple[int, int, int, int]) -> str:
    if not any(status):
        return

    res = ''
    symbols = ('?', '+', 'm', 'x')

    for stat, symb in zip(status, symbols):
        if stat:
            res += symb + str(stat) + ' '

    return res.strip()
