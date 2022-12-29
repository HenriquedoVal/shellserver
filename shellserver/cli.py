import argparse

from .__init__ import CACHE_PATH, PORT


def kill():
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.sendto(b'2Kill', ('localhost', PORT))


def clear():
    import os

    try:
        os.remove(CACHE_PATH)
    except FileNotFoundError:
        pass


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
