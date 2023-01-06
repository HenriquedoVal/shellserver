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

    git_dir = low.get_dot_git(target_path)

    if git_dir is not None and low.exists_head(git_dir):
        branch = low.get_branch_on_head(git_dir)
    else:
        return None, None

    try:
        if '--use-git' in sys.argv:
            raise high.FallbackError
        status = high.status(git_dir, branch)

    except high.FallbackError:
        status = low.parse_git_status(git_dir)

    except Exception:
        if '--let-crash' in sys.argv:
            raise
        status = low.parse_git_status(git_dir)

    return branch, status
