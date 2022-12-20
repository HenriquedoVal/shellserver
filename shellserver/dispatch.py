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

    def send_through(self, sock, data: str, addr: int):
        shell = self.addrs.get(addr)
        func = self.funcs.get(shell)

        if func is not None:
            data = func(data)

        if len(data) > 60000:
            data = data[:data.index('\n', 60000)] + '\nOverflow'

        sock.sendto(data.encode(), addr)

    def _pwsh_func(self, data: str):
        return data.replace('$', '`$', -1).replace('\x1b', '`e', -1)
