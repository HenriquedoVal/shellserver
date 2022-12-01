# ShellServer

It's a mix of [Starship](https://github.com/starship/starship) and [Zoxide](https://github.com/ajeetdsouza/zoxide) but faster.  
  
On Starship, every 'Enter' keystroke spawns a new process, which may cause a lag between prompts.  
Zoxide will raise a new process every time you call it.  
ShellServer raises the server only in the first shell creation and will _communicate_ with your shell on every 'Enter' keystroke.  
  
But if your hardware gives you a fluid shell experience using Starship, I recommend that you keep with it because it's way more customizable.  

## Features
  
### Prompt with the fast glance on what is on directory  

![Bloated](./images/bloated.png)  
This is the most bloated prompt that you will get.
Will indicate the existence of Python, C, C++, Lua and Node files on directory.  
The compilers searched are GCC and G++.  
  
### No lag from spawing process  

![Fast](./images/even_bloated.gif)  
  
### Better 'cd'  

![p, pz](./images/p_pz.gif)  
Note: [fzf](https://github.com/junegunn/fzf) is a dependency to use 'pz'  
  
### Listing directory

![lss](./images/ll_la.gif)  
  
## CLI

The server knows how many clients it haves and will know if you quit shell with 'exit'  
but if window is closed on 'X', it may outlive the shell. 

~~~
usage: shellserver [-h] {kill,clear}

positional arguments:
  {kill,clear}  "kill" to kill the server, "clear" to clear the cache.

options:
  -h, --help    show this help message and exit
~~~

## Requirements

- Python 3.10+
- PowerShell 5+ (I think)
- Any NerdFont (I use MesloGS NF)

## Installation

Currently, ShellServer will work only in PowerShell on Windows. A few things must be changed to make it work on Linux, so make an Issue if you want to use it. There are plans to get it to [Xonsh](https://github.com/xonsh/xonsh)

~~~PowerShell
> pip install shellserver  # or pip install --user shellserver
> Install-Module ShellServer -Scope CurrentUser
~~~

In your PowerShell profile:
~~~PowerShell
# By the beginning of the file
pythonw -m shellserver  # note the 'w'

# In some pwsh versions 'ls' is an alias to Get-Children
Remove-Alias ls

#
# Other things. Must give time to bind the port
#

# By the end of the file
Import-Module ShellServer
~~~

## Known Issues

- Git status brackets might give wrong values for now. ShellServer won't parse 'git status' command for it would threat performance, it deals with files directly.
- Prompt might be unstructured on small window.
