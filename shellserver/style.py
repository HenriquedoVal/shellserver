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


def resolve_duration(seconds: float) -> str:
    # return like: 2h, 1h3m, 4m, 2m5s, 58.4s
    minutes = int(seconds / 60)
    hours, minutes = int(minutes / 60), minutes % 60
    seconds = seconds % 60

    res = ''
    for val, unit in zip((hours, minutes, seconds), ('h', 'm', 's')):
        if unit == 's' and not res and val > 2:
            res += f'{val}{unit}'
        elif unit == 's' and 'h' in res:
            break
        else:
            if val and ((unit == 's' and (val > 2 or res)) or unit != 's'):
                res += f'{int(val)}{unit}'

    return res


# maybe will be relevant:    
def style(
    cwd: str,
    link: str,
    git: int | bool,
    brackets: list,
    after: list,
    no_error: int | bool,
    width: int,
    duration: float
) -> str:

    result = ''

    equal = cwd == link

    if cwd == '~':
        cwd = ' ' + cwd
    elif cwd.startswith(os.environ['HOMEDRIVE']):
        cwd = ' ' + cwd
    else:
        cwd = ' ' + cwd

    result += colors_map['Cwd'] + cwd + colors_map['reset'] + ' '

    if not equal:
        result += (
            colors_map['Link']
            + ' '
            + colors_map['Cwd']
            + link
            + colors_map['reset']
            + ' '
        )

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
    # clock: 2, space, hh:mm:ss -> 11

    for char in chars_with_double_lenght:
        if char in result:
            width -= 1

    duration = resolve_duration(duration)
    if duration:
        width -= len(duration) + 3  # symbol, space before, space after
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


chars_with_double_lenght = '🌙🕓'

# this antipattern makes easier to know the 'length' of chars
symbols_map = {
    'Git': '',
    'Branch': '',
    'Python': '',
    'Lua': '🌙',
    'Node': '',
    'C': '',
    'Cpp': '',
    'Pwsh': '',  # maybe  
    'Status': '',
    'Clock': '🕓',
    'Duration': ''
}

light_colors = {
    'Cwd': "\x1b[36m",
    'Link': "\x1b[90m",
    'Git': "\x1b[31m",
    'Branch': "\x1b[35m",
    'Python': "\x1b[33m",
    'Lua': "\x1b[34m",
    'Node': "\x1b[32m",
    'C': "\x1b[34m",
    'Cpp': "\x1b[34m",
    'Pwsh': "\x1b[34m",
    'Status': "\x1b[31m",
    'reset': "\x1b[0m",
    'no_error': "\x1b[32m",
    'error': "\x1b[31m"
}

dark_colors = {
    'Cwd': "\x1b[96m",
    'Link': "\x1b[90m",
    'Git': "\x1b[91m",
    'Branch': "\x1b[95m",
    'Python': "\x1b[93m",
    'Lua': "\x1b[94m",
    'Node': "\x1b[32m",
    'C': "\x1b[34m",
    'Cpp': "\x1b[94m",
    'Pwsh': "\x1b[94m",
    'Status': "\x1b[91m",
    'reset': "\x1b[0m",
    'no_error': "\x1b[92m",
    'error': "\x1b[91m"
}

colors_map = dark_colors if darkdetect.isDark() else light_colors

t = threading.Thread(target=darkdetect.listener, args=(darkdetect_callback,))
t.daemon = True
t.start()
