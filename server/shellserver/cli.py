import argparse

from .__init__ import PORT, APP_HOME


def kill():
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.sendto(b'2Kill', ('localhost', PORT))


def clear():
    import os

    for file in ('ShellServerCache', 'traceback'):
        file_path = os.path.join(APP_HOME, file)
        if os.path.exists(file_path):
            os.remove(file_path)

    os.removedirs(APP_HOME)


def main():
    parser = argparse.ArgumentParser(
        prog='shellserver'
    )

    parser.add_argument(
        'command',
        choices=('kill', 'clear'),
        help='"kill" to kill the server, "clear" to clear the cache.'
    )

    args = parser.parse_args()

    if args.command == 'kill':
        kill()
    elif args.command == 'clear':
        clear()
