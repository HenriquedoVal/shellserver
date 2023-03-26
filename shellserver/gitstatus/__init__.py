"""
This submodule provides an inline view of 'git status'
"""

import sys
import threading as th

from . import low, high


def _populate_status():
    try:
        status = obj.status()
    except high.FallbackError:
        status = obj.parse_git_status()

        if high.HAS_WATCHDOG:

            # TODO: implement some kind of idleness checker for wathdog thread
            # before saving cache

            obj.save_status_in_cache(status)

    except Exception:
        if '--let-crash' in sys.argv:
            raise
        status = obj.parse_git_status()

    status_list[0] = status


def gitstatus(
    target_path: str,
    config: dict = None
) -> tuple[str, str]:
    """
    Highest level function that gets an inline version of
    'git status'.
    param `target_path`: The path where the search for git info begins.
    return: tuple of two strings: The branch and the status of it.
    """

    if '--disable-git' in sys.argv:
        return None, None

    git_dir = low.get_dot_git(target_path)

    if git_dir is not None and low.exists_head(git_dir):
        branch = low.get_branch_on_head(git_dir)
    else:
        return None, None

    obj.init(git_dir, branch)

    if '--use-git' in sys.argv:
        status = obj.parse_git_status()

    elif '--use-pygit2' in sys.argv:
        status = obj.parse_pygit2()

    else:
        global thread

        status_list[0] = '...'

        if not thread.is_alive():
            thread = th.Thread(target=_populate_status)
            thread.start()

        if config is not None:
            thread.join(timeout=config.git_timeout / 1000)
        else:
            thread.join(2.5)

        status = status_list[0]

    return branch, status


obj = high.High()
status_list = [None]
thread = th.Thread(target=_populate_status)
