# Aseman Mod Pack

مخزن مودهای **BombSquad 1.8.7 (build 23089, API 9)** روی PC.
هر مود با یک خط کد از همین مخزن نصب می‌شود. الان شامل:

| # | مود | توضیح |
|---|-----|-------|
| 1 | **Aseman Tower** (`aseman_tower`) | نقشه سفارشی مولتی‌طبقه + بمب بی‌نهایت، پرش بلند، سرعت و مشت بیشتر، جان بیشتر، بات‌های موجی و باس «کرونک» + پلی‌لیست FFA |
| 2 | **FlyCheats** (`flycheats`) | پک چیت با دستورهای چت: پرواز، سرعت، نامیرایی، بمب بی‌نهایت، انواع بمب، قدرت انفجار/مشت، سپر، تله‌پورت، فریز، رنگین‌کمان و... |

## روش ۱ — فروشگاه مود (پیشنهادی)

در بازی مسیر زیر را باز کنید:

**Settings → Advanced → Python Console**

سپس این خط را کامل Paste و Enter کنید تا لیست همه مودها را ببینید:

```python
import importlib; exec(importlib.import_module('urllib.request').urlopen('https://raw.githubusercontent.com/amirali931493/Bomb-sq/main/store.py').read())
```

بعد در همان کنسول یکی از این دستورها را تایپ کنید:

```python
install(1)                  # نصب Aseman Tower با شماره
install(2)                  # نصب FlyCheats با شماره
install('flycheats')        # نصب با اسم
install_all()               # نصب همه مودها
list_mods()                 # دیدن دوباره لیست
uninstall('flycheats')      # حذف یک مود
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

## FlyCheats — راهنمای سریع

بعد از نصب، در چت لابی (Party Chat) کلمه‌ها را تایپ کنید؛ هر بازیکن
قدرت‌های خودش را جداگانه می‌گیرد. لیست کامل: `codes`

| دستور | کار |
|-------|-----|
| `fly [0.5-5]` | پرواز — با `fly off` فرود بیا |
| `speed [0.5-5]` | افزایش سرعت |
| `god` | نامیرایی |
| `heal` | درمان کامل |
| `inf` | بمب بی‌نهایت |
| `bombs <1-30>` | حداکثر تعداد بمب |
| `btype ice/impact/sticky/normal` | نوع بمب |
| `power <0.5-10>` | قدرت انفجار |
| `punch <1-10>` | قدرت مشت |
| `ptime <sec>` | مدت پاورآپ‌ها (0 = تا آخر) |
| `pu triple/ice/impact/sticky/mine/punch/shield/health/curse [sec]` | گرفتن پاورآپ |
| `mega` | کمبو: بمب سه‌تایی + سپر + مشت قوی |
| `spawnpu <type>` | ساختن جعبه پاورآپ |
| `tp <#>` / `freeze <#>` / `unfreeze <#>` / `boom <#>` | اثر روی بازیکن شماره <#> |
| `players` | لیست بازیکنان با شماره |
| `color <name/rainbow/off>` | رنگ بدن / رنگین‌کمان |
| `kill` | ریسپاون |
| `codes` / `off` | راهنما / خاموش‌کردن همه چیت‌ها |

دستورها وقتی کار می‌کنند که بازی از PC شما هاست شده باشد (در بازی تک‌نفره
شما همیشه هاست هستید).

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

در کنسول: `uninstall('aseman_tower')` یا `uninstall('flycheats')` یا مسیر
**Settings → Advanced → Show Mods Folder** → فایل مود را پاک کنید و بازی را ری‌استارت کنید.
