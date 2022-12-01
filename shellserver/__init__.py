import os

PORT = 5432
SEP = os.path.sep
APP_HOME = os.environ['LOCALAPPDATA'] + SEP + 'ShellServer'
CACHE_PATH = APP_HOME + SEP + 'ShellServerCache'
