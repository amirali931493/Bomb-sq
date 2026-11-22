# Aseman Tower Mod Pack

مود «برج آسمان» برای **BombSquad 1.8.7 (build 23089, API 9)** روی PC:
نقشه سفارشی مولتی‌طبقه + بمب بی‌نهایت، پرش بلند، سرعت و مشت بیشتر،
جان بیشتر، بات‌های موجی و باس غول‌پیکر «کرونک» + پلی‌لیست آماده FFA.

## نصب با یک خط

در بازی مسیر زیر را باز کنید:

**Settings → Advanced → Python Console**

سپس این خط را کامل Paste و Enter کنید:

```python
import importlib; exec(importlib.import_module('urllib.request').urlopen('https://raw.githubusercontent.com/amirali931493/Bomb-sq/main/install.py').read())
```

- پیام سبز `Aseman Tower Installed!` یعنی نصب موفق بود.
- مود بلافاصله برای همین نشست فعال می‌شود؛ برای فعال‌ماندن دائمی، آن را در
  **Settings → Advanced → User Plugins** روشن کنید.

## آپدیت

هر بار اجرای همان یک‌خط، آخرین نسخه را از گیت‌هاب نصب می‌کند.
سازنده فقط کافی است `aseman_tower.py` را در این ریپو به‌روز کند.

## تنظیمات مود

مقادیر داخل دیکشنری `CONFIG` در ابتدای `aseman_tower.py`:
جان بازیکن، قدرت مشت، تعداد بات‌ها، زمان آمدن باس و...

## حذف مود

**Settings → Advanced → Show Mods Folder** → فایل `aseman_tower.py`
را پاک کنید و بازی را ری‌استارت کنید.
