from __future__ import annotations

"""
Module with functions considered to be of low level,
that is, functions that doesn't call its siblings.
Same idea for the methods of Low class.
"""

import hashlib
import os
import subprocess
import zlib

try:
    import pygit2
    HAS_PYGIT2 = True
except ImportError:
    HAS_PYGIT2 = False


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
        return None

    return get_dot_git(parent)


def exists_head(git_dir: str) -> bool:
    """
    Checks if there are a 'HEAD' in git files.
    return: bool: Is there a 'HEAD' in .git?
    """

    head = os.path.join(git_dir, '.git/HEAD')
    return os.path.exists(head)


def get_branch_on_head(git_dir: str) -> str:
    """
    Parses 'HEAD' file to get the head branch.
    return: str: The name of the git branch.
    """

    head_path = os.path.join(git_dir, '.git/HEAD')

    with open(head_path) as head:
        content = head.read()

    return content[content.rindex('/') + 1:].strip()


class Low:
    # {git_dir: repo}
    pygit2_repos: dict[str, pygit2.Repository] = {}

    # populate var just for mypy stop complaining
    git_dir = 'Unreachable'
    branch = 'Unreachable'

    def get_info_packs_content(self) -> list:  # [str]:
        """
        Checks the existence of a 'packs' file in git/objects
        and return its content.
        return: list: Content of packs by line.
        """

        packs = os.path.join(self.git_dir, '.git/objects/info/packs')
        if not os.path.exists(packs):
            return []

        with open(packs) as in_file:
            content = in_file.readlines()[::-1]

        counter = 0
        while counter < len(content):
            test = content[counter][2:].strip()
            if not test:
                del content[counter]
                continue

            content[counter] = test
            counter += 1

        return content

    def get_gitignore_content(self, dir_path) -> list:  # [str]:
        """
        Searhes for a .gitignore in the same level of `dir_path`.
        return: list: Content of .gitignore by line.
        """

        gitignore = os.path.join(dir_path, '.gitignore')
        if not os.path.exists(gitignore):
            return []

        with open(gitignore) as in_file:
            content = in_file.readlines()

        counter = 0
        while counter < len(content):
            test = content[counter].strip()
            if not test:
                del content[counter]
                continue

            content[counter] = test
            counter += 1

        return content

    def get_last_commit_loose(self) -> str | None:
        """
        Gets the last commit's hash of a git repo.
        return: str | None: String of the last commit hash, None if there's no
                            last commit.
        """

        head_path = os.path.join(
            self.git_dir, f'.git/refs/heads/{self.branch}'
        )

        if not os.path.exists(head_path):
            return None

        with open(head_path) as file:
            return file.read().strip()

    def get_info_refs_content(self) -> list[str]:
        """
        Checks the existence of a 'refs' file in .git/info
        and return its content
        return: list: Content of 'refs' by line.
        """

        refs = os.path.join(self.git_dir, '.git/info/refs')
        if not os.path.exists(refs):
            return []

        with open(refs) as in_file:
            content = in_file.readlines()

        for ind in range(len(content)):
            content[ind] = content[ind].strip()

        return content

    def get_exclude_content(self) -> list:  # [str]:
        """
        Checks the existence of a 'exclude' file inside .git/info
        and return its content.
        return: list: Content of exclude by line.
        """
        exclude = os.path.join(self.git_dir, '.git/info/exclude')
        if not os.path.exists(exclude):
            return []

        with open(exclude) as in_file:
            content = in_file.readlines()

        counter = 0
        while counter < len(content):
            test = content[counter].strip()
            if not test:
                del content[counter]
                continue

            content[counter] = test
            counter += 1

        return content

    def get_hash_of_file(self, file_path: bytes | str, use_cr=False) -> str:
        """
        Get the SHA1 hash in the same way Git would do.
        param `file_path`: str | bytes: The path to file.
        param `use_cr`: bool: Use CRLF for new line?
        """
        with open(file_path, 'rb') as in_file:
            content = in_file.read()

        if not use_cr:
            content = content.replace(b'\r\n', b'\n', -1)

        size = len(content)
        string = f"blob {size}\x00"
        hash_ = hashlib.sha1(string.encode() + content).hexdigest()

        return hash_

    def get_content_by_hash_loose(self, hash_: str) -> bytes | None:
        """
        Get the content of a loose file by its hash.
        param `hash`: The hash gotten from `get_hash_of_file` for files in repo
                      or in git files.
        return: bytes | None: The content of file, None if it was not found.
        """

        path = os.path.join(
            self.git_dir, f'.git/objects/{hash_[:2]}/{hash_[2:]}'
        )
        if not os.path.exists(path):
            return None

        with open(path, 'rb') as in_file:
            content = in_file.read()

        # cannot decode here
        # in blob we can take bytes or str
        # in tree, only bytes
        return zlib.decompress(content)

    def get_tree_hash_from_commit(self, cmmt_obj: bytes) -> str:
        """
        Get the tree hash from an commit object.
        param `cmmt_obj`: bytes: A git commit object.
        return: str: The tree hash.
        """

        first_line = cmmt_obj.splitlines()[0].decode()
        tree_hash = first_line[first_line.index('tree') + 5:].strip()

        return tree_hash

    def get_status_string(
            self, status: tuple[int, int, int, int]
    ) -> str | None:
        """
        Get the string version of given Git status
        param `status`: tuple: untracked, staged, modified and deleted sums.
        return: str | None: String of status, None if not any value is above 0.
        """
        if not any(status):
            return None

        symbols = ('?', '+', 'm', 'x')

        return ' '.join(
            symb + str(stat)
            for symb, stat in zip(symbols, status)
            if stat
        )

    def parse_git_status(self) -> str:
        """
        Parses `git status --porcelain` returning tuple of untracked, staged,
        modified and deleted sums.
        return: str: String of status, empty string for nothing to report.
        """
        out, err = subprocess.Popen(
            f'git -C {self.git_dir} --no-optional-locks status --porcelain',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
        ).communicate()

        data = out.decode().splitlines()
        data = [line[:2].strip() for line in data]

        possibles = list(set(data))

        res = [mark + str(data.count(mark)) for mark in possibles]

        return ' '.join(res)

    def parse_tree_object(
            self, data: bytes, from_pack: bool = False
    ) -> list:
        """
        Parses the content of a git tree object and returns a list
        of its values
        param `data`: The content decompressed of tree object
        return: list: list of tuples containing the type, hash and
                the filename in tree.
        """

        if not from_pack:
            if not data[data.index(b'\x00') + 1:]:
                return []

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
            hexa_str = f'{int.from_bytes(hexa, "big"):x}'.zfill(40)

            res.append((type_.decode(), hexa_str, filename.decode().lower()))

            if not data[start + 1:]:
                break

        return res

    def parse_pygit2(self):
        repo = self.pygit2_repos.get(self.git_dir)
        if repo is None:
            repo = pygit2.Repository(self.git_dir)
            self.pygit2_repos[self.git_dir] = repo

        d: dict = repo.status()

        unt = sta = mod = del_ = 0
        for value in d.values():
            if value & 0x80:
                unt += 1
            elif value & 1:
                sta += 1
            elif value & 0x100:
                mod += 1
            elif value & 0x200:
                del_ += 1

        return self.get_status_string((unt, sta, mod, del_))
