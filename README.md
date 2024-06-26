# ShellServer

It's a mix of [Starship](https://github.com/starship/starship) and [Zoxide](https://github.com/ajeetdsouza/zoxide) made to be faster on Windows.  
  
The common approach of piping binaries outputs is almost free on
Linux but this is not true on Windows, the cost of raising processes is
way higher and long living processes are preferred.  

On Starship, every 'Enter' keystroke spawns a new process, which may cause a lag between prompts.  
Zoxide will raise a new process every time you call it.  
ShellServer raises the server only in the first shell creation and will _communicate_ with your shell on every 'Enter' keystroke.  
  
But if your hardware gives you a fluid shell experience using Starship, I recommend that you keep with it because it's way more customizable.  

## Features
  
### Prompt with a fast glance at what is in the directory  

![Bloated](./images/bloated.png)  
This is a sample of the prompt that you will get.
It will indicate the existence of Python, C, C++, C#, Lua, Node, PowerShell, Rust, and Java files in the directory.  
The C compilers searched are GCC and G++.  
  
### No lag from spawning processes  

![Fast](./images/even_bloated.gif)  
  
### Better 'cd'  

![p, pz](./images/p_pz.gif)
<details>
<summary>Options</summary>

- `p path -o`: For writing to output. Tool for things like `move somefile (p -o somepath)`.
- `p path -j`: Go to the Junction of the given `path`
- `p -d path`: Purges given relative or full paths from known paths.
- `p -dr refpath`: Deletes only the given `refpath` from known paths.
- `p -a path`: Manually add given `path` to tracked dirs.
- `p -a path -as given_name`: Will use `given_name` to jump to `path`.
- `p` behaves like `cd` for relative paths.  
Invocations like `p -d . -dr someref -a . -as anyname anyref -j -o` are allowed, but doesn't make much sense.  
It would remove all references to the current dir, delete `someref`, add the current dir as `anyname`, and write the junction
of `anyref` to the output...
</details>
  
### Switching Theme
  
![Switch-Theme](./images/switch_theme.gif)
The name changed to `Switch-ShellServerTheme`.  
<details>
<summary>Options</summary>

Switches colors to conform with light/dark themes.  
Can take five arguments: system, terminal, blue, prompt, and readline.  
- system: Toggles system-wide Light/Dark Mode.  
- terminal: Toggles Windows Terminal default theme.
- blue: Toggles 'Blue light reduction'.  
- prompt: Toggles prompt colors. 
- readline: Toggles PSReadLine colors. 
  
The `system` option is not working properly on Windows 11 22h2...

</details>
  
### Searching history

![history](./images/history.gif)
The name changed to `Search-ShellServerHistory`.  
<details>
<summary>Options</summary>

The amount of data printed will be limited to fit the terminal.
- pass `-a` to get the full result
- `-c` to make the search case-sensitive
- `-ac` and `-ca` are allowed too
</details>

### Listing directory

![lss](./images/ll_la.gif)  

<details>
<summary>Options</summary>

There are several switches. See `help ll`.
`ll -List -Icons -Color` will use these options for the current execution.  
An additional `-SetDefault` will make your flags persist.  
Use `-NoOutput` if you want to set it in $profile.  
  
Most flags can be aliased like:  
`ll -l -ac -he`  
Or prepending `-o` plus the initial of the flag:  
`ll -o acilmhCAH`  
  
Meaning:  
a: all files  
c: colors  
i: icons  
l: list  
m: modified time  
h: headers  
C: creation time  
A: access time  
H: hour  

</details>

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
# The best value is hardware-dependent.
# If you have watchdog, I would recommend something around 100,
# if you don't and the value is too low you might get no status over and over: `[...]`
~~~
See the [example](./.shellserver.toml) for more and the defaults.
  
## CLI

The server knows how many clients it has and will know if you quit the shell with 'exit'  
but if the window or tab is closed on the 'X' button it may outlive the shell. 

~~~
usage: shellserver <COMMAND> [Args]
       shellserver {kill|sync|clear|dump}
       shellserver run [Args]

shellserver gives some functionalities for better navigation on PowerShell

commands:

    run       Run the server.
    kill      Kill the server.
    sync      Clear useless entries and write cache to disk.
    clear     Delete the server cache.
    dump      Dump the server cache to stdout.

options:
  -h, --help  show this help message and exit
~~~

## Requirements

- Python 3.10+ (CPython 3.11+ recommended)
- PowerShell 7.4.1+
- Any NerdFont (I use MesloLGS NF [patched](https://github.com/romkatv/powerlevel10k/blob/master/font.md))
- A xterm compatible terminal

## Installation

ShellServer will work only in PowerShell on Windows.

~~~PowerShell
> pip install shellserver  # or pip install --user shellserver
> Install-Module ShellServer -Scope CurrentUser -AllowClobber
~~~

### Setup the server

There is a [helper script](./on_startup.ps1) to set the server to run on startup.
Alternatively, you can start the server manually with:
- `shellserverw run`: Does not create output terminal
- `shellserver run`
  
### Setup the client

Add `Import-Module ShellServer` by the end of your PowerShell profile.  

### Keep updated

As many things might change in versions below 0.1.0, consider upgrading both when one changes.
~~~PowerShell
> shellserver kill
> Remove-Module ShellServer

> pip install --upgrade shellserver
> Update-Module ShellServer

> Start-ScheduledTask ShellServer
> Import-Module ShellServer
~~~
Last break: Client (PowerShell module) v0.1.1 and Server (Python) v0.0.18.

## Debugging

All initial '--' are optional.  
The git status info is still experimental, do `pythonw -m shellserver --use-git` in your profile to always use git. 
If you have installed pygit2, you can pass `--use-pygit2` instead, which is faster than `--use-git`.  

Any errors that occur will be saved in `$env:localappdata\shellserver\traceback`.  
  
Attach a _stdout_ to the server, pass `--timeit` to it and it will give the time taken for each communication.  
Use `output=stdout` to get some info on the git repo. You can pass `output=C:\path\to\file` too.  
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
- --linear: Fill gitstatus info synchronously
- --multiproc: Very beta and will not be updated
- --no-read-async
- --let-crash: At this point, it's probably useless
- --test-status: Put gitstatus subpackage result and git.exe status side-by-side

Pwsh module cmdlets:

- `Get-ShellServerConfig`: get the current server config.
- `Get-ShellServerBuffer`: get output if it is set to 'buffer'. Pass `-k` to keep the content in memory.
- `Switch-ShellServerTimeout`: arg in ms. 
- `Switch-ShellServerOptions`: Sets most of the argv options in runtime:
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
