import socket

from . __init__ import PORT, APP_HOME

# Quit program as soon as possible
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', PORT))
except OSError:
    raise SystemExit

from .server import Server

server = Server(sock)
server.init_script()

try:
    server.mainloop()
except Exception:
    import traceback
    import time

    with open(APP_HOME + '/traceback', 'w') as out:
        print(time.ctime(), file=out)
        print(traceback.format_exc(), file=out)

    raise
