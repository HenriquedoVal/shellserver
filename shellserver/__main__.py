from . import server

try:
    server.mainloop()
except Exception:
    import traceback
    from .__init__ import APP_HOME

    with open(APP_HOME + '/traceback', 'w') as out:
        print(traceback.format_exc(), file=out)
