import os
import threading
from datetime import datetime

import darkdetect

from .__init__ import SEP


def darkdetect_callback(arg):
    global colors_map

    if colors_map is dark_colors:
        colors_map = light_colors
    else:
        colors_map = dark_colors


def hide_first_dirs(path: str, from_depth: int) -> str:
    if path.count(SEP) <= from_depth:
        return path

    first_slice_end = path.index(SEP) + 1

    second_slice_start = len(path) - 1
    for _ in range(from_depth):
        second_slice_start = path.rindex(SEP, 0, second_slice_start)

    removed = path[first_slice_end:second_slice_start]
    ast = '*' * (1 + int(removed.count(SEP) > 0))

    res = path[:first_slice_end] + ast + path[second_slice_start:]
    return res


def reduce_big_path_names(path: str, max_size: int) -> str:
    names = path.split(SEP)

    for idx in range(len(names)):
        size = len(names[idx])
        if size > max_size:
            middle = int(max_size // 2)
            end_slice = middle - 1
            start_slice = size - middle + 1

            names[idx] = (
                names[idx][:end_slice]
                + '...'
                + names[idx][start_slice:]
            )

    return SEP.join(names)


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


def resolve_clocks(duration: float, width: int) -> str:
    res = resolve_duration(duration)
    if res:
        res = symbols_map['Duration'] + ' ' + res

    if width - len(res) - 11 >= 0:
        time_str = datetime.now().strftime('%H:%M:%S')
        if res:
            res += ' ' + symbols_map['Clock'] + ' ' + time_str
        else:
            res += symbols_map['Clock'] + ' ' + time_str

    return res


def style(
    cwd: str,
    link: str,
    git: int,  # | bool,
    brackets: list,
    after: list,
    no_error: int,  # | bool,
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

    cwd = hide_first_dirs(cwd, 5)
    cwd = reduce_big_path_names(cwd, 25)

    result += colors_map['Cwd'] + cwd + colors_map['Reset'] + ' '

    if not equal:
        link = hide_first_dirs(link, 5)
        link = reduce_big_path_names(link, 25)
        result += (
            colors_map['Link']
            + ' '
            + colors_map['Cwd']
            + link
            + colors_map['Reset']
            + ' '
        )

    if git:
        result += (
            colors_map['Git'] + symbols_map['Git'] + colors_map['Reset'] + ' '
        )

    for item in brackets:
        symbol, text = item.split(';')

        result += '[' + colors_map[symbol] + symbols_map[symbol]
        if symbol != 'Status':
            result += ' '
        result += text + colors_map['Reset'] + '] '

    for item in after:
        result += (
            colors_map[item] + symbols_map[item] + colors_map['Reset'] + ' '
        )

    # remove last empty space, new line might be in there
    result = result.strip()

    # get the lenght of written so far
    raw = result
    for item in colors_map:
        raw = raw.replace(colors_map[item], '', -1)

    width -= len(raw) + int('🌙' in raw) + 1  # new line at the end

    clocks_str = resolve_clocks(duration, width)
    if clocks_str:
        result += ' '
        width -= 1

    width -= len(clocks_str) - int('🕓' not in clocks_str)
    result += ' ' * width + clocks_str

    if width > 0:
        result += '\n'

    if no_error:
        result += colors_map['No_error']
    else:
        result += colors_map['Error']

    result += '❯ ' + colors_map['Reset']

    return result


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
    'Duration': '',
    'Error': '✘'
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
    'Reset': "\x1b[0m",
    'No_error': "\x1b[32m",
    'Error': "\x1b[31m"
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
    'Reset': "\x1b[0m",
    'No_error': "\x1b[92m",
    'Error': "\x1b[91m"
}

colors_map = dark_colors if darkdetect.isDark() else light_colors

threading.Thread(
    target=darkdetect.listener, args=(darkdetect_callback,), daemon=True
).start()
