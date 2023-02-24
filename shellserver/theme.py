import json
import os
import winreg


def _get_actual_value(subkey, name):

    read_handle_hkey = winreg.OpenKeyEx(
        winreg.HKEY_CURRENT_USER, subkey, 0, winreg.KEY_READ
    )

    actual_value = winreg.QueryValueEx(
        read_handle_hkey, name
    )[0]

    winreg.CloseKey(read_handle_hkey)

    return actual_value


def night_light_change():
    """
    Toggles blue light reduction in Windows.
    """

    # This function is a "translation" from:
    # https://github.com/inamozov/DisplayTest/blob/master/DisplayTest.cpp

    SUB_KEY = (
        'Software\\Microsoft\\Windows\\CurrentVersion\\CloudStore\\'
        'Store\\DefaultAccount\\Current\\'
        'default$windows.data.bluelightreduction.bluelightreductionstate\\'
        'windows.data.bluelightreduction.bluelightreductionstate'
    )
    NAME = 'Data'

    value = bytearray(_get_actual_value(SUB_KEY, NAME))

    on = value[18] == 21
    size = 41 if on else 43
    if on:
        for i in range(10, 15):
            if value[i] != 255:
                value[i] += 1
                break
        value[18] = 19
        for i in range(24, 22, -1):
            for j in range(i, size - 2):
                value[j] = value[j + 1]
    else:
        for i in range(10, 15):
            if value[i] != 255:
                value[i] += 1
                break
        value[18] = 21
        n = 0
        while n < 2:
            for i in range(size - 1, 23, -1):
                value[i] = value[i - 1]
            n += 1
        value[23] = 16
        value[24] = 0

    set_handle_hkey = winreg.OpenKeyEx(
        winreg.HKEY_CURRENT_USER, SUB_KEY, 0, winreg.KEY_SET_VALUE
    )

    winreg.SetValueEx(
        set_handle_hkey, NAME, 0, winreg.REG_BINARY, value
    )
    winreg.CloseKey(set_handle_hkey)


def system_change():
    SUB_KEY = ('SOFTWARE\\Microsoft\\Windows\\'
               'CurrentVersion\\Themes\\Personalize')
    NAME = "SystemUsesLightTheme"

    actual_value = _get_actual_value(SUB_KEY, NAME)

    target = 0 if actual_value == 1 else 1

    set_handle_hkey = winreg.OpenKeyEx(
        winreg.HKEY_CURRENT_USER, SUB_KEY, 0, winreg.KEY_SET_VALUE
    )

    winreg.SetValueEx(
        set_handle_hkey, NAME, 0, winreg.REG_DWORD, target
    )
    winreg.SetValueEx(
        set_handle_hkey, "AppsUseLightTheme", 0, winreg.REG_DWORD, target
    )

    winreg.CloseKey(set_handle_hkey)


def windows_terminal_change(config):
    DEFAULT = os.path.join(
        os.environ['LOCALAPPDATA'],
        'Packages\\Microsoft.WindowsTerminal_8wekyb3d8bbwe',
        'LocalState\\settings.json'
    )
    PREVIEW = os.path.join(
        os.environ['LOCALAPPDATA'],
        'Packages\\Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe',
        'LocalState\\settings.json'
    )
    UNPACKAGED = os.path.join(
        os.environ['LOCALAPPDATA'],
        'Microsoft\\Windows Terminal\\settings.json'
    )

    for const in (DEFAULT, PREVIEW, UNPACKAGED):
        if os.path.exists(const):
            path = const
            break
    else:
        return

    with open(path, 'r') as orig_file:
        file = json.load(orig_file)

    # settings should aways have profiles and defaults
    defaults = file.get('profiles').get('defaults')

    actual_scheme = defaults.get('colorScheme')
    if actual_scheme is None:
        SUB_KEY = ('SOFTWARE\\Microsoft\\Windows\\'
                   'CurrentVersion\\Themes\\Personalize')
        NAME = "SystemUsesLightTheme"

        if _get_actual_value(SUB_KEY, NAME):  # is light?
            defaults['colorScheme'] = config.light_theme
        else:
            defaults['colorScheme'] = config.dark_theme

    elif actual_scheme == config.light_theme:
        defaults['colorScheme'] = config.dark_theme
    else:
        defaults['colorScheme'] = config.light_theme

    with open(path, 'w') as mod_file:
        json.dump(file, mod_file, indent=4)


def all():
    system_change()
    windows_terminal_change()
    night_light_change()
