from .__init__ import PORT, APP_HOME, CACHE_PATH


HELP_MSG = (
    '''
usage: shellserver <COMMAND> [Args]
       shellserver {kill|sync|clear|dump}
       shellserver run [Args]

shellserver gives some functionalities for better navigation on PowerShell

commands:

    run       Run the server.
    kill      Kill the server.
    sync      Clear useless entries and write cache to disk.
    clear     Delete the server cache.
    dump      Dump the server cache to stdout.

options:
  -h, --help  show this help message and exit'''
)


def run():
    from shellserver import __main__


def send(msg: bytes):
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.sendto(b'2' + msg, ('127.0.0.1', PORT))


def clear():
    import os

    for file in ('ShellServerCache', 'traceback'):
        file_path = os.path.join(APP_HOME, file)
        if os.path.exists(file_path):
            os.remove(file_path)

    os.removedirs(APP_HOME)


def dump():
    import os
    import pickle

    try:
        from rich import print
    except ImportError:
        from pprint import pprint as print

    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, 'rb') as file:
            content = pickle.load(file)

        print(content)


def main():
    import sys

    prog, *initial_args = sys.argv
    if not initial_args:
        print(HELP_MSG)
        sys.exit(1)

    for entry in initial_args:
        if entry in ('-h', '--help'):
            print(HELP_MSG)
            sys.exit(1)

    cmd, *args = initial_args

    if cmd == 'run':
        run()
    elif cmd == 'kill':
        send(b'Kill')
    elif cmd == 'sync':
        send(b'Sync')
    elif cmd == 'clear':
        clear()
    elif cmd == 'dump':
        dump()
    else:
        print("Unknown command.")
        print(HELP_MSG)
        sys.exit(1)
