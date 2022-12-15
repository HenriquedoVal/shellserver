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
        # for now, treat every call as pwsh call
        shell = self.addrs.get(addr, 'pwsh')
        func = self.funcs[shell]
        sock.sendto(func(data).encode(), addr)

    def _pwsh_func(self, data: str):
        return data.replace('$', '`$', -1).replace('\x1b', '`e', -1)
