import os
import socket
import tempfile
import unittest

import shellserver
import shellserver.server


TEST_PORT = 7070

shellserver.CONFIG_PATH = tempfile.mkdtemp(prefix='shellserver_test_')
shellserver.APP_HOME = tempfile.mkdtemp(prefix='shellserver_test_')

shellserver.CACHE_PATH = os.path.join(shellserver.APP_HOME, 'test_cache')

server_addr = ('localhost', TEST_PORT)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(server_addr)
server = shellserver.server.Server(sock)

# it calls `gc.disable()`. `server.cleanup()` collects
# server.init_script()

client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


class TestShellServerUtilsDirCache(unittest.TestCase):
    """
    Tests for shellserver.utils.DirCache
    """

    @classmethod
    def setUpClass(cls):
        cls.testdir = tempfile.mkdtemp(prefix='shellserver_test_')
        cls.cache = shellserver.utils.DirCache()

    @classmethod
    def tearDownClass(cls):
        os.system(f'rmdir /s /q {cls.testdir}')

    def test_add(self):
        changed = self.cache.add(self.testdir)
        self.assertTrue(changed)

        changed = self.cache.add('J:\\')
        self.assertFalse(changed)  # False!

        changed = self.cache.add('j:\\;given_ref')
        self.assertTrue(changed)

        changed = self.cache.add('j:\\;other_ref')
        self.assertTrue(changed)

        os.system(f'rmdir /s /q {self.testdir}')

    def test_delete(self):
        changed = self.cache.delete(self.testdir, abs_path=True)
        self.assertTrue(changed)


if __name__ == "__main__":
    unittest.main()
    os.system(f'rmdir /s /q {shellserver.APP_HOME}')
    os.system(f'rmdir /s /q {shellserver.CONFIG_PATH}')
