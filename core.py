# -*- coding: utf-8 -*-
"""core.py — Installer engine for the Aseman mod repository (BombSquad API 9).

Executed from the in-game Python console through a one-line bootstrap.
For every mod listed in mods.json it provides:

    list_mods()               -> show the mod menu
    install(name_or_index)    -> download + save + activate one mod
    install_all()             -> install every mod in the manifest
    uninstall(name_or_index)  -> delete a mod file from the mods folder

Universal one-line bootstrap (shows the menu):
import importlib; exec(importlib.import_module('urllib.request').urlopen('https://raw.githubusercontent.com/amirali931493/Bomb-sq/main/store.py').read())

Direct one-liner for any single mod (replace NAME_MOD):
import importlib; exec(importlib.import_module('urllib.request').urlopen('https://raw.githubusercontent.com/amirali931493/Bomb-sq/main/core.py').read()); install('NAME_MOD')
"""

import builtins as _builtins
import importlib.util as _ilu
import json as _json
import os as _os
import sys as _sys
import traceback as _tb

import babase as _babase
import bauiv1 as _bui

REPO_RAW = 'https://raw.githubusercontent.com/amirali931493/Bomb-sq/main'
MANIFEST = 'mods.json'


def _fetch(path: str, timeout: int = 30) -> bytes:
    import urllib.request
    return urllib.request.urlopen(REPO_RAW + '/' + path, timeout=timeout).read()


def _msg(text: str, color=(0.75, 1.0, 0.8)) -> None:
    """Show an in-game message, tolerating API differences."""
    try:
        _babase.screenmessage(text, color=color)
    except Exception:
        try:
            import bascenev1
            bascenev1.screenmessage(text, color=color)
        except Exception:
            pass


def _sound(name: str) -> None:
    """Play a game system sound (achievement / error)."""
    try:
        import _babase
        _babase.getsimplesound(name).play()
    except Exception:
        pass


def _manifest() -> dict:
    return _json.loads(_fetch(MANIFEST).decode('utf-8'))


def _find(mod):
    """Resolve a manifest entry from an index (int) or name (str)."""
    mods = _manifest().get('mods', [])
    if isinstance(mod, int):
        if not 1 <= mod <= len(mods):
            print('ERROR: index out of range (1-' + str(len(mods)) + '). Run list_mods() first.')
            return None
        return mods[mod - 1]
    entry = next(
        (m for m in mods if str(m.get('name', '')).lower() == str(mod).lower()),
        None,
    )
    if entry is None:
        print('ERROR: mod "' + str(mod) + '" not found. Run list_mods() to see the menu.')
    return entry


def list_mods():
    """Print every mod available in this repository."""
    mods = _manifest().get('mods', [])
    print('=== Aseman Mod Repository | ' + str(len(mods)) + ' mods available ===')
    for i, m in enumerate(mods, 1):
        star = '*' if m.get('default') else ' '
        print(' {} {:>2}. {:<18} v{:<5} {}'.format(
            star, i, m.get('name', '?'), str(m.get('version', '?')), m.get('title', '')))
        if m.get('description'):
            print('       ' + m['description'])
    print()
    print("  install(1)               install by index")
    print("  install('aseman_tower')  install by name")
    print('  install_all()            install everything')
    print("  uninstall('aseman_tower') remove an installed mod")
    return mods


def _activate(path: str, plugin_class: str) -> None:
    """Activate a freshly downloaded plugin for this session.

    Imports the module from file and runs on_app_running if the plugin
    exposes it. Mods with their own re-entry guards stay safe.
    """
    try:
        mod_name = _os.path.splitext(_os.path.basename(path))[0]
        spec = _ilu.spec_from_file_location(mod_name, path)
        mod = _ilu.module_from_spec(spec)
        _sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)
        cls = getattr(mod, plugin_class, None) if plugin_class else None
        if cls is not None:
            inst = cls()
            if hasattr(inst, 'on_app_running'):
                inst.on_app_running()
    except Exception:
        print(_tb.format_exc())


def install(mod):
    """Install one mod from the repository, by index (int) or name (str)."""
    try:
        entry = _find(mod)
        if entry is None:
            return None
        name = entry.get('name', '?')
        fname = entry.get('file', name + '.py')
        dst = _bui.app.env.python_directory_user
        print('Downloading:', REPO_RAW + '/' + fname)
        data = _fetch(fname)
        path = _os.path.join(dst, fname)
        with open(path, 'wb') as f:
            f.write(data)
        print('Saved:', path)
        _activate(path, entry.get('plugin_class', ''))
        _msg(entry.get('title', name) + ' Installed! (Settings > Advanced > User Plugins)',
             color=(0.0, 1.0, 0.0))
        _sound('achievement')
        return entry
    except Exception:
        print(_tb.format_exc())
        _msg('Install Error! Check internet and try again.', color=(1.0, 0.0, 0.0))
        _sound('error')
        return None


def install_all() -> None:
    """Install every mod listed in the repository manifest."""
    try:
        mods = _manifest().get('mods', [])
        print('Installing all ' + str(len(mods)) + ' mods ...')
        for i, m in enumerate(mods, 1):
            print('--- [' + str(i) + '/' + str(len(mods)) + '] ' + m.get('name', '?'))
            install(m.get('name'))
    except Exception:
        print(_tb.format_exc())


def uninstall(mod) -> bool:
    """Remove a mod file from the user mods folder (restart to fully unload)."""
    try:
        entry = _find(mod)
        if entry is None:
            return False
        name = entry.get('name', '?')
        fname = entry.get('file', name + '.py')
        dst = _bui.app.env.python_directory_user
        path = _os.path.join(dst, fname)
        if _os.path.exists(path):
            _os.remove(path)
            print('Deleted:', path)
            _msg(entry.get('title', name) + ' uninstalled. Restart the game to fully unload.',
                 color=(1.0, 0.7, 0.3))
        else:
            print('Not installed (file not found):', path)
        return True
    except Exception:
        print(_tb.format_exc())
        return False


# Make the tools callable from later console lines regardless of which
# namespace the console uses for evaluation.
for _fname in ('list_mods', 'install', 'install_all', 'uninstall'):
    setattr(_builtins, _fname, globals()[_fname])
