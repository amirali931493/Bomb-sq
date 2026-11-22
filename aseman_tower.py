# -*- coding: utf-8 -*-
"""Aseman Tower Mod Pack for BombSquad 1.8.7 (build 23089, API 9).

مود نقشه سفارشی «برج آسمان» به‌همراه فیچرهای گیم‌پلی:
  - نقشه سفارشی مولتی‌طبقه بر پایه Tower D با حال‌وهوای آسمانی
  - بمب بی‌نهایت برای بازیکن‌ها
  - پرش بلند (پرش زنجیره‌ای در هوا)
  - سرعت دویدن و قدرت مشت بیشتر
  - جان بیشتر برای بازیکن‌ها (عددش در CONFIG قابل تغییر است)
  - تولید خودکار بات‌های دشمن + باس غول‌پیکر «کرونک»

نصب: این فایل را داخل پوشه mods بازی کپی کنید و بازی را ری‌استارت کنید.
مسیر پوشه از داخل بازی: Settings -> Advanced -> Show Mods Folder
سازگار با BombSquad 1.8.7 build 23089 (API 9) روی PC.

ویژگی پلی‌لیست: نسخه رایگان بازی اجازه ساختن/ویرایش پلی‌لیست نمی‌دهد
(فقط Pro)، ولی اجرای پلی‌لیست‌های موجود آزاد است. بنابراین این مود یک
پلی‌لیست آماده «Aseman Tower FFA» را مستقیماً داخل کانفیگ بازی ثبت
می‌کند تا از مسیر Play > Free-for-All Games قابل اجرا باشد.
"""
# ba_meta require api 9

from __future__ import annotations

import copy
import random
import weakref
from typing import Any

import babase
import bascenev1 as bs
from bascenev1._messages import DieMessage
from bascenev1lib.actor.playerspaz import PlayerSpaz
from bascenev1lib.actor.powerupbox import PowerupBoxFactory
from bascenev1lib.actor.spaz import Spaz
from bascenev1lib.actor.spazbot import (
    BomberBot,
    BomberBotProShielded,
    BrawlerBot,
    ChargerBot,
    SpazBotSet,
    StickyBot,
)
from bascenev1lib.gameutils import SharedObjects
from bascenev1lib.mapdata import tower_d as _tower_d

# ==========================================================================
#  تنظیمات مود — هر مقداری را که خواستی عوض کن
# ==========================================================================
CONFIG: dict[str, Any] = {
    # زبان پیام‌های داخل بازی:
    #   'fa'        = فارسی با حروف لاتین (Finglish)؛ روی فونت بازی همیشه
    #                 درست نمایش داده می‌شود (پیشنهادی)
    #   'fa_script' = فارسی با حروف فارسی؛ اگر فونت بازی پشتیبانی نکند
    #                 ممکن است مربع‌مربع یا جدا-جدا دیده شود
    #   'en'        = انگلیسی
    'lang': 'fa',
    # ---------------- گیم‌پلی ----------------
    'infinite_bombs': True,   # بمب بی‌نهایت (فقط بازیکن‌ها؛ بات‌ها عادی می‌مانند)
    'infinite_shild': True,   # بمب بی‌نهایت (فقط بازیکن‌ها؛ بات‌ها عادی می‌مانند)
    'bomb_limit': 10,          # حداکثر بمبی که همزمان حمل می‌کنی
    'super_jump': True,       # پرش بلند؛ بعد از پرش، چند ضربه پرش اضافی در هوا
    'extra_jumps': 1,         # تعداد ضربات پرش اضافی (۲ یا ۳ پیشنهاد می‌شود)
    'speed_boost': True,      # دویدن سریع‌تر مثل حالت هاکی
    'punch_power': 5.0,       # ضریب قدرت مشت (1.0 = عادی بازی)
    'player_health': 5000,    # جان بازیکن (1000 = عادی بازی؛ مثلاً 5000
                              # بگذاری ۵ برابر می‌شود)
    # ---------------- پلی‌لیست آماده ----------------
    'add_playlist': True,     # ساخت خودکار پلی‌لیست آماده (نسخه رایگان
                              # بازی اجازه ساختن دستی پلی‌لیست نمی‌دهد)
    'playlist_name': 'Aseman Tower FFA',
    # ---------------- بات‌ها و باس ----------------
    'spawn_bots': True,       # تولید خودکار بات دشمن روی نقشه
    'max_bots': 5,            # حداکثر بات زنده به‌طور همزمان
    'bot_interval': 5,     # هر چند ثانیه جای بات مرده، بات تازه بیاید
    'spawn_boss': True,       # آمدن باس غول‌پیکر وسط بازی
    'boss_delay': 40.0,       # چند ثانیه بعد از شروع، باس بیاید
    'boss_hitpoints': 3000,   # جان باس (بازیکن معمولی 1000 جان دارد)
}

# ==========================================================================
#  پیام‌های داخل بازی (سه زبان: فینگلیش، فارسی، انگلیسی)
# ==========================================================================
_MESSAGES = {
    'fa': {
        'welcome': ('Aseman Tower faal shod! | Bomb: Bi-Nahayat | '
                    'Super Jump | Speed+ | Boss: ~40 sanie bad!'),
        'boss': 'BOSS omad: KRONK-e ghoolpeykar! Mohtaat bash!',
        'map_hint': ('Aseman Tower: ba Super Jump mishe gooshe-haye tower '
                     'ra girft!'),
        'playlist': ('Playlist "Aseman Tower FFA" sakhte shod! | '
                     'Play > Free-for-All Games'),
    },
    'fa_script': {
        'welcome': ('برج آسمان فعال شد! | بمب بی‌نهایت | پرش بلند | '
                    'سرعت بیشتر | باس بعد از ~۴۰ ثانیه!'),
        'boss': 'باس اومد: کرونک غول‌پیکر! مواظب باش!',
        'map_hint': 'برج آسمان: با پرش بلند می‌شود طبقه‌های برج را گرفت!',
        'playlist': 'پلی‌لیست «برج آسمان» ساخته شد! از Play > Free-for-All '
                    'Games اجرا کنید',
    },
    'en': {
        'welcome': ('Aseman Tower active! | Infinite Bombs | Super Jump | '
                    'Speed+ | Boss in ~40s!'),
        'boss': 'BOSS INCOMING: Giant KRONK! Watch out!',
        'map_hint': 'Aseman Tower: use Super Jump to grab the tower tops!',
        'playlist': ('Playlist "Aseman Tower FFA" created! | '
                     'Play > Free-for-All Games'),
    },
}


def _msg(key: str) -> str:
    """Return the configured in-game message for the given key."""
    lang = str(CONFIG.get('lang', 'fa'))
    table = _MESSAGES.get(lang) or _MESSAGES['fa']
    return table[key]


def _screenmessage(text: str, color: tuple[float, float, float] = (
        0.75, 1.0, 0.8)) -> None:
    """Show a message in-game, tolerating API differences."""
    try:
        babase.screenmessage(text, color=color)
    except Exception:
        try:
            bs.screenmessage(text, color=color)
        except Exception:
            pass


def _is_player_spaz(spaz: Any) -> bool:
    """True for real player spazes (bots have source_player = None)."""
    try:
        return getattr(spaz, 'source_player', None) is not None
    except Exception:
        return False


def _get_asset(getter: Any, *names: str) -> Any:
    """Try several asset names and return the first one that loads."""
    for name in names:
        try:
            return getter(name)
        except Exception:
            continue
    return None


# ==========================================================================
#  دیتای نقشه — بر پایه دیتای رسمی Tower D با نقاط اضافه برای ۸ نفر
# ==========================================================================
_SPAWN_ROT = (1.66339533, 1.0, 0.8737798622)


class AsemanTowerData:
    """Points/boxes for the Aseman Tower map.

    همه نقاط اصلی Tower D حفظ شده‌اند و فقط چند نقطه spawn و پاورآپ
    اضافه شده تا بازی ۸ نفره آزاد (FFA) هم بدون مشکل کار کند.
    """

    points = dict(_tower_d.points)
    boxes = dict(_tower_d.boxes)

    # --- اسپاون‌های اضافه برای بازی آزاد ۸ نفره ---
    # همگی از نقاط معتبر خود Tower D کپی شده‌اند تا مطمئن باشیم
    # روی سطح برج قرار می‌گیرند.
    points['ffa_spawn2'] = _tower_d.points['bot_spawn_bottom_left']
    points['ffa_spawn3'] = _tower_d.points['bot_spawn_bottom_right']
    points['ffa_spawn4'] = _tower_d.points['flag1'] + _SPAWN_ROT
    points['ffa_spawn5'] = _tower_d.points['flag2'] + _SPAWN_ROT
    points['ffa_spawn6'] = _tower_d.points['powerup_spawn1'] + _SPAWN_ROT
    points['ffa_spawn7'] = _tower_d.points['powerup_spawn4'] + _SPAWN_ROT
    points['ffa_spawn8'] = (0.0, 2.8, 4.9) + _SPAWN_ROT

    # --- دو نقطه پاورآپ اضافه کنار پرچم‌ها ---
    points['powerup_spawn5'] = _tower_d.points['flag1']
    points['powerup_spawn6'] = _tower_d.points['flag2']


# ==========================================================================
#  سیستم بات‌ها
# ==========================================================================
_LIVING_BOTS: 'weakref.WeakSet[Any]' = weakref.WeakSet()
_WAVE_BOT_TYPES: list[type] = []


def _make_wave_bot(base: type) -> type:
    """Create a bot subclass that registers itself in _LIVING_BOTS."""

    class WaveBot(base):  # type: ignore[valid-type, misc]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            _LIVING_BOTS.add(self)

        def handlemessage(self, msg: Any) -> Any:
            if isinstance(msg, DieMessage):
                _LIVING_BOTS.discard(self)
            return super().handlemessage(msg)

    WaveBot.__name__ = 'Wave' + base.__name__
    return WaveBot


if not _WAVE_BOT_TYPES:
    _WAVE_BOT_TYPES = [
        _make_wave_bot(BomberBot),
        _make_wave_bot(BrawlerBot),
        _make_wave_bot(ChargerBot),
        _make_wave_bot(StickyBot),
    ]


class AsemanBossBot(BomberBotProShielded):
    """باس غول‌پیکر: کرونک با سپر و بمب‌های برخوردی و ۳۰۰۰ جان."""

    character = 'Kronk'
    color = (0.85, 0.25, 0.10)
    highlight = (1.0, 0.95, 0.30)
    default_shields = True
    default_bomb_type = 'impact'
    default_bomb_count = 3
    points_mult = 5

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        try:
            hp = float(CONFIG['boss_hitpoints'])
            self.hitpoints = hp
            self.hitpoints_max = hp
        except Exception:
            pass


# ==========================================================================
#  کلاس نقشه «برج آسمان»
# ==========================================================================
class AsemanTowerMap(bs.Map):
    """نقشه سفارشی مولتی‌طبقه با فضا و رنگ آسمانی + سیستم بات."""

    defs = AsemanTowerData()
    name = 'Aseman Tower'

    @classmethod
    def get_play_types(cls) -> list[str]:
        return ['melee', 'free_for_all', 'teams', 'keep_away',
                'king_of_the_hill']

    @classmethod
    def get_preview_texture_name(cls) -> str:
        # نام تأییدشده در نسخه 1.7 (همان که مود Abyss استفاده می‌کند)
        return 'alwaysLandPreview'

    @classmethod
    def get_preview_texture_spec(cls) -> Any:
        """Return the packaged preview texture (the api 9 hook)."""
        try:
            from bauiv1 import _classiccatalogassets as _uicat
            return _uicat.textures.always_land_preview
        except Exception:
            return None

    @classmethod
    def get_music_type(cls) -> bs.MusicType:
        return bs.MusicType.EPIC

    @classmethod
    def on_preload(cls) -> Any:
        return {
            # اجزای اصلی برج (از خود بازی) — نام‌های رسمی نسخه 1.7
            'mesh': bs.getmesh('towerDLevel'),
            'collision_mesh': bs.getcollisionmesh('towerDLevelCollide'),
            'tex': bs.gettexture('towerDLevelColor'),
            # اجزای اختیاری — اگر نبودند بی‌صدا رد می‌شوند.
            'mesh_bottom': _get_asset(bs.getmesh, 'towerDLevelBottom'),
            'bgmesh': _get_asset(bs.getmesh, 'thePadBG'),
            'bgtex': _get_asset(bs.gettexture, 'menuBG'),
            'player_wall': _get_asset(bs.getmesh, 'towerDPlayerWall'),
            'vr_fill_mesh': _get_asset(bs.getmesh, 'stepRightUpVRFillMound'),
            'vr_fill_tex': _get_asset(bs.gettexture, 'vrFillMound'),
        }

    def __init__(self) -> None:
        super().__init__()
        shared = SharedObjects.get()

        # بدنه اصلی برج: مش + مش برخورد + متریال footing (الگوی رسمی Tower D)
        self.node = bs.newnode(
            'terrain',
            delegate=self,
            attrs={
                'mesh': self.preloaddata['mesh'],
                'color_texture': self.preloaddata['tex'],
                'collision_mesh': self.preloaddata['collision_mesh'],
                'materials': [shared.footing_material],
            },
        )

        # بخش زیرین برج (اختیاری)
        if self.preloaddata.get('mesh_bottom') is not None:
            bs.newnode(
                'terrain',
                delegate=self,
                attrs={
                    'mesh': self.preloaddata['mesh_bottom'],
                    'lighting': False,
                    'color_texture': self.preloaddata['tex'],
                },
            )

        # پس‌زمینه
        if (self.preloaddata.get('bgmesh') is not None
                and self.preloaddata.get('bgtex') is not None):
            self.background = bs.newnode(
                'terrain',
                attrs={
                    'mesh': self.preloaddata['bgmesh'],
                    'lighting': False,
                    'background': True,
                    'color_texture': self.preloaddata['bgtex'],
                },
            )

        # دیوار غیرقابل‌عبور برای بازیکن (مثل Tower D اصلی)
        wall_mesh = self.preloaddata.get('player_wall')
        if wall_mesh is not None:
            wall_material = bs.Material()
            wall_material.add_actions(
                actions=('modify_part_collision', 'friction', 0.0))
            wall_material.add_actions(
                conditions=('they_dont_have_material',
                            shared.object_material),
                actions=('modify_part_collision', 'collide', False),
            )
            bs.newnode(
                'terrain',
                attrs={
                    'collision_mesh': wall_mesh,
                    'affect_bg_dynamics': False,
                    'materials': [wall_material],
                },
            )

        # حال‌وهوای آسمانی: رنگ‌های خنک و روشن
        gnode = bs.getactivity().globalsnode
        gnode.tint = (1.05, 1.16, 1.30)
        gnode.ambient_color = (1.15, 1.22, 1.34)
        gnode.vignette_outer = (0.62, 0.70, 0.84)
        gnode.vignette_inner = (0.93, 0.96, 1.0)

        # دو چراغ تزئینی بالای برج (نارنجی و آبی)
        try:
            bs.newnode('light',
                       attrs={
                           'position': (-8.0, 12.0, -2.0),
                           'color': (1.0, 0.55, 0.25),
                           'radius': 0.35,
                           'intensity': 0.8,
                       })
            bs.newnode('light',
                       attrs={
                           'position': (8.0, 12.0, -2.0),
                           'color': (0.35, 0.65, 1.0),
                           'radius': 0.35,
                           'intensity': 0.8,
                       })
        except Exception:
            pass

        # استارت سیستم بات‌ها و باس
        if CONFIG.get('spawn_bots'):
            bs.timer(3.0, bs.WeakCallPartial(self._start_bot_system))

    # --- تشخیص لبه نقشه (کپی منطق رسمی Tower D؛ دو جعبه لبه) ---
    def is_point_near_edge(self,
                           point: bs.Vec3,
                           running: bool = False) -> bool:
        boxes = self.defs.boxes
        box_position = boxes['edge_box'][0:3]
        box_scale = boxes['edge_box'][6:9]
        box_position2 = boxes['edge_box2'][0:3]
        box_scale2 = boxes['edge_box2'][6:9]
        xpos = (point.x - box_position[0]) / box_scale[0]
        zpos = (point.z - box_position[2]) / box_scale[2]
        xpos2 = (point.x - box_position2[0]) / box_scale2[0]
        zpos2 = (point.z - box_position2[2]) / box_scale2[2]
        return ((xpos < -0.5 or xpos > 0.5 or zpos < -0.5 or zpos > 0.5)
                and (xpos2 < -0.5 or xpos2 > 0.5
                     or zpos2 < -0.5 or zpos2 > 0.5))

    # ------------------------------------------------------------------
    #  سیستم بات‌ها
    # ------------------------------------------------------------------
    def _start_bot_system(self) -> None:
        """3 ثانیه بعد از لود نقشه اجرا می‌شود."""
        try:
            self._bots = SpazBotSet()
            self._bot_spawns = [
                self.defs.points['bot_spawn_bottom_left'][0:3],
                self.defs.points['bot_spawn_bottom_right'][0:3],
                self.defs.points['bot_spawn_start'][0:3],
            ]
            self._boss_spawned = False
            self._spawn_wave(int(CONFIG.get('max_bots', 4)))
            interval = float(CONFIG.get('bot_interval', 15.0))
            bs.timer(interval, bs.WeakCallPartial(self._bot_topup), repeat=True)
            if CONFIG.get('spawn_boss'):
                bs.timer(float(CONFIG.get('boss_delay', 40.0)),
                         bs.WeakCallPartial(self._spawn_boss))
        except Exception:
            pass

    def _spawn_wave(self, count: int) -> None:
        for i in range(max(0, count)):
            bottype = random.choice(_WAVE_BOT_TYPES)
            pos = self._bot_spawns[i % len(self._bot_spawns)]

            def _spawn(bottype=bottype, pos=pos) -> None:
                self._bots.spawn_bot(bottype, pos=pos, spawn_time=1.0)

            bs.timer(0.4 * i, _spawn)

    def _bot_topup(self) -> None:
        try:
            max_bots = int(CONFIG.get('max_bots', 4))
            missing = max_bots - len(_LIVING_BOTS)
            if missing > 0:
                self._spawn_wave(min(2, missing))
        except Exception:
            pass

    def _spawn_boss(self) -> None:
        try:
            if getattr(self, '_boss_spawned', False):
                return
            self._boss_spawned = True
            pos = self._bot_spawns[2]
            self._bots.spawn_bot(AsemanBossBot, pos=pos, spawn_time=2.0)
            bs.cameraflash()
            _screenmessage(_msg('boss'), color=(1.0, 0.5, 0.3))
        except Exception:
            pass


# ==========================================================================
#  پچ‌های گیم‌پلی (فقط یک‌بار اعمال می‌شوند)
# ==========================================================================

# ---- 1) بمب بی‌نهایت ----
if not getattr(PlayerSpaz, '_aseman_inf_bombs', False):
    _orig_drop_bomb = PlayerSpaz.drop_bomb

    def _aseman_drop_bomb(self: PlayerSpaz) -> Any:
        bomb = _orig_drop_bomb(self)
        try:
            if (bomb is not None and CONFIG.get('infinite_bombs')
                    and _is_player_spaz(self)):
                self.bomb_count = self._max_bomb_count
                if self.node:
                    self.node.counter_texture = (
                        PowerupBoxFactory.get().tex_bomb)
                    self.node.counter_text = (
                        'x' + str(int(self._max_bomb_count)))
        except Exception:
            pass
        return bomb

    PlayerSpaz.drop_bomb = _aseman_drop_bomb  # type: ignore[method-assign]
    PlayerSpaz._aseman_inf_bombs = True

# ---- 2) پرش بلند ----
if not getattr(Spaz, '_aseman_super_jump', False):
    _orig_jump_press = Spaz.on_jump_press

    def _aseman_jump_press(self: Spaz) -> None:
        _orig_jump_press(self)
        try:
            if (CONFIG.get('super_jump') and self.node
                    and _is_player_spaz(self)):
                node = self.node
                extra = max(0, int(CONFIG.get('extra_jumps', 2)))

                def _hop(node=node) -> None:
                    if node:
                        node.jump_pressed = False

                        def _press(node=node) -> None:
                            if node:
                                node.jump_pressed = True

                        bs.timer(0.04, _press)

                for i in range(extra):
                    bs.timer(0.18 + 0.20 * i, _hop)
        except Exception:
            pass

    Spaz.on_jump_press = _aseman_jump_press  # type: ignore[method-assign]
    Spaz._aseman_super_jump = True

# ---- 3) سرعت بیشتر و قدرت مشت ----
if not getattr(PlayerSpaz, '_aseman_boost', False):
    _orig_player_init = PlayerSpaz.__init__

    def _aseman_player_init(self: PlayerSpaz, *args: Any,
                            **kwargs: Any) -> None:
        _orig_player_init(self, *args, **kwargs)
        try:
            if self.node:
                if CONFIG.get('speed_boost'):
                    self.node.hockey = True
                punch = float(CONFIG.get('punch_power', 1.0))
                if punch != 1.0:
                    self._punch_power_scale = punch
        except Exception:
            pass

    PlayerSpaz.__init__ = _aseman_player_init  # type: ignore[method-assign]
    PlayerSpaz._aseman_boost = True

# ---- 4) جان بیشتر برای بازیکن ----
if not getattr(PlayerSpaz, '_aseman_hp', False):
    _player_hp = int(CONFIG.get('player_health', 1000))
    if _player_hp > 0:
        # خود بازی جان اولیه را از صفت default_hitpoints می‌گیرد
        # (کلاس Spaz: عدد 1000). با عوض کردن همین صفت روی PlayerSpaz
        # فقط بازیکن‌ها جان بیشتر می‌گیرند؛ بات‌ها عادی می‌مانند و
        # جان باس هم جداگانه با boss_hitpoints تنظیم می‌شود.
        PlayerSpaz.default_hitpoints = _player_hp
    PlayerSpaz._aseman_hp = True


# ==========================================================================
#  پلی‌لیست آماده — برای نسخه رایگان بازی
# ==========================================================================
# فرمت و کلید کانفیگ دقیقاً مطابق خود بازی است:
#   کلید: 'Free-for-All Playlists'  (bauiv1lib/playlist: config_name
#          'Free-for-All' + ' Playlists')
#   هر مدخل: {'type': <module.ClassGame>, 'settings': {..., 'map': ...}}
# نام بازی‌ها به‌صورت مسیر رسمی نسخه 1.7 نوشته شده‌اند تا فیلتر بازی
# (bascenev1.filter_playlist) بی‌واسطه آن‌ها را قبول کند.
_PLAYLIST_KEY = 'Free-for-All Playlists'
_PLAYLIST_NAME = 'Aseman Tower FFA'

_PLAYLIST_GAMES = [
    {
        'type': 'bascenev1lib.game.deathmatch.DeathMatchGame',
        'settings': {
            'Epic Mode': False,
            'Kills to Win Per Player': 10,
            'Respawn Times': 1.0,
            'Time Limit': 300,
            'map': 'Aseman Tower',
        },
    },
    {
        'type': 'bascenev1lib.game.elimination.EliminationGame',
        'settings': {
            'Epic Mode': False,
            'Lives Per Player': 3,
            'Respawn Times': 1.0,
            'Time Limit': 300,
            'map': 'Aseman Tower',
        },
    },
    {
        'type': 'bascenev1lib.game.kingofthehill.KingOfTheHillGame',
        'settings': {
            'Hold Time': 30,
            'Respawn Times': 1.0,
            'Time Limit': 300,
            'map': 'Aseman Tower',
        },
    },
    {
        'type': 'bascenev1lib.game.keepaway.KeepAwayGame',
        'settings': {
            'Hold Time': 30,
            'Respawn Times': 1.0,
            'Time Limit': 300,
            'map': 'Aseman Tower',
        },
    },
]


def _add_playlist() -> bool:
    """Register the ready-made FFA playlist in the game config.

    True if it was added now; False if it already existed, the feature
    is off in CONFIG, or anything went wrong.
    """
    try:
        if not CONFIG.get('add_playlist', True):
            return False
        cfg = babase.app.config
        if cfg is None:
            return False
        playlists = cfg.setdefault(_PLAYLIST_KEY, {})
        name = str(CONFIG.get('playlist_name', _PLAYLIST_NAME))
        if name in playlists:
            return False
        playlists[name] = copy.deepcopy(_PLAYLIST_GAMES)
        cfg.commit()
        return True
    except Exception:
        return False


# ==========================================================================
#  ثبت نقشه در بازی + پلاگین
# ==========================================================================
_MAP_NAME = 'Aseman Tower'


def _register_map() -> None:
    """Register the custom map with the game (idempotent)."""
    try:
        classic = babase.app.classic
        if classic is not None and _MAP_NAME not in classic.maps:
            try:
                # از 1.8 به بعد مسیر عمومی bs.register_map در دسترس است
                bs.register_map(AsemanTowerMap)
            except Exception:
                bs._map.register_map(AsemanTowerMap)
            return
    except Exception:
        pass
    # روش جایگزین: مستقیم داخل دیکشنری نقشه‌ها
    try:
        classic = babase.app.classic
        if classic is not None and _MAP_NAME not in classic.maps:
            classic.maps[_MAP_NAME] = AsemanTowerMap
    except Exception:
        pass


# ba_meta export plugin
class AsemanTowerPlugin(babase.Plugin):
    """پلاگین اصلی: ثبت نقشه + پلی‌لیست آماده + پیام خوش‌آمد."""

    def __init__(self) -> None:
        _register_map()
        self.playlist_added = _add_playlist()

    def on_app_running(self) -> None:
        # اگر ثبت نقشه/پلی‌لیست در لحظه لود پلاگین ممکن نشده بود،
        # اینجا بعد از آماده‌شدن کامل بازی دوباره تلاش می‌شود.
        _register_map()
        if not getattr(self, 'playlist_added', False):
            self.playlist_added = _add_playlist()
        _screenmessage(_msg('welcome'))
        if getattr(self, 'playlist_added', False):
            _screenmessage(_msg('playlist'), color=(1.0, 0.9, 0.4))
        try:
            bs.timer(6.0,
                     babase.CallPartial(_screenmessage, _msg('map_hint'),
                                 (0.7, 0.85, 1.0)))
        except Exception:
            pass
