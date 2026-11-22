# -*- coding: utf-8 -*-
"""install.py — نصب‌کننده یک‌خطی مود Aseman Tower برای BombSquad 1.7+ (API 9).

این فایل قرار نیست دستی نصب شود؛ فقط ابزار نصب است:
  1) aseman_tower.py را از همین ریپو دانلود می‌کند
  2) داخل پوشه mods بازی (python_directory_user) ذخیره می‌کند
  3) برای همین نشست فوری فعالش می‌کند و پیام سبز می‌دهد

کاربر فقط این یک‌خط را در کنسول پایتون بازی می‌زند:
import importlib; exec(importlib.import_module('urllib.request').urlopen('https://raw.githubusercontent.com/amirali931493/Bomb-sq/main/install.py').read())
"""

import importlib.util
import os
import sys
import traceback
import urllib.request

import babase
import bauiv1 as bui

REPO_RAW = 'https://raw.githubusercontent.com/amirali931493/Bomb-sq/main'
FILES = ['aseman_tower.py']
PLUGIN_CLASS = 'AsemanTowerPlugin'


def _msg(text: str, color=(0.75, 1.0, 0.8)) -> None:
    """نمایش پیام داخل بازی با تحمل تفاوت‌های API."""
    try:
        babase.screenmessage(text, color=color)
    except Exception:
        try:
            import bascenev1 as bs
            bs.screenmessage(text, color=color)
        except Exception:
            pass


def _sound(name: str) -> None:
    """پخش صدای سیستم بازی (achievement / error)."""
    try:
        import _babase
        _babase.getsimplesound(name).play()
    except Exception:
        pass


def _activate_now(path: str) -> None:
    """فعال‌سازی فوری برای همین نشست: import پلاگین + اجرای on_app_running.

    مود خودش با فلگ‌های _aseman_* ضد نصب دوباره است، پس اجرای تکراری بی‌خطر است.
    """
    try:
        mod_name = os.path.splitext(os.path.basename(path))[0]
        spec = importlib.util.spec_from_file_location(mod_name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)
        cls = getattr(mod, PLUGIN_CLASS, None)
        if cls is not None:
            inst = cls()
            if hasattr(inst, 'on_app_running'):
                inst.on_app_running()
    except Exception:
        print(traceback.format_exc())


def _install() -> None:
    dst = bui.app.env.python_directory_user
    print('Mods folder:', dst)
    for name in FILES:
        url = REPO_RAW + '/' + name
        print('Downloading:', url)
        data = urllib.request.urlopen(url, timeout=30).read()
        path = os.path.join(dst, name)
        with open(path, 'wb') as f:
            f.write(data)
        print('Saved:', path)
        _activate_now(path)
    _msg('Aseman Tower Installed! (Settings > Advanced > User Plugins)',
         color=(0.0, 1.0, 0.0))


try:
    _install()
    _sound('achievement')
except Exception:
    print(traceback.format_exc())
    _msg('Install Error! Internet ra check kon va dobare talash kon.',
         color=(1.0, 0.0, 0.0))
    _sound('error')
