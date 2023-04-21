from __future__ import annotations

"""
Interface for shellserver.

set_config()
init()
gitstatus(path)
...
"""

import io
import os
import threading as th
from typing import Any

from . import high
from . import plugins

OS_CPU_COUNT = os.cpu_count() or 1


class Config:
    use_git: bool = False
    use_pygit2: bool = False
    git_timeout: int = 2500
    let_crash: bool = False
    test_status: bool = False  # used only when linear == True
    linear: bool = False
    watchdog: bool = True
    multiproc: bool = False
    workers: int = OS_CPU_COUNT - 1
    read_async: bool = False
    fallback: bool = True
    output: io.TextIOWrapper | io.StringIO | None = None


interface_only = {
    'use_git', 'use_pygit2',
    'git_timeout', 'let_crash', 'test_status'
}
both = {
    'linear', 'watchdog'
}
instance_only = {
    'multiproc', 'workers', 'read_async', 'fallback', 'output'
}


def gitstatus(target_path: str) -> tuple[str | None, str | None]:
    """
    Highest level function that gets an inline version of
    'git status'.
    param `target_path`: The path where the search for git info begins.
    """

    git_dir = _get_dot_git(target_path)

    if git_dir is not None and _exists_head(git_dir):
        branch = _get_branch_on_head(git_dir)
    else:
        return None, None

    _Globals.obj.init(git_dir, branch)

    if Config.use_git:
        status = _Globals.obj.parse_git_status()

    elif Config.use_pygit2:
        print('pygit')
        status = _Globals.obj.parse_pygit2()

    else:
        status = _package_status()

    return branch, status


def update_conf(opt: str, val: bool) -> None:
    if opt in interface_only:
        setattr(Config, opt, val)
    elif opt in both:
        setattr(Config, opt, val)
        setattr(_Globals.obj, opt, val)
    elif opt in instance_only:
        setattr(_Globals.obj, opt, val)


def set_config(Cls_config: Any) -> None:
    """
    Param config can be of any class with class variables.
    Raise no errors on unneeded ones.
    """
    for config, value in Cls_config.__dict__.items():
        if config.startswith('__'):
            continue

        setattr(Config, config, value)


def init() -> None:
    config = {
        name: value
        for name, value in Config.__dict__.items()
        if name[:2] != '__'
    }
    _Globals.obj = high.High(**config)


def _populate_status() -> None:
    try:
        status = _Globals.obj.status()
    except high.FallbackError:
        status = _Globals.obj.parse_git_status()

        if plugins.HAS_WATCHDOG and Config.watchdog:
            plugins.observer.event_queue.join()
            _Globals.obj.save_status_in_cache(status)

    except Exception:
        if Config.let_crash:
            raise
        status = _Globals.obj.parse_git_status()

    _Globals.g_status = status


def _package_status() -> str | None:
    if Config.linear:
        _populate_status()
        status = _Globals.g_status
        if Config.test_status:
            git_status = _Globals.obj.parse_git_status()
            status = f'{status} {git_status}'
        return status

    _Globals.g_status = '...'

    if not _Globals.thread.is_alive():
        _Globals.thread = th.Thread(target=_populate_status)
        _Globals.thread.start()

    _Globals.thread.join(timeout=Config.git_timeout / 1000)

    return _Globals.g_status


def _get_dot_git(target_path: str) -> str | None:
    git = os.path.join(target_path, '.git')
    if os.path.exists(git):
        return target_path

    parent = os.path.dirname(target_path)
    if parent == target_path:
        return None

    return _get_dot_git(parent)


def _exists_head(git_dir: str) -> bool:

    head = os.path.join(git_dir, '.git/HEAD')
    return os.path.exists(head)


def _get_branch_on_head(git_dir: str) -> str:
    head_path = os.path.join(git_dir, '.git/HEAD')

    with open(head_path) as head:
        content = head.read()

    return content[content.rindex('/') + 1:].strip()


class _Globals:
    obj: high.High
    thread: th.Thread = th.Thread(target=_populate_status)
    g_status: str | None = None
