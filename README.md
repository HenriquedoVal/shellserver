# ShellServer

It's a mix of [Starship](https://github.com/starship/starship) and [Zoxide](https://github.com/ajeetdsouza/zoxide) but faster.  
  
On Starship, every 'Enter' keystroke spawns a new process, which may cause a lag between prompts.  
Zoxide will raise a new process every time you call it.  
ShellServer raises the server only in the first shell creation and will _communicate_ with your shell on every 'Enter' keystroke.  
Fastness comes from not having spawning time, which seems to be way higher in Windows.  
  
But if your hardware gives you a fluid shell experience using Starship, I recommend that you keep with it because it's way more customizable.  

## Features
  
### Prompt with a fast glance at what is in the directory  

![Bloated](./images/bloated.png)  
This is the most bloated prompt that you will get.
It will indicate the existence of Python, C, C++, Lua, Node, and PowerShell files in the directory.  
The compilers searched are GCC and G++.  
  
### No lag from spawning processes  

![Fast](./images/even_bloated.gif)  
  
### Better 'cd'  

![p, pz](./images/p_pz.gif)
- `p -o path` for writing to output. Tool for things like `move somefile (p -o somepath)`  
- `p` behaves like `cd` for unknown paths
  
Note: [fzf](https://github.com/junegunn/fzf) is a dependency to use 'pz'  
  
### Switching Theme
  
![Switch-Theme](./images/switch_theme.gif)
Can take five different arguments: all, system, terminal, blue, and readline.  
- terminal: Toggles Windows Terminal default theme.
- system: Toggles system-wide Dark Mode.  
- blue: Toggles 'Blue light reduction'.  
- all: Same as not passing arguments. Do all the above.  
- readline: Toggles PSReadLine colors. 
  
The `system` option is not working properly on Windows 11 22h2...
  
### Searching history

![history](./images/history.gif)
The amount of data printed will be limited to fit the terminal.
- pass `-a` to get the full result
- `-c` to make the search case-sensitive
- `-ac` and `-ca` are allowed too

### Listing directory

![lss](./images/ll_la.gif)  

### Plugins

All those are relative to getting the git status.

- [watchdog](https://github.com/gorakhargosh/watchdog): Filesystem watcher. Makes better caching possible.
- [pygit2](https://github.com/libgit2/pygit2): libgit2 python bindings. Faster than using git itself.
- [ssd_checker](https://github.com/kipodd/ssd_checker): Solid-State Drive checker. Change the strategy accordingly to drive speed.  
  
Just `pip install` the ones you want, restart shellserver, and no further config is needed.


### Customization

The server will look for a `.shellserver.toml` in the user home directory.  
The most important option will be `git_timeout`.

~~~toml
git_timeout = 500  # in ms, defaults to 2500
# the best value is really hardware dependent
# if you have watchdog, I would recommend something around 100
# if you don't and the value is too low you might get no status over and over: `[...]`
~~~
See the [example](./.shellserver.toml) for more and the defaults.
  
## CLI

The server knows how many clients it haves and will know if you quit the shell with 'exit'  
but if the window or tab is closed on the 'X' button it may outlive the shell. 

~~~
usage: shellserver [-h] {kill,clear}

positional arguments:
  {kill,clear}  "kill" to kill the server, "clear" to clear the cache.

options:
  -h, --help    show this help message and exit
~~~

## Requirements

- Python 3.9+ or latest [Pypy](https://www.pypy.org/) (still slower than Python 3.11)
- PowerShell 6.2+ (I think)
- Any NerdFont (I use MesloLGS NF)
- A xterm compatible terminal

## Installation

ShellServer will work only in PowerShell on Windows.

~~~PowerShell
> pip install shellserver  # or pip install --user shellserver
> Install-Module ShellServer -Scope CurrentUser
~~~

In your PowerShell profile:
~~~PowerShell
# By the beginning of the file
pythonw -m shellserver  # note the 'w'

# By the end of the file
Import-Module ShellServer
~~~

### Keep updated
As many things might change in versions below 0.1.0, consider upgrading both when one changes.
~~~PowerShell
> pip install --upgrade shellserver
> Update-Module ShellServer
~~~
v0.0.8+ will work with the PowerShell ShellServer module 0.0.6+.

## Debugging

All initial '--' are optional.  
The git status info is still experimental, do `pythonw -m shellserver --use-git` in your profile to always use git. 
If you have installed pygit2, you can pass `--use-pygit2` instead, which is faster than `--use-git`.  

Any errors that occur will be saved in `$env:localappdata\shellserver\traceback`.  
  
Attach a _stdout_ to the server, pass `--timeit` to it and it will give the time taken for each communication.  
Use `output=stdout` to get some info on git repo. You can pass `output=C:\path\to\file` too.  
~~~
> shellserver kill
# A message that the server is not responding and your prompt will be like before.
> python -m shellserver --timeit --output=stdout  # no w, blocking
~~~
Open another shell and walk to a git repo.  
  
There are also: 
- --no-fallback: We will use our 'gitstatus' subpackage for repos up to 2500 index entries (in ssd, 1000 otherwise if ssd_checker is present). Will use git otherwise, unless this flag is set.
- --no-watchdog: Disables Watchdog plugin
- --disable-git
- --use-git  # instead of gitstatus subpackage
- --use-pygit2
- --linear: Fill gitstatus synchronously
- --multiproc: Very beta and will not be updated
- --read-async: Speed increase but error-prone
- --let-crash: At this point, it's probably useless
- --test-status: Put gitstatus subpackage result and git.exe status side-by-side

Pwsh module cmdlets:
- `Switch-ServerTimeout`: arg in ms. 
- `Switch-ServerOpt`: Sets most of the argv options in runtime:
    - use-git
    - use-gitstatus: Use gitstatus subpackage for git status info
    - use-pygit2
    - disable-git
    - enable-git
    - timeit
    - no-timeit
    - fallback
    - no-fallback
    - watchdog
    - no-watchdog
    - test-status
    - no-test-status
    - linear
    - no-linear
    - read-async
    - no-read-async
    - let-crash
