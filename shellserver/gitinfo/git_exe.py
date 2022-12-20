def worker(q):
    import os
    from .low import parse_git_status

    while 1:
        git_dir = q.get()
        if not git_dir:
            return

        data = os.popen(f'git -C {git_dir} status -s').read()
        result = parse_git_status(data)
        q.put(result)
