import hashlib
import os
import subprocess
import zlib

from . import packs
from . import plugins


class IndexTooBigError(Exception):
    pass


class Base(packs.Packs):
    # {git_dir: repo}
    pygit2_repos: dict[str, plugins.pygit2.Repository] = {}
    git_dir: str
    branch: str
    index_tracked: dict[str, float]
    relative: list[str]
    fallback: bool

    # dropped __slots__

    def __init__(self) -> None:
        raise TypeError("cannot create 'gitstatus.base.Base' instances")

    def set_packs(self) -> None:
        """
        Sets the `packs_list` attribute.
        return: None.
        """
        # info/packs is not needed
        pack_def_path = '.git/objects/pack'

        packs_list = self.get_info_packs_content()
        if packs_list:
            self.packs_list = [
                os.path.join(
                    self.git_dir, pack_def_path, i
                ) for i in packs_list
            ]
            return

        packs = os.path.join(self.git_dir, pack_def_path)
        if not os.path.exists(packs):
            self.packs_list = []
            return

        dir_ = os.scandir(packs)
        self.packs_list = [
            i.path for i in dir_ if i.name.endswith('.pack')
        ]

    def set_index_tracked(self) -> None:
        """
        Sets `index_tracked` attribute.
        Modified and simpler version of gin.
        https://github.com/sbp/gin
        return: None.
        """
        max_entries = 1000
        if plugins.HAS_SSD_CHECKER:
            for drive in plugins.DRIVE_SSD_MAP:
                if self.git_dir.startswith(drive):
                    # if SSD: 2500 if HDD: 1000
                    max_entries = (
                        2500 if plugins.DRIVE_SSD_MAP[drive] else 1000
                    )
                    break

        index_path = os.path.join(self.git_dir, '.git/index')
        if not os.path.exists(index_path):
            self.index_tracked = {}
            return

        with open(index_path, 'rb') as f:

            def read_str_until(delim: bytes) -> str:
                ret: list[bytes] = []
                while True:
                    b = f.read(1)
                    if b == b'' or b == delim:
                        return b"".join(ret).decode()

                    ret.append(b)

            constant = f.read(4)
            version = int.from_bytes(f.read(4), 'big')
            if constant != b'DIRC' or version not in (2, 3):
                self.index_tracked = {}

            entries = int.from_bytes(f.read(4), 'big')
            res = {}

            for entry in range(entries):
                f.read(8)
                # converted to float to keep type consistence
                mtime = float(int.from_bytes(f.read(4), 'big'))
                mtime += int.from_bytes(f.read(4), 'big') / 1000000000
                f.read(44)

                flags = int.from_bytes(f.read(2), 'big')
                namelen = flags & 0xfff
                extended = flags & (0b0100_0000 << 8)

                entrylen = 62

                if extended:
                    f.read(2)
                    entrylen += 2

                if namelen < 0xfff:
                    name = f.read(namelen).decode()
                    entrylen += namelen
                else:
                    name = read_str_until(b'\x00')
                    entrylen += 1

                res[name] = mtime

                if self.fallback and len(res) > max_entries:
                    raise IndexTooBigError

                padlen = (8 - (entrylen % 8)) or 8
                f.read(padlen)

        self.index_tracked = res

    def get_split_ignored(
        self, raw_ignored: list[str], prepend: None | str = None
    ) -> tuple[list[str], list[str]]:
        """
        Returns two lists in this order: fixed and relative.
        """
        raw_ignored = [
            i.strip()
            for i in raw_ignored
            if not i.strip().startswith('#')
        ]

        relative = [
            i for i in raw_ignored
            if '/' not in i[:-1]
        ]

        if prepend is None:
            fixed = [i.lstrip('/') for i in raw_ignored if i not in relative]

        else:
            relpath = prepend.removeprefix(
                self.git_dir + '\\'
            ).replace('\\', '/', -1)

            fixed = [
                f'{relpath}/{i}' for i in raw_ignored if i not in relative
            ]

        return fixed, relative

    def get_content_by_hash_packed(self, hash_: str) -> bytes | None:
        """
        Gets the content of an object by its hash in any packfiles present.
        param `hash_`: The hash to be searched in packfiles.
        return: bytes | None: The content of object, None if it was not Found.
        """
        content = None

        for pack in self.packs_list:
            idx = self.get_idx_of_pack(pack)
            offset = self.search_idx(idx, hash_)
            if offset is None:
                continue
            content = self.get_content_by_offset(pack, offset)
            if content:
                break

        return content

    def get_last_commit_packed(self) -> str | None:
        """
        Gets the last commit's hash of a git repo by a packed perspective.
        return: str | None: String of the last commit hash, None if there's no
                            last commit packed.
        """
        info_refs = self.get_info_refs_content()
        last_commt_hash = None

        for line in info_refs:
            a, b = line.strip().split()
            if b == f'refs/heads/{self.branch}':
                last_commt_hash = a
                break

        return last_commt_hash

    def get_last_commit_hash(self) -> str | None:
        """
        Gets the last commit's hash of a git repo.
        return: str | None: String of the last commit hash, None if there's no
                            last commit.
        """
        last_cmmt = self.get_last_commit_loose()

        if last_cmmt is None:
            last_cmmt = self.get_last_commit_packed()

        return last_cmmt

    def get_ignored_lists(
        self,
        dir_path: str,
        relpath: str | None,
        fixed_prev: list[str] | None,
        relative_prev: list[str] | None,
        exclude_content: list[str] | None = None
    ) -> tuple[list[str], list[str], list[str]]:
        first_call = exclude_content is not None

        raw_ignored = self.get_gitignore_content(dir_path)
        if isinstance(exclude_content, list):
            raw_ignored += exclude_content

        prepend = None if first_call else dir_path
        fixed, relative = self.get_split_ignored(raw_ignored, prepend)

        # this supposes that most of .gitignore are in first level of depth
        # if first_call:
        #     self.relative = relative
        #     relative = []

        # if it isn't the first call, but first_call var can't be used (mypy)
        if isinstance(fixed_prev, list) and isinstance(relative_prev, list):
            fixed += fixed_prev
            relative += relative_prev
            # fixed = self.get_clean_fixed_level(relpath, fixed)
            assert isinstance(relpath, str)
            clean_fixed = self.get_clean_fixed_depth(relpath, fixed)
        # pass everything onward
        else:
            clean_fixed = fixed

        return fixed, relative, clean_fixed

    def get_clean_fixed_depth(
        self, relpath: str, fixed: list[str]
    ) -> list[str]:

        depth = relpath.count('/')
        return [
            pattern for pattern in fixed
            if pattern[:-1].count('/') > depth
            or '**' in pattern
        ]

    #
    # Low
    #

    def get_info_packs_content(self) -> list[str]:
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

    def get_gitignore_content(self, dir_path: str) -> list[str]:
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

    def get_exclude_content(self) -> list[str]:
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

    def get_hash_of_file(
        self, file_path: bytes | str,
        use_cr: bool = False,
        use_prev_read: bool = False,
        *,
        is_buf: bool = False
    ) -> str:
        """
        Get the SHA1 hash in the same way Git would do.
        param `file_path`: str | bytes: The path to file.
        param `use_cr`: bool: Use CRLF for new line?
        """
        if is_buf:
            assert isinstance(file_path, bytes)
            self.prev_read = file_path
        elif not use_prev_read:
            with open(file_path, 'rb') as in_file:
                self.prev_read = in_file.read()

        content = self.prev_read

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

    def parse_git_status(self) -> str | None:
        """
        Parses `git status --porcelain` returning tuple of untracked, staged,
        modified and deleted sums.
        return: str: String of status, empty string for nothing to report.
        """
        out, err = subprocess.Popen(
            ['git', '-C', self.git_dir,
             '--no-optional-locks', 'status', '--porcelain'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
        ).communicate()

        data = out.decode().splitlines()
        data = [line[:2].strip() for line in data]

        possibles = list(set(data))

        res = [mark + str(data.count(mark)) for mark in possibles]

        ret_value = ' '.join(res)
        return ret_value if ret_value else None

    def parse_tree_object(
        self, data: bytes, from_pack: bool = False
    ) -> list[tuple[str, str, str]]:
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

            res.append((type_.decode(), hexa_str, filename.decode()))

            if not data[start + 1:]:
                break

        return res

    def parse_pygit2(self) -> str | None:
        repo = self.pygit2_repos.get(self.git_dir)
        if repo is None:
            repo = plugins.pygit2.Repository(self.git_dir)
            repo.free()
            self.pygit2_repos[self.git_dir] = repo

        d: dict[str, int] = repo.status(untracked_files='normal')

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
