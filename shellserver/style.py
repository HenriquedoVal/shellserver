import os
import threading
from datetime import datetime

import darkdetect


def darkdetect_callback(arg):
    global colors_map

    if colors_map is dark_colors:
        colors_map = light_colors
    else:
        colors_map = dark_colors


def style(
    cwd: str,
    git: int | bool,
    brackets: list,
    after: list,
    no_error: int | bool,
    width: int,
    duration: float
) -> str:

    result = ''

    if cwd == '~':
        cwd = ' ' + cwd
    elif cwd.startswith(os.environ['HOMEDRIVE']):
        cwd = ' ' + cwd
    else:
        cwd = ' ' + cwd

    result += colors_map['Cwd'] + cwd + colors_map['reset'] + ' '

    if git:
        result += (
            colors_map['Git'] + symbols_map['Git'] + colors_map['reset'] + ' '
        )

    for item in brackets:
        symbol, text = item.split(';')

        result += '[' + colors_map[symbol] + symbols_map[symbol]
        if symbol != 'Status':
            result += ' '
        result += text + colors_map['reset'] + '] '

    for item in after:
        result += (
            colors_map[item] + symbols_map[item] + colors_map['reset'] + ' '
        )

    # get the lenght of written so far
    aux = result
    for item in colors_map:
        aux = aux.replace(colors_map[item], '', -1)
    width -= len(aux) + 11  # will be the size of datetime.now

    for char in chars_with_double_lenght:
        if char in result:
            width -= 1

    if duration > 2:
        width -= len(str(duration)) + 3
        result += ' ' * width + symbols_map['Duration'] + f' {duration} '
    else:
        result += ' ' * width

    time_str = datetime.now().strftime('%H:%M:%S')
    result += symbols_map['Clock'] + ' ' + time_str

    if no_error:
        result += colors_map['no_error']
    else:
        result += colors_map['error']

    result += '❯ ' + colors_map['reset']

    return result


chars_with_double_lenght = '🐍🌙🕓'

symbols_map = {
    'Git': '',
    'Branch': '',
    'Python': '🐍',
    'Lua': '🌙',
    'Node': '',
    'C': 'C',
    'Cpp': 'C++',
    'Status': '',
    'Clock': '🕓',
    'Duration': ''
}

light_colors = {
    'Cwd': "`e[36m",
    'Git': "`e[31m",
    'Branch': "`e[35m",
    'Python': "`e[33m",
    'Lua': "`e[34m",
    'Node': "`e[32m",
    'C': "`e[34m",
    'Cpp': "`e[34m",
    'Status': "`e[31m",
    'reset': "`e[0m",
    'no_error': "`e[32m",
    'error': "`e[31m"
}

dark_colors = {
    'Cwd': "`e[96m",
    'Git': "`e[91m",
    'Branch': "`e[95m",
    'Python': "`e[93m",
    'Lua': "`e[94m",
    'Node': "`e[32m",
    'C': "`e[34m",
    'Cpp': "`e[94m",
    'Status': "`e[91m",
    'reset': "`e[0m",
    'no_error': "`e[92m",
    'error': "`e[91m"
}

colors_map = dark_colors if darkdetect.isDark() else light_colors

t = threading.Thread(target=darkdetect.listener, args=(darkdetect_callback,))
t.daemon = True
t.start()
