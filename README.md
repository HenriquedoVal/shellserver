# ShellServer

It's a mix of [Starship](https://github.com/starship/starship) and [Zoxide](https://github.com/ajeetdsouza/zoxide) but faster.  
  
On Starship, every 'Enter' keystroke spawns a new process, which may cause a lag between prompts.  
Zoxide will raise a new process every time you call it.  
ShellServer raises the server only in the first shell creation and will _communicate_ with your shell on every 'Enter' keystroke.  
Fastness comes from not having spawning time, which seems to be way higher in Windows.  
  
But if your hardware gives you a fluid shell experience using Starship, I recommend that you keep with it because it's way more customizable.  

## Features
  
### Prompt with a fast glance at what is in directory  

![Bloated](./images/bloated.png)  
This is the most bloated prompt that you will get.
It will indicate the existence of Python, C, C++, Lua, Node and PowerShell files on directory.  
The compilers searched are GCC and G++.  
  
### No lag from spawning processes  

![Fast](./images/even_bloated.gif)  
  
### Better 'cd'  

![p, pz](./images/p_pz.gif)
- Tab completions works just fine.
- With no arguments will behave just like 'cd'.
- `p -o path` for writing to output. Tool for things like `move somefile (p -o somepath)`  
Note: [fzf](https://github.com/junegunn/fzf) is a dependency to use 'pz'  
  
### Switching Theme
  
![Switch-Theme](./images/switch_theme.gif)
Can take four arguments: all, system, terminal, and blue.  
- terminal: Toggles Windows Terminal default theme between 'Tango Dark' and 'Solarized Light'.  
- system: Toggles system wide Dark Mode.  
- blue: Toggles 'Blue light reduction'.  
- all: Same as not passing arguments. Do all the above.
  
### Searching history

![history](./images/history.gif)

### Listing directory

![lss](./images/ll_la.gif)  
  
## CLI

The server knows how many clients it haves and will know if you quit shell with 'exit'  
but if window is closed on 'X' it may outlive the shell. 

~~~
usage: shellserver [-h] {kill,clear}

positional arguments:
  {kill,clear}  "kill" to kill the server, "clear" to clear the cache.

options:
  -h, --help    show this help message and exit
~~~

## Requirements

- Python 3.10+
- PowerShell 6.2+ (I think)
- Any NerdFont (I use MesloGS NF)
- A xterm compatible terminal

## Installation

Currently, ShellServer will work only in PowerShell on Windows. A few things must change to make it work on Linux, so make an Issue if you want to use it.

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
As many things might change in versions below 0.1.0, `pip install --upgrade shellserver` and `Upgrade-Module ShellServer` must be run both when one changes.  
v0.0.8+ will work with the PowerShell ShellServer module 0.0.6+.

## Debugging

The git status info still experimental, do `pythonw -m shellserver --use-git` in your profile to always use git. 

Any errors that occur will be saved in `$env:localappdata\shellserver\traceback`.  
  
Attach a _stdout_ to the server, pass `--verbose` to it and it will give lot of info when it sees a git repo.
~~~
shellserver kill
# A message that the server is not responding and your prompt will be like before.
python -m shellserver --verbose  # no w, blocking
~~~
Open another shell and walk to a git repo.  
  
The server can accept `--let-crash` argument to let errors propagate. `--use-git` will have preference over this.
