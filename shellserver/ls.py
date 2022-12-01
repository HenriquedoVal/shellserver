import sys
import os
import stat
import time

from colorama import Fore, Style, init, deinit


check_0 = (
    ('d', stat.FILE_ATTRIBUTE_DIRECTORY),
    ('l', stat.FILE_ATTRIBUTE_REPARSE_POINT),
    ('D', stat.FILE_ATTRIBUTE_DEVICE)
)

check_1 = (
    ('a', stat.FILE_ATTRIBUTE_ARCHIVE),
    ('r', stat.FILE_ATTRIBUTE_READONLY),
    ('h', stat.FILE_ATTRIBUTE_HIDDEN),
    ('s', stat.FILE_ATTRIBUTE_SYSTEM)
)


class Cache:
    __slots__ = 'data'

    def __init__(self):
        self.data = ''

    def write(self, value):
        self.data += value.replace('\x1b', '`e', -1).replace('$', '`$', -1)


class Ls:
    '''
    This is a simple Python class for listing the content of a directory.
    The sole purpose is giving better visualization.
    '''

    __slots__ = 'opt', 'path', 'out'

    def __init__(self, opt='', path='.', to_cache=False) -> None:

        if not opt or opt.startswith('-'):
            self.opt, self.path = opt, path
        else:
            self.opt, self.path = '', opt

        self.out = Cache() if to_cache else sys.stdout

    def echo(self, signal: int) -> None:
        try:
            with os.scandir(self.path) as scan:
                # just add to the list if it will be ever displayed
                # first we remove hidden ones if user hasn't asked for it
                dir = [i for i in scan
                       if (
                           not (i.name.startswith('.') or i.stat().st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN)
                           or 'a' in self.opt
                       )]

        except NotADirectoryError:
            print(f'{self.path} is not a directory.', file=self.out)
            return
        except FileNotFoundError:  # Check not a valid path
            print(f'{self.path} is not a valid path.', file=self.out)
            return
        except PermissionError as err:
            if signal:  # not going recursively on echo()
                print(f'{str(err)[:12]} {err.strerror}: {err.filename}', file=self.out)
                return

            self.path = os.path.realpath(self.path)
            self.echo(1)
            print(
                Style.RESET_ALL +
                "\nYou can't access files from here because CD doesn't "
                f"follow symlinks. Do first: cd {os.path.realpath('.')}",
                file=self.out
            )

        if 'l' in self.opt:
            # if not l, i would want the oposite order
            dir.sort(key=lambda x: (x.stat().st_mode, x.name))

            for i in dir:
                filemode_str = self._windows_filemode(
                    i.stat().st_file_attributes
                )

                # print() by 'column item' for better performance
                print(end=' ', file=self.out)
                print(filemode_str, end='   ', file=self.out)
                print(time.strftime(
                    '%d %b %y %H:%M', time.localtime(
                        i.stat().st_ctime)), end='   ', file=self.out)
                print(
                    self._humanize_size(i).rjust(7),
                    end='   ', file=self.out
                )
                print(self._type_color(i), file=self.out)

        else:
            dir.sort(key=lambda x: (x.stat().st_mode, x.name), reverse=True)

            print(
                *[self._type_color(i) for i in dir],
                sep='   ', file=self.out
            )

    def _type_color(self, i: os.DirEntry) -> str:
        if 'c' not in self.opt:
            return i.name

        # if i.is_symlink(): doesn't work
        if i.is_dir():
            # workaround
            if os.path.realpath(i.path) != os.path.join(os.path.realpath(self.path), i.name):  # noqa: E501
                return (Fore.CYAN
                        + i.name
                        + Fore.LIGHTBLACK_EX
                        + ' --> '
                        + os.path.realpath(i.path)
                        + Style.RESET_ALL)

            return Fore.LIGHTBLUE_EX + i.name + Style.RESET_ALL

        else:
            if i.name.endswith(('.zip', '.exe', '.msi', '.dll',
                                '.bat', '.sys', '.log', '.ini')):
                return Fore.YELLOW + i.name + Style.RESET_ALL
            if i.name.endswith(('.py', '.pyx', '.pyd', '.pyw')):
                return Fore.GREEN + i.name + Style.RESET_ALL
            if i.name.endswith(('.tmp')):
                return Fore.LIGHTBLACK_EX + i.name + Style.RESET_ALL
            if i.name.endswith(('.pdf')):
                return Fore.LIGHTRED_EX + i.name + Style.RESET_ALL
            return i.name

    def _humanize_size(self, i: os.DirEntry):
        if i.is_dir():
            return '-'

        entry = i.stat().st_size
        units = ('k', 'M', 'G')
        final = ''

        for unit in units:
            if entry < 1024:
                break
            entry /= 1024
            final = unit

        if final:
            data = f'{entry:.1f}{final}'
        else:
            data = str(entry)

        if 'c' in self.opt:
            if 'G' in data:
                data = Fore.RED + data + Style.RESET_ALL
                data = data.rjust(16)
            elif 'M' in data:
                data = Fore.LIGHTRED_EX + data + Style.RESET_ALL
                data = data.rjust(16)
            elif 'k' in data:
                data = Fore.YELLOW + data + Style.RESET_ALL
                data = data.rjust(16)

        return data

    def _windows_filemode(
        self,
        data: os.stat_result.st_file_attributes
    ):

        if data == 0x80:
            str_res = list('-a---')
        else:
            str_res = list('-----')
            for check in check_0:
                if data & check[1]:
                    str_res[0] = check[0]

            for ind, check in zip(range(1, 5), check_1):
                if data & check[1]:
                    str_res[ind] = check[0]

        if 'c' not in self.opt:
            return ''.join(str_res)

        for ind in range(5):
            if str_res[ind] == '-':
                continue
            str_res[ind] = (Fore.BLUE + str_res[ind] + Style.RESET_ALL)

        return ''.join(str_res)


def main():
    init()

    args = sys.argv[1:]

    # notice useless parameters
    if len(args) > 2:
        print(f'Ignored {args[2:]} parameter(s)')
        args = args[:2]
    if len(args) == 2 and not args[0].startswith('-'):
        print('Try: py ls.py -acl path')

    Ls(*args).echo(0)
    deinit()


if __name__ == '__main__':
    main()
