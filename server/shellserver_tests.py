import os
import socket
import tempfile
import unittest

import shellserver
import shellserver.server


TEST_PORT = 7070

shellserver.CONFIG_PATH = tempfile.mkdtemp(prefix='shellserver_test_config_')
shellserver.APP_HOME = tempfile.mkdtemp(prefix='shellserver_test_app_home_')
shellserver.CACHE_PATH = os.path.join(shellserver.APP_HOME, 'test_cache')

server_addr = ('localhost', TEST_PORT)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(server_addr)
server = shellserver.server.Server(sock)

client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


class TestShellServerUtilsDirCache(unittest.TestCase):
    """
    Tests for shellserver.utils.DirCache
    """

    @classmethod
    def setUpClass(cls):
        cls.testdir = tempfile.mkdtemp(prefix='shellserver_test_case_')
        cls.cache = shellserver.utils.DirCache()

    @classmethod
    def tearDownClass(cls):
        os.system(f'rmdir /s /q {cls.testdir}')

    def test_add(self):
        changed = self.cache.add(self.testdir)
        self.assertTrue(changed)

        changed = self.cache.add('J:\\')
        self.assertFalse(changed)

        changed = self.cache.add('j:\\;given_ref')
        self.assertTrue(changed)

        changed = self.cache.add('j:\\;other_ref')
        self.assertTrue(changed)

    def test_delete(self):
        changed = self.cache.delete(self.testdir, abs_path=True)
        self.assertTrue(changed)


def tearDownModule():
    os.system(f'rmdir /s /q "{shellserver.CONFIG_PATH}"')
    os.system(f'rmdir /s /q "{shellserver.APP_HOME}"')


if __name__ == "__main__":
    unittest.main()
