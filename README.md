# Aseman Mod Pack

مخزن مودهای **BombSquad 1.8.7 (build 23089, API 9)** روی PC.
هر مود با یک خط کد از همین مخزن نصب می‌شود. الان شامل:

| # | مود | توضیح |
|---|-----|-------|
| 1 | **Aseman Tower** (`aseman_tower`) | نقشه سفارشی مولتی‌طبقه + بمب بی‌نهایت، پرش بلند، سرعت و مشت بیشتر، جان بیشتر، بات‌های موجی و باس «کرونک» + پلی‌لیست FFA |

## روش ۱ — فروشگاه مود (پیشنهادی)

در بازی مسیر زیر را باز کنید:

**Settings → Advanced → Python Console**

سپس این خط را کامل Paste و Enter کنید تا لیست همه مودها را ببینید:

```python
import importlib; exec(importlib.import_module('urllib.request').urlopen('https://raw.githubusercontent.com/amirali931493/Bomb-sq/main/store.py').read())
```

بعد در همان کنسول یکی از این دستورها را تایپ کنید:

```python
install(1)                  # نصب با شماره از لیست
install('aseman_tower')     # نصب با اسم
install_all()               # نصب همه مودها
list_mods()                 # دیدن دوباره لیست
uninstall('aseman_tower')   # حذف یک مود
```

## روش ۲ — نصب مستقیم Aseman Tower (خط قدیمی، همچنان کار می‌کند)

```python
import importlib; exec(importlib.import_module('urllib.request').urlopen('https://raw.githubusercontent.com/amirali931493/Bomb-sq/main/install.py').read())
```

## روش ۳ — نصب مستقیم هر مود دیگر (الگو)

در خط زیر فقط اسم مود را عوض کنید:

```python
import importlib; exec(importlib.import_module('urllib.request').urlopen('https://raw.githubusercontent.com/amirali931493/Bomb-sq/main/core.py').read()); install('NAME_MOD')
```

- پیام سبز `... Installed!` یعنی نصب موفق بود.
- مود بلافاصله برای همین نشست فعال می‌شود؛ برای فعال‌ماندن دائمی، آن را در
  **Settings → Advanced → User Plugins** روشن کنید.

## آپدیت

هر بار اجرای همان یک‌خط، آخرین نسخه را از گیت‌هاب نصب می‌کند.
سازنده فقط کافی است فایل مود را در این ریپو به‌روز کند.

## اضافه‌کردن مود جدید به مخزن (برای سازنده)

1. فایل مود را به این ریپو اضافه کنید (مثلاً `my_mod.py`).
2. در `mods.json` یک رکورد به لیست `mods` اضافه کنید با فیلدهای:
   `name`، `file`، `title`، `version`، `plugin_class` (کلاس پلاگین داخل فایل) و `description`.
3. تمام — مود جدید در `list_mods()` ظاهر می‌شود و با `install('my_mod')` یا
   الگوی روش ۳ نصب می‌شود.

## تنظیمات مود Aseman Tower

مقادیر داخل دیکشنری `CONFIG` در ابتدای `aseman_tower.py`:
جان بازیکن، قدرت مشت، تعداد بات‌ها، زمان آمدن باس و...

## حذف مود

در کنسول: `uninstall('aseman_tower')` یا مسیر
**Settings → Advanced → Show Mods Folder** → فایل مود را پاک کنید و بازی را ری‌استارت کنید.
