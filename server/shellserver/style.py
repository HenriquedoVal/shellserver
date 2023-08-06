import os
from datetime import datetime

from .__init__ import SEP, USER_HOME


symbols_map = {
    'Git': '',
    'Branch': '',
    'Python': '',
    'Lua': '🌙',
    'Node': '',
    'C': '',
    'Cpp': '',
    'Pwsh': '',  # maybe  
    'Java': '',
    'Rust': '',
    'Csharp': '',
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
    'Java': '\x1b[31m',
    'Rust': '\x1b[31m',
    'Csharp': "\x1b[94m",
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
    'Java': '\x1b[91m',
    'Rust': '\x1b[91m',
    'Csharp': "\x1b[94m",
    'Status': "\x1b[91m",
    'Reset': "\x1b[0m",
    'No_error': "\x1b[92m",
    'Error': "\x1b[91m"
}

colors_map = dark_colors


def toggle_prompt():
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
        elif val and ((unit == 's' and (val > 2 or res)) or unit != 's'):
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


def get_ephem_brackets(brackets, after, apply_esc=False):
    result = ''
    for item in brackets:
        symbol, text = item.split(';')

        result += '['
        if apply_esc:
            result += colors_map[symbol]
        result += symbols_map[symbol]

        if symbol != 'Status':
            result += ' '
        result += text

        if apply_esc:
            result += colors_map['Reset']
        result += '] '

    for item in after:
        if apply_esc:
            result += colors_map[item]

        result += symbols_map[item] + ' '

        if apply_esc:
            result += colors_map['Reset']

    return result


def get_brackets_no_version(brackets, after, apply_esc=False):
    result = ''
    for item in brackets:
        symbol, text = item.split(';')

        if symbol == 'Status':
            if apply_esc:
                result += f'[{colors_map[symbol]}{text}{colors_map["Reset"]}] '
            else:
                result += '[' + text + '] '
            continue

        if apply_esc:
            result += colors_map[symbol]

        # wrapped block
        if symbol == 'Branch':
            result += text + ' '
        else:
            result += symbols_map[symbol] + ' '
        #

        if apply_esc:
            result += colors_map['Reset']

    for item in after:
        result += symbols_map[item] + ' '

    return result


def get_ephem_cwd_and_link(cwd, link, dir_depth: int, path_max_len: int):
    equal = cwd == link

    if cwd == '~':
        cwd = ' ' + cwd
    elif cwd.startswith(os.environ['HOMEDRIVE']):
        cwd = ' ' + cwd
    else:
        cwd = ' ' + cwd

    if dir_depth:
        cwd = hide_first_dirs(cwd, dir_depth)
    if path_max_len:
        cwd = reduce_big_path_names(cwd, path_max_len)
    cwd += ' '

    if not equal:
        if dir_depth:
            link = hide_first_dirs(link, dir_depth)
        if path_max_len:
            link = reduce_big_path_names(link, path_max_len)
        link += ' '
    else:
        link = ''

    return cwd, link


def apply_escape_codes(
    cwd: str,
    link: str,
    result_git: str,
    brackets: list,
    after: list,
    no_versions: bool,
    clock: str,
    spaces: int,
    no_error: int,  # | bool,
) -> str:

    result = colors_map['Cwd'] + cwd + colors_map['Reset']
    if link:
        result += (
            colors_map['Link']
            + ' '
            + colors_map['Cwd']
            + link
            + colors_map['Reset']
        )

    if result_git:
        result += (
            colors_map['Git'] + result_git + colors_map['Reset']
        )

    if no_versions:
        result += get_brackets_no_version(
            brackets, after, apply_esc=True
        )
    else:
        result += get_ephem_brackets(brackets, after, apply_esc=True)

    if spaces >= 1:  # if there's room for new line
        result += ' ' * (spaces - 1) + clock + '\n'
    else:
        result += clock

    if no_error:
        result += colors_map['No_error']
    else:
        result += colors_map['Error']

    result += '❯ ' + colors_map['Reset']

    return result


def get_prompt(
    cwd: str,
    link: str,
    brackets: list,
    after: list,
    no_error: int,  # | bool,
    width: int,
    duration: float
) -> str:

    if USER_HOME in cwd:
        cwd = '~' + cwd.removeprefix(USER_HOME)
    if USER_HOME in link:
        link = '~' + link.removeprefix(USER_HOME)

    result_cwd, result_link = get_ephem_cwd_and_link(cwd, link, 0, 0)
    result_brackets = get_ephem_brackets(brackets, after)
    result_clocks = resolve_clocks(duration, width)
    result_git = (
        symbols_map['Git'] + ' '
        if any(i.startswith('Branch') for i in brackets)
        else ''
    )

    counter = 0
    no_versions = False
    prompt = (
        result_cwd + result_link + result_git + result_brackets + result_clocks
    )
    prompt_length = (
        len(prompt) + int('🌙' in prompt) + int('🕓' in prompt)
        + (2 if result_link else 0)
    )

    while prompt_length > width:

        if counter in range(4):
            result_cwd, result_link = get_ephem_cwd_and_link(
                cwd, link, 5 - counter, 0
            )

        elif counter == 4:
            result_brackets = get_brackets_no_version(brackets, after)
            no_versions = True

        elif counter == 5:
            result_clocks = resolve_clocks(duration, width - prompt_length)

        elif counter in range(6, 9):
            result_cwd, result_link = get_ephem_cwd_and_link(
                cwd, link, 3, 65 - counter * 5
            )

        elif counter == 9:
            break

        counter += 1
        prompt = (
            result_cwd + result_link + result_git
            + result_brackets + result_clocks
        )
        prompt_length = (
            len(prompt) + int('🌙' in prompt) + int('🕓' in prompt)
            + (2 if result_link else 0)
        )

    spaces = width - prompt_length

    result = apply_escape_codes(
        result_cwd,
        result_link,
        result_git,
        brackets,
        after,
        no_versions,
        result_clocks,
        spaces,
        no_error
    )

    return result
