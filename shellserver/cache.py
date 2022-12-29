import os
import pickle
import threading

from .__init__ import CACHE_PATH, SEP


class DirCache:
    __slots__ = 'dirs', 'flag'

    # dirs = list[list[precedence: int, abs_path: str, short_path: str]]
    def __init__(self):
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, 'rb') as in_file:
                self.dirs = pickle.load(in_file)
            self._clear()
        else:
            self.dirs = []

            # Need to create file or cache will never save
            # if it doesn't exist.
            # Need to put something there or server might break
            # when pickle tries to read an empty file.
            with open(CACHE_PATH, 'wb') as in_file:
                pickle.dump([], in_file)

        self.flag = False  # New paths were added to cache?

    def add(self, path: str) -> None:
        for item in self.dirs:
            if item[1] == path:
                break
        else:
            out = path[path.rindex(SEP) + 1:].lower()
            if not out:
                out = path.strip(SEP).lower()

            self.dirs.append([0, path, out])

            # just want to set flag if it is false to start thread
            # that will capture WM_SAVE_YOURSELF
            if not self.flag:
                self.flag = True
                threading.Thread(target=self._signal_cap, daemon=True).start()

    def get(self, rel_path: str) -> str:
        for item in self.dirs:
            if item[2] == rel_path:
                return item[1]
        return ''

    def update_by_full_path(self, full_path: str) -> None:
        for ind in range(len(self.dirs)):
            if self.dirs[ind][1] == full_path:
                self.dirs[ind][0] += 1
                break

    def finish(self):
        self._clear()
        self._save()

    def sort(self) -> None:
        self.dirs.sort(key=lambda x: x[0], reverse=True)

    def _save(self) -> None:
        # if there were calls to clear the cache during this runtime
        if not os.path.exists(CACHE_PATH):
            return
        if self.flag:
            with open(CACHE_PATH, 'wb') as out:
                pickle.dump(self.dirs, out, protocol=5)

    def _clear(self) -> None:
        aux = []
        for item in self.dirs:
            if not os.path.exists(item[1]):
                aux.append(item)
        if aux:
            self.flag = True
        for item in aux:
            self.dirs.remove(item)

    def _signal_cap(self):
        import tkinter as tk

        def finish():
            self.finish()
            self.flag = False  # will make new threads possible
            raise SystemExit

        root = tk.Tk()
        root.withdraw()
        root.protocol('WM_SAVE_YOURSELF', finish)
        root.mainloop()
