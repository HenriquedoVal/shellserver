from __future__ import annotations

"""
This submodule provides an inline view of 'git status'
"""

import sys
import threading as th

from . import low, high


def _populate_status() -> None:
    try:
        status = obj.status()
    except high.FallbackError:
        status = obj.parse_git_status()

        if high.HAS_WATCHDOG and '--no-watchdog' not in sys.argv:
            high.observer.event_queue.join()
            obj.save_status_in_cache(status)

    except Exception:
        if '--let-crash' in sys.argv:
            raise
        status = obj.parse_git_status()

    status_list[0] = status


def _package_status(config) -> str | None:
    if '--git-linear' in sys.argv:
        _populate_status()
        status = status_list[0]
        if '--test-status' in sys.argv:
            git_status = obj.parse_git_status()
            status = f'{status} {git_status}'
        return status

    global thread

    status_list[0] = '...'

    if not thread.is_alive():
        thread = th.Thread(target=_populate_status)
        thread.start()

    if config:
        thread.join(timeout=config.git_timeout / 1000)
    else:
        thread.join(2.5)

    return status_list[0]


def gitstatus(
    target_path: str,
    config: dict
) -> tuple[str | None, str | None]:
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
        status = _package_status(config)

    return branch, status


status_list: list[str | None] = [None]
obj = high.High()
thread = th.Thread(target=_populate_status)
