# Released under the MIT License. See LICENSE file for details.
#
# XPSystem - a chat-command XP & level system for BombSquad 1.8.x (api 9).
#
# ba_meta require api 9
"""XP & level system for BombSquad 1.8.x.

Kill players or bots to earn XP, gain levels (Rookie up to BombSquad
God) and climb the leaderboard. Progress is saved to a json file in
the mods folder, so it survives game restarts.

Chat commands:

    xp      - show your level, xp, progress and K/D
    top     - show the top 5 players by xp
    xphelp  - help and scoring rules

Kills are credited to whoever damaged the victim within the last few
seconds, exactly like the game itself credits kills.
"""

from __future__ import annotations

import json
import os
from typing import Any

import babase
import bauiv1
import bascenev1 as bs
import bascenev1._hooks as _bshooks

from bascenev1lib.actor.spaz import Spaz

MOD_NAME = 'XPSystem'
DATA_FILE = 'bs_xp_data.json'

# ---------------------------------------------------------------------------
# Tunables (feel free to tweak these numbers)
# ---------------------------------------------------------------------------

XP_PER_KILL = 10
XP_PER_DEATH = 2  # xp lost when dying; total xp never goes below zero
MULTIKILL_WINDOW = 3.0  # seconds between kills for a bonus
MULTIKILL_BONUS = 5  # extra xp for double/triple/... kills
KILL_WINDOW = 5.0  # hit -> death seconds for kill credit
LEVEL_BASE = 100  # xp needed to go from level 1 to 2
LEVEL_STEP = 50  # each further level needs this much more xp
LEVEL_CAP = 99

LEVEL_TITLES = [
    (30, 'BombSquad God'),
    (20, 'Legend'),
    (15, 'Master'),
    (10, 'Elite'),
    (6, 'Warrior'),
    (3, 'Fighter'),
    (1, 'Rookie'),
]

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_SENDING = [False]
_ORIG_FILTER_CHAT: Any = None
_ORIG_SPAZ_HANDLE: Any = None
_INSTALLED = [False]

_DATA: dict[str, dict[str, Any]] = {}
_LASTKILL: dict[str, float] = {}

GOLD = (1.0, 0.8, 0.2)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _say(text: str, color: Any = None) -> None:
    """Chat reply, marked as coming from XPSystem."""
    _SENDING[0] = True
    try:
        if color is None:
            try:
                bs.chatmessage(text, sender_override=MOD_NAME)
            except TypeError:
                bs.chatmessage(text)
        else:
            try:
                bs.chatmessage(text, color=color, sender_override=MOD_NAME)
            except TypeError:
                bs.chatmessage(text)
    except Exception:
        pass
    finally:
        _SENDING[0] = False


def _reply(text: str) -> None:
    _say(text)


def _host_activity() -> Any:
    try:
        return bs.get_foreground_host_activity()
    except Exception:
        return None


def _pname(player: Any) -> str | None:
    try:
        name = player.getname(full=False, icon=False)
        if name:
            return str(name)
    except Exception:
        pass
    return None


def _client_name(act: Any, client_id: int) -> str | None:
    """Display name of the first player controlled by this client."""
    for player in act.players:
        try:
            sessplayer = player.sessionplayer
            if sessplayer is not None and not bool(sessplayer):
                continue
            if sessplayer.inputdevice.client_id == client_id:
                name = _pname(player)
                if name:
                    return name
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# Levels & persistence
# ---------------------------------------------------------------------------


def _data_path() -> str:
    try:
        return os.path.join(bauiv1.app.env.python_directory_user, DATA_FILE)
    except Exception:
        return DATA_FILE


def _load() -> None:
    global _DATA
    _DATA = {}
    try:
        with open(_data_path(), 'r', encoding='utf-8') as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            _DATA = {k: v for k, v in raw.items() if isinstance(v, dict)}
    except Exception:
        _DATA = {}


def _save() -> None:
    try:
        with open(_data_path(), 'w', encoding='utf-8') as f:
            json.dump(_DATA, f)
    except Exception:
        pass


def _record(name: str) -> dict[str, Any]:
    key = name.lower()
    rec = _DATA.get(key)
    if rec is None:
        rec = {'xp': 0, 'kills': 0, 'deaths': 0, 'name': name}
        _DATA[key] = rec
    rec['name'] = name
    return rec


def _level_info(xp: int) -> tuple[int, int, int]:
    """Return (level, xp_into_level, xp_needed_for_next)."""
    level = 1
    remaining = max(0, xp)
    need = LEVEL_BASE
    while remaining >= need and level < LEVEL_CAP:
        remaining -= need
        level += 1
        need = LEVEL_BASE + (level - 1) * LEVEL_STEP
    return level, remaining, need


def _title_for(level: int) -> str:
    for minlevel, title in LEVEL_TITLES:
        if level >= minlevel:
            return title
    return 'Rookie'


def _bar(cur: int, need: int, width: int = 10) -> str:
    need = max(1, need)
    filled = int(width * min(cur, need) / need)
    return '[' + '#' * filled + '-' * (width - filled) + ']'


# ---------------------------------------------------------------------------
# Kill / death tracking
# ---------------------------------------------------------------------------


def _on_death(spaz: Any) -> None:
    victim_name = None
    try:
        player = spaz.getplayer(bs.Player)
        if player:
            victim_name = _pname(player)
    except Exception:
        victim_name = None

    # Victim pays a small xp toll (so dying is never completely free).
    if victim_name:
        vrec = _record(victim_name)
        vrec['deaths'] = vrec.get('deaths', 0) + 1
        vrec['xp'] = max(0, vrec.get('xp', 0) - XP_PER_DEATH)

    # Find whoever attacked us last (if any) and credit them.
    attacker = getattr(spaz, '_xp_attacker', None)
    attack_time = getattr(spaz, '_xp_attack_time', None)
    if attacker is not None and attack_time is not None:
        try:
            fresh = (bs.time() - float(attack_time)) <= KILL_WINDOW
        except Exception:
            fresh = False
        if fresh:
            try:
                killer_name = _pname(attacker)
            except Exception:
                killer_name = None
            if killer_name and not (
                victim_name and killer_name.lower() == victim_name.lower()
            ):
                _award_kill(killer_name)
    _save()


def _award_kill(killer_name: str) -> None:
    rec = _record(killer_name)
    old_level = _level_info(rec.get('xp', 0))[0]

    bonus = 0
    key = killer_name.lower()
    now = babase.apptime()
    last = _LASTKILL.get(key)
    if last is not None and (now - last) <= MULTIKILL_WINDOW:
        bonus = MULTIKILL_BONUS
        _say(f'{killer_name} MULTI KILL! (+{XP_PER_KILL + bonus} xp)', GOLD)
    _LASTKILL[key] = now

    rec['kills'] = rec.get('kills', 0) + 1
    rec['xp'] = rec.get('xp', 0) + XP_PER_KILL + bonus

    new_level, _cur, _need = _level_info(rec['xp'])
    if new_level > old_level:
        title = _title_for(new_level)
        _say(f'{killer_name} reached Level {new_level} - {title}!', GOLD)


# ---------------------------------------------------------------------------
# Chat commands
# ---------------------------------------------------------------------------


def _cmd_xp(client_id: int, _args: list[str], act: Any) -> None:
    name = _client_name(act, client_id)
    if name is None:
        _reply('Join a game first so I know who you are.')
        return
    rec = _record(name)
    xp = rec.get('xp', 0)
    level, cur, need = _level_info(xp)
    title = _title_for(level)
    _reply(
        f'{name}: Level {level} {title} | {xp} xp | '
        f'K:{rec.get("kills", 0)} D:{rec.get("deaths", 0)}'
    )
    _reply(f'Next level: {cur}/{need} {_bar(cur, need)}')


def _cmd_top(_client_id: int, _args: list[str], _act: Any) -> None:
    if not _DATA:
        _reply('No xp records yet - go get some kills!')
        return
    ranked = sorted(
        _DATA.items(), key=lambda kv: kv[1].get('xp', 0), reverse=True
    )[:5]
    _reply('--- TOP 5 by XP ---')
    for i, (key, rec) in enumerate(ranked, start=1):
        name = rec.get('name', key)
        level = _level_info(rec.get('xp', 0))[0]
        _reply(
            f'{i}. {name} - Level {level} ({rec.get("xp", 0)} xp, '
            f'K:{rec.get("kills", 0)})'
        )


def _cmd_xphelp(_client_id: int, _args: list[str], _act: Any) -> None:
    _reply(f'--- {MOD_NAME} ---')
    _reply('xp = your stats | top = leaderboard | xphelp = this list')
    _reply(
        f'Each kill +{XP_PER_KILL} xp, death -{XP_PER_DEATH} xp, '
        f'multi-kill bonus +{MULTIKILL_BONUS}.'
    )
    _reply('Levels: Rookie > Fighter > Warrior > Elite > Master > Legend > God')


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------


def _hook_spaz() -> None:
    """Wrap Spaz.handlemessage once to track hits and deaths."""
    global _ORIG_SPAZ_HANDLE
    if getattr(Spaz, '_xp_hook_installed', False):
        return
    _ORIG_SPAZ_HANDLE = Spaz.handlemessage

    def _patched(self: Any, msg: Any) -> Any:
        if isinstance(msg, bs.HitMessage):
            try:
                src = msg.source_player
                if src is not None:
                    self._xp_attacker = src
                    self._xp_attack_time = bs.time()
            except Exception:
                pass
        elif isinstance(msg, bs.DieMessage):
            try:
                if not getattr(self, '_dead', False):
                    _on_death(self)
            except Exception:
                pass
        return _ORIG_SPAZ_HANDLE(self, msg)

    Spaz.handlemessage = _patched
    Spaz._xp_hook_installed = True  # type: ignore[attr-defined]


def _filter_chat_message(msg: str, client_id: int) -> str | None:
    try:
        _handle_command(msg, client_id)
    except Exception:
        pass
    return _ORIG_FILTER_CHAT(msg, client_id)


def _handle_command(msg: str, client_id: int) -> None:
    if _SENDING[0] or not isinstance(msg, str):
        return
    text = msg.strip()
    if not text:
        return
    if text[0] in ('/', '!'):
        text = text[1:].strip()
    if not text:
        return
    parts = text.split()
    handler = _COMMANDS.get(parts[0].lower())
    if handler is None:
        return
    act = _host_activity()
    if act is None:
        return
    with act.context:
        try:
            handler(client_id, parts[1:], act)
        except Exception:
            pass


_COMMANDS: dict[str, Any] = {
    'xp': _cmd_xp,
    'stats': _cmd_xp,
    'top': _cmd_top,
    'top5': _cmd_top,
    'xphelp': _cmd_xphelp,
    'xph': _cmd_xphelp,
}


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------


def _install() -> None:
    if _INSTALLED[0]:
        return
    _INSTALLED[0] = True
    _load()
    _hook_spaz()

    global _ORIG_FILTER_CHAT
    _ORIG_FILTER_CHAT = _bshooks.filter_chat_message
    _bshooks.filter_chat_message = _filter_chat_message
    # The native layer caches the hook functions; make it re-read ours.
    bs.reload_hooks()

    # The chat system is not up yet during boot; greet a bit later.
    babase.apptimer(
        6.0,
        lambda: _reply(
            'XPSystem loaded! Kills give xp - type "xphelp" in chat.'
        ),
    )


# ba_meta export babase.Plugin
class XPSystemPlugin(babase.Plugin):
    """Registers the xp tracking and chat hook when the app starts."""

    def on_app_running(self) -> None:
        _install()
