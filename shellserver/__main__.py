if __name__ == "__main__":
    import multiprocessing as mp

    from . import server
    from .gitinfo.git_exe import worker

    queue = mp.Queue()
    mp.Process(target=worker, args=(queue,)).start()

    server.mainloop(queue)
