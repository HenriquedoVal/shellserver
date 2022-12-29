class Dispatcher:
    """
    This class will hold the specifics convertions
    necessary to each shell, apply them and send
    data through socket.
    """
    __slots__ = 'addrs', 'funcs'

    def __init__(self):
        self.addrs = {}
        self.funcs = {'pwsh': self._pwsh_func}

    def register(self, addr: int, shell: str):
        self.addrs.update({addr: shell})

    def send_through(self, sock, data: str, addr: tuple[str, int]):
        shell = self.addrs.get(addr)
        func = self.funcs.get(shell)

        if func is not None:
            data = func(data)

        while data[60_000:]:
            msg = '1' + data[:60_000]
            sock.sendto(msg.encode(), addr)
            data = data[60_000:]

        msg = '0' + data

        sock.sendto(msg.encode(), addr)

    def _pwsh_func(self, data: str):
        return data.replace('$', '`$', -1)
