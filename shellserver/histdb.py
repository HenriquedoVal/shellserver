import os
from collections import OrderedDict


def main(queries: str, width: int, height: int) -> str:
    if not queries:
        return 'Pass queries as arguments.'

    file = os.path.join(
        os.environ['APPDATA'],
        'Microsoft/Windows',
        'PowerShell/PSReadLine/ConsoleHost_history.txt'
    )
    with open(file, 'r', encoding='utf-8') as history:
        content = history.read()

    content = content.splitlines()
    content = OrderedDict.fromkeys(content[-2::-1])
    height -= 4
    height = max(height, 5)
    res = ''

    counter = 0
    printed = 0
    flag = False
    for item in content:

        # Checks the point when we're not printing anymore
        if not flag and counter >= height:
            printed = counter
            flag = True

        for query in queries.split():
            if query in item:

                # Check if isn't the first loop
                if counter and not flag:
                    res += '\n'

                counter += 1
                if len(item) > width:
                    counter += 1

                if not flag:
                    res += item.replace(query, f'\x1b[32m{query}\x1b[0m', -1)
                break

    if flag:
        res += ' ' * 10 + f'\x1b[33m[and {counter - printed} more]\x1b[0m'

    return res
