# Released under the MIT License. See LICENSE file for details.
#
# FlyCheats - a chat-command cheat pack for BombSquad 1.8.x (api 9).
#
# ba_meta require api 9
"""Chat-command cheat pack for BombSquad 1.8.x.

Type plain words in the party chat to toggle powers for yourself:

    fly  speed  god  heal  inf  bombs  btype  power  punch  ptime
    pu  mega  shield  curse  spawnpu  kill  tp  freeze  unfreeze
    boom  players  color  codes  off

Commands work while hosting a game (you are always host in solo and
in games hosted from your PC). Every player in the lobby can use the
commands and each one gets their own powers.
"""

from __future__ import annotations

import math
from typing import Any

import babase
import bascenev1 as bs
import bascenev1._hooks as _bshooks

from bascenev1lib.actor.bomb import Blast
from bascenev1lib.actor.powerupbox import PowerupBox
from bascenev1lib.actor.spazfactory import SpazFactory

MOD_NAME = 'FlyCheats'

# ---------------------------------------------------------------------------
# Tunables (feel free to tweak these numbers)
# ---------------------------------------------------------------------------

FLY_FORCE_BASE = 380.0  # upward kick_back force at fly power 1.0
FLY_FORCE_MAX = 2200.0  # safety cap
FLY_VY_CAP = 7.5  # skip thrust while rising faster than this (m/s)
FLY_TICK = 0.05  # thrust interval (seconds)

SPEED_FORCE_BASE = 260.0  # extra push per speed point above 1.0
SPEED_FORCE_MAX = 900.0
SPEED_TICK = 0.05
SPEED_MIN_MOVE = 0.6  # only boost when actually moving

PU_REAPPLY = 3.0  # re-apply timed powerups every N seconds

FLY_MIN = 0.5
FLY_MAX = 5.0
SPEED_MIN = 0.5
SPEED_MAX = 5.0
POWER_MIN = 0.5
POWER_MAX = 10.0
PUNCH_MIN = 1.0
PUNCH_MAX = 10.0
BOMBS_MIN = 1
BOMBS_MAX = 30
PTIME_MAX = 600.0

POWERUP_ALIASES = {
    'triple': 'triple_bombs',
    'triple_bombs': 'triple_bombs',
    'ice': 'ice_bombs',
    'ice_bombs': 'ice_bombs',
    'impact': 'impact_bombs',
    'impact_bombs': 'impact_bombs',
    'sticky': 'sticky_bombs',
    'sticky_bombs': 'sticky_bombs',
    'mine': 'land_mines',
    'mines': 'land_mines',
    'land_mines': 'land_mines',
    'punch': 'punch',
    'gloves': 'punch',
    'shield': 'shield',
    'health': 'health',
    'heal': 'health',
    'curse': 'curse',
}

# 'triple_bombs', 'ice_bombs', 'impact_bombs', 'sticky_bombs', 'punch',
# 'shield' and 'land_mines' can be kept alive for a while; the rest are
# instant effects.
TIMED_POWERUPS = {
    'triple_bombs',
    'ice_bombs',
    'impact_bombs',
    'sticky_bombs',
    'punch',
    'shield',
    'land_mines',
}

BOMB_TYPES = ('normal', 'ice', 'impact', 'sticky')

COLORS = {
    'red': (1.0, 0.25, 0.25),
    'orange': (1.0, 0.5, 0.1),
    'yellow': (1.0, 0.9, 0.2),
    'green': (0.3, 1.0, 0.3),
    'blue': (0.3, 0.5, 1.0),
    'purple': (0.7, 0.3, 1.0),
    'pink': (1.0, 0.4, 0.8),
    'white': (1.0, 1.0, 1.0),
    'black': (0.1, 0.1, 0.1),
    'default': None,  # resolved to player's original color
}

# ---------------------------------------------------------------------------
# Per-client state
# ---------------------------------------------------------------------------


def _new_state() -> dict[str, Any]:
    return {
        'fly': 0.0,  # 0 = off, else 0.5..5
        'speed': 0.0,  # 0 = off, else 0.5..5
        'god': False,
        'inf': False,
        'bombs': 0,  # 0 = no override, else 1..30
        'btype': None,  # None or 'normal'/'ice'/'impact'/'sticky'
        'power': 0.0,  # 0 = no override, else blast radius multiplier
        'punch': 0.0,  # 0 = no override, else punch power multiplier
        'ptime': 30.0,  # default powerup duration in seconds (0 = forever)
        'pus': [],  # pending timed powerups: [type, remaining, since_last]
        'rainbow': False,
        'hue': 0.0,
    }


_CHEATS: dict[int, dict[str, Any]] = {}
_SENDING = [False]
_ORIG_FILTER_CHAT = None
_INSTALLED = [False]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _reply(text: str) -> None:
    """Show a chat reply to everyone, marked as coming from FlyCheats."""
    _SENDING[0] = True
    try:
        try:
            bs.chatmessage(text, sender_override=MOD_NAME)
        except TypeError:
            bs.chatmessage(text)
    except Exception:
        pass
    finally:
        _SENDING[0] = False


def _host_activity() -> Any:
    try:
        act = bs.get_foreground_host_activity()
    except Exception:
        return None
    return act


def _client_players(act: Any, client_id: int) -> list[Any]:
    """Players controlled by the given client id (host itself is -1)."""
    out = []
    for player in act.players:
        try:
            sessplayer = player.sessionplayer
            if sessplayer is not None and not bool(sessplayer):
                continue
            if sessplayer.inputdevice.client_id == client_id:
                out.append(player)
        except Exception:
            continue
    return out


def _my_spaz(act: Any, client_id: int) -> Any:
    """First living spaz actor controlled by this client, or None."""
    for player in _client_players(act, client_id):
        actor = getattr(player, 'actor', None)
        if actor is None:
            continue
        node = getattr(actor, 'node', None)
        if node is None:
            continue
        try:
            if actor._dead:  # pylint: disable=protected-access
                continue
        except Exception:
            pass
        return actor
    return None


def _resolve_target(act: Any, arg: str) -> Any:
    """Resolve a 1-based player number (as shown by the players command)."""
    try:
        idx = int(arg)
    except Exception:
        return None
    players = list(act.players)
    if idx < 1 or idx > len(players):
        return None
    player = players[idx - 1]
    actor = getattr(player, 'actor', None)
    if actor is None or getattr(actor, 'node', None) is None:
        return None
    return actor


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _to_float(text: str) -> float | None:
    try:
        return float(text)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Impulse helpers (all pure physics; the kick_back message deals no damage)
# ---------------------------------------------------------------------------


def _apply_fly(spaz: Any, power: float) -> None:
    node = spaz.node
    try:
        pos = node.position
        vel = node.velocity
    except Exception:
        return
    if vel[1] > FLY_VY_CAP:
        return
    mag = _clamp(FLY_FORCE_BASE * power, 10.0, FLY_FORCE_MAX)
    node.handlemessage('kick_back', pos[0], pos[1], pos[2], 0.0, 1.0, 0.0, mag)


def _apply_speed(spaz: Any, mult: float) -> None:
    node = spaz.node
    try:
        pos = node.position
        vel = node.velocity
    except Exception:
        return
    hspeed = math.sqrt(vel[0] * vel[0] + vel[2] * vel[2])
    if hspeed < SPEED_MIN_MOVE or hspeed > 6.0 + 4.0 * mult:
        return
    extra = SPEED_FORCE_BASE * max(0.0, mult - 1.0)
    mag = _clamp(extra, 10.0, SPEED_FORCE_MAX)
    node.handlemessage(
        'kick_back',
        pos[0],
        pos[1],
        pos[2],
        vel[0] / hspeed,
        0.0,
        vel[2] / hspeed,
        mag,
    )


# ---------------------------------------------------------------------------
# Timed powerup management
# ---------------------------------------------------------------------------


def _apply_powerup(spaz: Any, putype: str) -> None:
    spaz.handlemessage(bs.PowerupMessage(putype))


def _cleanup_powerup(st: dict[str, Any], spaz: Any, putype: str) -> None:
    """Revert temporary effects of a timed powerup when it runs out."""
    try:
        if putype in ('ice_bombs', 'impact_bombs', 'sticky_bombs'):
            spaz.bomb_type = st['btype'] if st['btype'] else 'normal'
        elif putype == 'triple_bombs':
            spaz.set_bomb_count(st['bombs'] if st['bombs'] else 1)
        elif putype == 'punch':
            spaz._punch_power_scale = SpazFactory.get().punch_power_scale
            spaz._has_boxing_gloves = False
            if spaz.node:
                spaz.node.boxing_gloves = False
    except Exception:
        pass


def _grant_powerup(
    st: dict[str, Any], spaz: Any, putype: str, duration: float
) -> None:
    _apply_powerup(spaz, putype)
    if putype in TIMED_POWERUPS:
        # duration <= 0 means "keep until turned off"
        st['pus'].append([putype, duration if duration > 0 else -1.0, 0.0])


def _powerup_tick(st: dict[str, Any], spaz: Any) -> None:
    for entry in st['pus']:
        putype, remaining, since = entry
        if remaining > 0:
            entry[1] = remaining = max(0.0, remaining - 0.25)
            if remaining <= 0.0:
                _cleanup_powerup(st, spaz, putype)
                continue
        if remaining < 0 or remaining > 0:
            entry[2] = since = since + 0.25
            if since >= PU_REAPPLY:
                entry[2] = 0.0
                _apply_powerup(spaz, putype)
    st['pus'] = [e for e in st['pus'] if e[1] != 0.0]


# ---------------------------------------------------------------------------
# Repeating ticks (self-rescheduling apptimers; run outside scene context
# so every scene touch is wrapped in the activity context)
# ---------------------------------------------------------------------------


def _motion_tick() -> None:
    babase.apptimer(SPEED_TICK, _motion_tick)
    act = _host_activity()
    if act is None:
        return
    with act.context:
        for client_id, st in list(_CHEATS.items()):
            if st['fly'] <= 0.0 and st['speed'] <= 1.0:
                continue
            spaz = _my_spaz(act, client_id)
            if spaz is None:
                continue
            try:
                if st['fly'] > 0.0:
                    _apply_fly(spaz, st['fly'])
                if st['speed'] > 1.0:
                    _apply_speed(spaz, st['speed'])
            except Exception:
                pass


def _buffs_tick() -> None:
    babase.apptimer(0.25, _buffs_tick)
    act = _host_activity()
    if act is None:
        return
    with act.context:
        try:
            factory = SpazFactory.get()
        except Exception:
            factory = None
        for client_id, st in list(_CHEATS.items()):
            if not (
                st['god']
                or st['inf']
                or st['bombs']
                or st['btype']
                or st['power']
                or st['punch']
                or st['rainbow']
                or st['pus']
            ):
                continue
            spaz = _my_spaz(act, client_id)
            if spaz is None:
                continue
            try:
                if st['god']:
                    spaz.node.invincible = True
                if st['inf']:
                    spaz.bomb_count = spaz._max_bomb_count
                if st['bombs'] and not _has_pending(st, 'triple_bombs'):
                    spaz.set_bomb_count(st['bombs'])
                if st['btype'] and not (
                    _has_pending(st, 'ice_bombs')
                    or _has_pending(st, 'impact_bombs')
                    or _has_pending(st, 'sticky_bombs')
                ):
                    if spaz.bomb_type != st['btype']:
                        spaz.bomb_type = st['btype']
                if st['power']:
                    spaz.blast_radius = 2.0 * st['power']
                if st['punch'] and factory is not None:
                    spaz._punch_power_scale = (
                        factory.punch_power_scale * st['punch']
                    )
                if st['rainbow']:
                    st['hue'] = (st['hue'] + 0.04) % 1.0
                    spaz.node.color = _hsv_to_rgb(st['hue'])
                if st['pus']:
                    _powerup_tick(st, spaz)
            except Exception:
                pass


def _has_pending(st: dict[str, Any], putype: str) -> bool:
    return any(e[0] == putype for e in st['pus'])


def _hsv_to_rgb(h: float) -> tuple[float, float, float]:
    i = int(h * 6.0) % 6
    f = h * 6.0 - int(h * 6.0)
    q = 1.0 - f
    table = [
        (1.0, f, 0.0),
        (q, 1.0, 0.0),
        (0.0, 1.0, f),
        (0.0, q, 1.0),
        (f, 0.0, 1.0),
        (1.0, 0.0, q),
    ]
    return table[i]


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def _cmd_fly(st: dict, _cid: int, args: list[str], _act: Any) -> None:
    if args and args[0].lower() in ('off', '0', 'disable'):
        st['fly'] = 0.0
        _reply('Fly OFF.')
        return
    power = _to_float(args[0]) if args else 1.0
    if power is None:
        power = 1.0
    power = _clamp(power, FLY_MIN, FLY_MAX)
    st['fly'] = power
    _reply(f'Fly ON (power {power:g}). Type "fly off" to land.')


def _cmd_speed(st: dict, _cid: int, args: list[str], _act: Any) -> None:
    if args and args[0].lower() in ('off', '0', 'normal'):
        st['speed'] = 0.0
        _reply('Speed boost OFF.')
        return
    mult = _to_float(args[0]) if args else 2.0
    if mult is None:
        mult = 2.0
    mult = _clamp(mult, SPEED_MIN, SPEED_MAX)
    st['speed'] = mult
    _reply(f'Speed boost x{mult:g} ON.')


def _cmd_god(st: dict, _cid: int, args: list[str], _act: Any) -> None:
    if args and args[0].lower() in ('off', '0'):
        st['god'] = False
    elif args and args[0].lower() in ('on', '1'):
        st['god'] = True
    else:
        st['god'] = not st['god']
    act = _host_activity()
    spaz = _my_spaz(act, _cid) if act else None
    if spaz is not None:
        spaz.node.invincible = st['god']
    _reply('God mode ON - nothing can hurt you.' if st['god']
           else 'God mode OFF.')


def _cmd_heal(st: dict, _cid: int, _args: list[str], act: Any) -> None:
    spaz = _my_spaz(act, _cid)
    if spaz is None:
        _reply('No living player found for you.')
        return
    _apply_powerup(spaz, 'health')
    _reply('Fully healed.')


def _cmd_inf(st: dict, _cid: int, args: list[str], _act: Any) -> None:
    if args and args[0].lower() in ('off', '0'):
        st['inf'] = False
    elif args and args[0].lower() in ('on', '1'):
        st['inf'] = True
    else:
        st['inf'] = not st['inf']
    _reply('Infinite bombs ON.' if st['inf'] else 'Infinite bombs OFF.')


def _cmd_bombs(st: dict, _cid: int, args: list[str], act: Any) -> None:
    count = int(_to_float(args[0]) or 0) if args else 0
    if count < BOMBS_MIN or count > BOMBS_MAX:
        _reply(f'Usage: bombs <{BOMBS_MIN}-{BOMBS_MAX}>')
        return
    st['bombs'] = count
    spaz = _my_spaz(act, _cid)
    if spaz is not None:
        spaz.set_bomb_count(count)
    _reply(f'Max bombs set to {count}.')


def _cmd_btype(st: dict, _cid: int, args: list[str], act: Any) -> None:
    if not args or args[0].lower() not in BOMB_TYPES:
        _reply(f'Usage: btype <{"|".join(BOMB_TYPES)}>')
        return
    btype = args[0].lower()
    st['btype'] = None if btype == 'normal' else btype
    spaz = _my_spaz(act, _cid)
    if spaz is not None:
        spaz.bomb_type = btype
        spaz.bomb_type_default = btype
    _reply(f'Bomb type: {btype.upper()}')


def _cmd_power(st: dict, _cid: int, args: list[str], act: Any) -> None:
    if args and args[0].lower() in ('off', '1', 'normal'):
        st['power'] = 0.0
        spaz = _my_spaz(act, _cid)
        if spaz is not None:
            spaz.blast_radius = 2.0
        _reply('Blast power reset.')
        return
    mult = _to_float(args[0]) if args else None
    if mult is None:
        _reply(f'Usage: power <{POWER_MIN:g}-{POWER_MAX:g}>')
        return
    mult = _clamp(mult, POWER_MIN, POWER_MAX)
    st['power'] = mult
    spaz = _my_spaz(act, _cid)
    if spaz is not None:
        spaz.blast_radius = 2.0 * mult
    _reply(f'Blast power x{mult:g} (radius {2.0 * mult:g}).')


def _cmd_punch(st: dict, _cid: int, args: list[str], act: Any) -> None:
    if args and args[0].lower() in ('off', '1', 'normal'):
        st['punch'] = 0.0
        spaz = _my_spaz(act, _cid)
        if spaz is not None:
            spaz._punch_power_scale = SpazFactory.get().punch_power_scale
        _reply('Punch power reset.')
        return
    mult = _to_float(args[0]) if args else None
    if mult is None:
        _reply(f'Usage: punch <{PUNCH_MIN:g}-{PUNCH_MAX:g}>')
        return
    mult = _clamp(mult, PUNCH_MIN, PUNCH_MAX)
    st['punch'] = mult
    spaz = _my_spaz(act, _cid)
    if spaz is not None:
        spaz._punch_power_scale = SpazFactory.get().punch_power_scale * mult
    _reply(f'Punch power x{mult:g} ON.')


def _cmd_ptime(st: dict, _cid: int, args: list[str], _act: Any) -> None:
    if args and args[0].lower() in ('off', 'forever'):
        st['ptime'] = 0.0
        _reply('Powerups now last until you type "off".')
        return
    secs = _to_float(args[0]) if args else None
    if secs is None or secs < 0 or secs > PTIME_MAX:
        _reply(f'Usage: ptime <0-{PTIME_MAX:g}> seconds (0 = forever)')
        return
    st['ptime'] = secs
    label = 'forever' if secs == 0 else f'{secs:g}s'
    _reply(f'Powerup duration set to {label}.')


def _cmd_pu(st: dict, _cid: int, args: list[str], act: Any) -> None:
    if not args:
        types = '/'.join(sorted({k for k in POWERUP_ALIASES if '_' not in k}))
        _reply(f'Usage: pu <{types}> [seconds]')
        return
    putype = POWERUP_ALIASES.get(args[0].lower())
    if putype is None:
        _reply('Unknown powerup. Type "codes" for the list.')
        return
    spaz = _my_spaz(act, _cid)
    if spaz is None:
        _reply('No living player found for you.')
        return
    duration = st['ptime']
    if len(args) > 1:
        override = _to_float(args[1])
        if override is not None:
            duration = override
    if putype in ('health', 'curse'):
        _apply_powerup(spaz, putype)
        _reply('Healed.' if putype == 'health' else 'You are cursed... hehe')
        return
    _grant_powerup(st, spaz, putype, duration)
    label = 'forever' if duration <= 0 else f'{duration:g}s'
    _reply(f'Powerup {putype.upper()} granted ({label}).')


def _cmd_mega(st: dict, _cid: int, _args: list[str], act: Any) -> None:
    spaz = _my_spaz(act, _cid)
    if spaz is None:
        _reply('No living player found for you.')
        return
    _grant_powerup(st, spaz, 'triple_bombs', -1.0)
    _grant_powerup(st, spaz, 'shield', -1.0)
    _grant_powerup(st, spaz, 'punch', -1.0)
    _reply('MEGA combo: triple bombs + shield + mega punch (until off).')


def _cmd_shield(st: dict, _cid: int, args: list[str], act: Any) -> None:
    spaz = _my_spaz(act, _cid)
    if spaz is None:
        _reply('No living player found for you.')
        return
    duration = st['ptime']
    if args:
        override = _to_float(args[0])
        if override is not None:
            duration = override
    _grant_powerup(st, spaz, 'shield', duration)
    label = 'forever' if duration <= 0 else f'{duration:g}s'
    _reply(f'Shield ON ({label}).')


def _cmd_curse(st: dict, _cid: int, _args: list[str], act: Any) -> None:
    spaz = _my_spaz(act, _cid)
    if spaz is None:
        _reply('No living player found for you.')
        return
    spaz.curse()
    _reply('You are cursed. Have fun!')


def _cmd_spawnpu(st: dict, _cid: int, args: list[str], act: Any) -> None:
    putype = POWERUP_ALIASES.get(args[0].lower()) if args else None
    if putype is None:
        _reply('Usage: spawnpu <triple/ice/impact/sticky/mine/punch/shield>')
        return
    spaz = _my_spaz(act, _cid)
    if spaz is None:
        _reply('No living player found for you.')
        return
    pos = spaz.node.position
    PowerupBox(
        position=(pos[0], pos[1] + 1.0, pos[2]), poweruptype=putype
    )
    _reply(f'Powerup box spawned: {putype.upper()}')


def _cmd_kill(st: dict, _cid: int, _args: list[str], act: Any) -> None:
    spaz = _my_spaz(act, _cid)
    if spaz is None:
        _reply('No living player found for you.')
        return
    spaz.handlemessage(bs.DieMessage())
    _reply('Respawning...')


def _cmd_tp(st: dict, _cid: int, args: list[str], act: Any) -> None:
    if not args:
        _reply('Usage: tp <player number>. Type "players" first.')
        return
    me = _my_spaz(act, _cid)
    target = _resolve_target(act, args[0])
    if me is None or target is None:
        _reply('No such player number.')
        return
    tpos = target.node.position
    me.handlemessage(bs.StandMessage((tpos[0], tpos[1], tpos[2]), 0.0))
    _reply('Teleported.')


def _cmd_freeze(st: dict, _cid: int, args: list[str], act: Any) -> None:
    if not args:
        _reply('Usage: freeze <player number>.')
        return
    target = _resolve_target(act, args[0])
    if target is None:
        _reply('No such player number.')
        return
    target.handlemessage(bs.FreezeMessage())
    _reply('Target frozen. Brrr!')


def _cmd_unfreeze(st: dict, _cid: int, args: list[str], act: Any) -> None:
    if not args:
        _reply('Usage: unfreeze <player number>.')
        return
    target = _resolve_target(act, args[0])
    if target is None:
        _reply('No such player number.')
        return
    target.handlemessage(bs.ThawMessage())
    _reply('Target unfrozen.')


def _cmd_boom(st: dict, _cid: int, args: list[str], act: Any) -> None:
    if not args:
        _reply('Usage: boom <player number>.')
        return
    target = _resolve_target(act, args[0])
    if target is None:
        _reply('No such player number.')
        return
    me = _my_spaz(act, _cid)
    tpos = target.node.position
    Blast(
        position=(tpos[0], tpos[1] + 0.5, tpos[2]),
        blast_radius=2.5,
        source_player=me.source_player if me is not None else None,
    )
    _reply('BOOM!')


def _cmd_players(st: dict, _cid: int, _args: list[str], act: Any) -> None:
    players = list(act.players)
    if not players:
        _reply('No players in this game.')
        return
    lines = []
    for i, player in enumerate(players, start=1):
        try:
            name = player.getname(full=False, icon=False)
        except Exception:
            name = '???'
        alive = 'alive' if player.is_alive() else 'dead'
        lines.append(f'{i}. {name} ({alive})')
    _reply('Players: ' + '  '.join(lines))


def _cmd_color(st: dict, _cid: int, args: list[str], act: Any) -> None:
    if not args:
        _reply(
            'Usage: color <'
            + '/'.join(COLORS)
            + '/rainbow/off>'
        )
        return
    spaz = _my_spaz(act, _cid)
    if spaz is None:
        _reply('No living player found for you.')
        return
    name = args[0].lower()
    if name == 'rainbow':
        st['rainbow'] = True
        _reply('RAINBOW mode ON!')
        return
    st['rainbow'] = False
    rgb = COLORS.get(name)
    if rgb is None and name not in ('off', 'default'):
        _reply('Unknown color.')
        return
    if rgb is None:
        rgb = _original_color(spaz)
    spaz.node.color = rgb
    _reply(f'Body color: {name.upper()}')


def _original_color(spaz: Any) -> tuple[float, float, float]:
    player = None
    try:
        player = spaz.getplayer(bs.Player)
    except Exception:
        pass
    if player is not None and player.color:
        return (player.color[0], player.color[1], player.color[2])
    return (1.0, 1.0, 1.0)


def _cmd_codes(st: dict, _cid: int, _args: list[str], _act: Any) -> None:
    _reply('--- FlyCheats commands ---')
    _reply(
        'fly [0.5-5]  speed [0.5-5]  god  heal  inf  bombs <1-30>  '
        'btype <ice|impact|sticky|normal>'
    )
    _reply(
        'power <0.5-10>  punch <1-10>  ptime <sec>  '
        'pu <triple|ice|impact|sticky|shield|mine|punch|health|curse> [sec]'
    )
    _reply(
        'mega  shield [sec]  curse  spawnpu <type>  kill  '
        'tp <#>  freeze <#>  unfreeze <#>  boom <#>'
    )
    _reply('players  color <name|rainbow|off>  off  codes')


def _cmd_off(st: dict, _cid: int, _args: list[str], act: Any) -> None:
    spaz = _my_spaz(act, _cid)
    if spaz is not None:
        try:
            spaz.node.invincible = False
            spaz.blast_radius = 2.0
            spaz.bomb_type = 'normal'
            spaz.bomb_type_default = 'normal'
            spaz.set_bomb_count(1)
            spaz._punch_power_scale = SpazFactory.get().punch_power_scale
            spaz.node.color = _original_color(spaz)
        except Exception:
            pass
    _CHEATS[_cid] = _new_state()
    _reply('All your cheats are OFF.')


_COMMANDS: dict[str, Any] = {
    'fly': _cmd_fly,
    'speed': _cmd_speed,
    'god': _cmd_god,
    'heal': _cmd_heal,
    'inf': _cmd_inf,
    'bombs': _cmd_bombs,
    'btype': _cmd_btype,
    'power': _cmd_power,
    'punch': _cmd_punch,
    'ptime': _cmd_ptime,
    'pu': _cmd_pu,
    'mega': _cmd_mega,
    'shield': _cmd_shield,
    'curse': _cmd_curse,
    'spawnpu': _cmd_spawnpu,
    'kill': _cmd_kill,
    'tp': _cmd_tp,
    'freeze': _cmd_freeze,
    'unfreeze': _cmd_unfreeze,
    'boom': _cmd_boom,
    'players': _cmd_players,
    'color': _cmd_color,
    'codes': _cmd_codes,
    'help': _cmd_codes,
    'off': _cmd_off,
}


# ---------------------------------------------------------------------------
# Chat hook
# ---------------------------------------------------------------------------


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
    st = _CHEATS.setdefault(client_id, _new_state())
    with act.context:
        handler(st, client_id, parts[1:], act)


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------


def _install() -> None:
    if _INSTALLED[0]:
        return
    _INSTALLED[0] = True
    global _ORIG_FILTER_CHAT  # pylint: disable=global-statement
    _ORIG_FILTER_CHAT = _bshooks.filter_chat_message
    _bshooks.filter_chat_message = _filter_chat_message

    # The native layer caches the hook functions; make it re-read ours.
    bs.reload_hooks()

    babase.apptimer(FLY_TICK, _motion_tick)
    babase.apptimer(0.25, _buffs_tick)

    # The chat system is not up yet during boot; greet a bit later.
    babase.apptimer(
        6.0,
        lambda: _reply(
            f'{MOD_NAME} loaded! Everyone can type "codes" in chat '
            'for the cheat command list.'
        )
    )


# ba_meta export babase.Plugin
class FlyCheatsPlugin(babase.Plugin):
    """Registers the chat hook and effect timers when the app starts."""

    def on_app_running(self) -> None:
        _install()
