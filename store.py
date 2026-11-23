# -*- coding: utf-8 -*-
"""store.py — One-line bootstrap that opens the Aseman mod store in the console.

Console line (paste as ONE line in Settings > Advanced > Python Console):
import importlib; exec(importlib.import_module('urllib.request').urlopen('https://raw.githubusercontent.com/amirali931493/Bomb-sq/main/store.py').read())

It downloads core.py (the installer engine), injects the commands
(list_mods / install / install_all / uninstall) and prints the mod menu.
"""

import importlib as _importlib

_urllib = _importlib.import_module('urllib.request')
_BASE = 'https://raw.githubusercontent.com/amirali931493/Bomb-sq/main/'

exec(_urllib.urlopen(_BASE + 'core.py').read())

try:
    list_mods()  # noqa: F821  (provided by core.py)
except NameError:
    print('Could not load the mod store. Check your internet connection and try again.')
