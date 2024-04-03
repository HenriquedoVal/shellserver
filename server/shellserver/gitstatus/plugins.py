__all__ = (
    'HAS_PYGIT2',
    'HAS_SSD_CHECKER',
    'DRIVE_SSD_MAP',
    'pygit2',
    'FileSystemEvent'
)

try:
    import pygit2
    HAS_PYGIT2 = True
except ImportError:
    HAS_PYGIT2 = False

    class pygit2:  # dummy
        Repository = None

try:
    DRIVE_SSD_MAP: dict[str, bool] = {}

    from ssd_checker import is_ssd  # fail fast

    # pywin32 is dep of ssd_checker
    from pythoncom import CoInitialize

    from ctypes import windll
    from string import ascii_uppercase
    from threading import Thread

    def populate(letter: str) -> None:
        CoInitialize()
        DRIVE_SSD_MAP[letter] = is_ssd(letter)

    bitmask = windll.kernel32.GetLogicalDrives()
    for letter in ascii_uppercase:
        if bitmask & 1:
            letter = letter + ':'
            Thread(
                target=populate, args=(letter,), daemon=True
            ).start()
        bitmask >>= 1

    HAS_SSD_CHECKER = True

except ImportError:
    HAS_SSD_CHECKER = False

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEvent
    observer = Observer()
    observer.start()
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

    class FileSystemEvent:
        ...
