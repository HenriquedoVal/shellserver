"""
This submodule provides an inline view of 'git status'
"""

import sys

from . import low, high


def gitstatus(
    target_path: str,
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

    try:
        if '--use-git' in sys.argv:
            raise high.FallbackError
        obj = high.High(git_dir, branch)
        status = obj.status()

    except high.FallbackError:
        obj = low.Low()
        obj.git_dir = git_dir
        status = obj.parse_git_status()

    except Exception:
        if '--let-crash' in sys.argv:
            raise
        obj = low.Low()
        obj.git_dir = git_dir
        status = obj.parse_git_status()

    return branch, status
