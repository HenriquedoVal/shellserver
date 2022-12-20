from . import low, high


def gitinfo(
    target_path: str,
    queue
) -> tuple[str, tuple[int, int, int, int]]:

    git_dir = low.get_dot_git(target_path)

    if git_dir is not None and low.exists_head(git_dir):
        branch = low.get_branch_on_head(git_dir)
    else:
        return None, None

    if low.exists_packs(git_dir):
        queue.put(git_dir)
        res = queue.get()
    else:
        res = high.status(git_dir)

    status = stringfy_status(res)

    return branch, status


def stringfy_status(status: tuple[int, int, int, int]) -> str:
    if not any(status):
        return  # noqa

    res = ''
    symbols = ('?', '+', 'm', 'x')

    for stat, symb in zip(status, symbols):
        if stat:
            res += symb + str(stat) + ' '

    return res.strip()
