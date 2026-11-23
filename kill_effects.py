# Released under the MIT License. See LICENSE file for details.
#
# KillEffects - a chat-command death-effects mod for BombSquad 1.8.x (api 9).
#
# ba_meta require api 9
"""Death effects for BombSquad 1.8.x.

Pick a special effect that plays whenever YOU die - so everyone knows
you went out in style:

    explosion - a triple chain blast at your body
    rainbow   - a colorful rainbow flash show
    lightning - a thunder strike from the sky
    fireworks - a six-shot fireworks show above your body

Chat commands:

    killfx                       - show your current effect
    killfx <explosion/rainbow/lightning/fireworks/off> - pick one
"""

from __future__ import annotations

import random
from typing import Any

import babase
import bascenev1 as bs
import bascenev1._hooks as _bshooks

from bascenev1lib.actor.bomb import Blast
from bascenev1lib.actor.powerupbox import PowerupBoxFactory
from bascenev1lib.actor.spaz import Spaz
from bascenev1lib.actor.spazfactory import SpazFactory

MOD_NAME = 'KillEffects'

FX_TYPES = ('explosion', 'rainbow', 'lightning', 'fireworks')

RAINBOW_COLORS = [
    (1.0, 0.25, 0.25),
    (1.0, 0.65, 0.1),
    (1.0, 0.9, 0.2),
    (0.3, 1.0, 0.3),
    (0.3, 0.5, 1.0),
    (0.7, 0.3, 1.0),
    (1.0, 0.4, 0.8),
]

FIREWORK_COLORS = [
    (1.0, 0.3, 0.3),
    (1.0, 0.8, 0.2),
    (0.3, 1.0, 0.4),
    (0.3, 0.6, 1.0),
    (0.8, 0.4, 1.0),
    (1.0, 0.4, 0.8),
]

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_SENDING = [False]
_ORIG_FILTER_CHAT: Any = None
_ORIG_SPAZ_HANDLE: Any = None
_INSTALLED = [False]

_FX: dict[int, str] = {}  # client_id -> effect name


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _reply(text: str) -> None:
    """Chat reply, marked as coming from KillEffects."""
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
        return bs.get_foreground_host_activity()
    except Exception:
        return None


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
# Effect building blocks (all vanilla-style node effects, all harmless
# unless the effect itself spawns a real Blast)
# ---------------------------------------------------------------------------


def _light_flash(
    pos: tuple[float, float, float],
    color: tuple[float, float, float],
    radius: float,
    intensity: float,
    fade: float = 0.4,
) -> None:
    """A soft fading light - the vanilla 'shatter' effect pattern."""
    try:
        light = bs.newnode(
            'light',
            attrs={
                'position': pos,
                'radius': radius,
                'intensity': intensity,
                'height_attenuated': False,
                'color': color,
            },
        )
        bs.animate(light, 'intensity', {0.0: intensity, fade: 0.0})
        bs.timer(fade + 0.05, light.delete)
    except Exception:
        pass


def _flash_node(
    pos: tuple[float, float, float],
    color: tuple[float, float, float],
    size: float,
) -> None:
    """A quick camera-facing flash sprite (like punch hits use)."""
    try:
        flash = bs.newnode(
            'flash', attrs={'position': pos, 'size': size, 'color': color}
        )
        bs.timer(0.08, flash.delete)
    except Exception:
        pass


def _sparks(pos: tuple[float, float, float], count: int, spread: float) -> None:
    try:
        bs.emitfx(
            position=pos,
            count=count,
            scale=0.6,
            spread=spread,
            chunk_type='spark',
        )
    except Exception:
        pass


def _powerup_sound(pos: tuple[float, float, float]) -> None:
    try:
        bs.playsound(PowerupBoxFactory.get().powerup_sound, 1.0, pos)
    except Exception:
        pass


def _zap_sound(pos: tuple[float, float, float]) -> None:
    try:
        bs.playsound(bs.getsound('sparks'), 1.0, pos)
    except Exception:
        try:
            bs.playsound(SpazFactory.get().shield_down_sound, 1.0, pos)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# The four effects
# ---------------------------------------------------------------------------


def _fx_explosion(pos: tuple[float, float, float]) -> None:
    """A dramatic triple chain blast where you died (yes, it hurts)."""
    _light_flash(pos, (1.0, 0.6, 0.2), 0.8, 2.5)
    _flash_node(pos, (1.0, 0.8, 0.4), 0.5)
    try:
        Blast(position=(pos[0], pos[1] + 0.4, pos[2]), blast_radius=2.3)
    except Exception:
        pass


def _fx_explosion_echo1(pos: tuple[float, float, float]) -> None:
    try:
        Blast(
            position=(pos[0] + 0.8, pos[1] + 0.6, pos[2] - 0.5),
            blast_radius=1.4,
        )
    except Exception:
        pass


def _fx_explosion_echo2(pos: tuple[float, float, float]) -> None:
    try:
        Blast(
            position=(pos[0] - 0.7, pos[1] + 0.9, pos[2] + 0.6),
            blast_radius=1.4,
        )
    except Exception:
        pass


def _fx_rainbow_step(pos: tuple[float, float, float], hue: float) -> None:
    _light_flash(pos, _hsv_to_rgb(hue), 0.5, 2.0, fade=0.3)


def _fx_lightning(pos: tuple[float, float, float]) -> None:
    """A thunder strike: sky flash, white zap and sparks."""
    sky = (pos[0], pos[1] + 4.0, pos[2])
    _light_flash(sky, (0.85, 0.9, 1.0), 2.5, 3.0, fade=0.25)
    _light_flash(pos, (1.0, 1.0, 1.0), 0.7, 2.5, fade=0.2)
    _flash_node(pos, (0.9, 0.95, 1.0), 1.1)
    _sparks(pos, 30, 0.9)


def _fx_lightning_echo(pos: tuple[float, float, float]) -> None:
    _flash_node((pos[0], pos[1] + 0.3, pos[2]), (1.0, 1.0, 1.0), 0.7)
    _sparks(pos, 15, 0.6)


def _fx_firework_step(pos: tuple[float, float, float], idx: int) -> None:
    color = FIREWORK_COLORS[idx % len(FIREWORK_COLORS)]
    spot = (
        pos[0] + random.uniform(-1.6, 1.6),
        pos[1] + 2.6 + random.uniform(0.0, 1.2),
        pos[2] + random.uniform(-1.6, 1.6),
    )
    _light_flash(spot, color, 0.5, 2.5, fade=0.35)
    _flash_node(spot, color, 0.35)
    _sparks(spot, 15, 0.6)
    if idx == 5:  # grand finale pop
        try:
            Blast(position=spot, blast_radius=1.2)
        except Exception:
            pass


def _steps_for(fx: str, pos: tuple[float, float, float]) -> list[Any]:
    if fx == 'explosion':
        return [
            (0.0, lambda: _fx_explosion(pos)),
            (0.15, lambda: _fx_explosion_echo1(pos)),
            (0.3, lambda: _fx_explosion_echo2(pos)),
        ]
    if fx == 'rainbow':
        steps: list[Any] = [(0.0, lambda: _powerup_sound(pos))]
        for i in range(7):
            hue = i / 7.0
            steps.append(
                (i * 0.08, lambda h=hue: _fx_rainbow_step(pos, h))
            )
        return steps
    if fx == 'lightning':
        return [
            (0.0, lambda: _zap_sound(pos)),
            (0.0, lambda: _fx_lightning(pos)),
            (0.15, lambda: _fx_lightning_echo(pos)),
        ]
    if fx == 'fireworks':
        return [
            (i * 0.14, lambda k=i: _fx_firework_step(pos, k)) for i in range(6)
        ]
    return []


def _safe_run(act: Any, fn: Any) -> None:
    try:
        with act.context:
            fn()
    except Exception:
        pass


def _play(act: Any, fx: str, pos: tuple[float, float, float]) -> None:
    for delay, fn in _steps_for(fx, pos):
        babase.apptimer(delay, lambda f=fn, a=act: _safe_run(a, f))


# ---------------------------------------------------------------------------
# Death hook
# ---------------------------------------------------------------------------


def _hook_spaz() -> None:
    """Wrap Spaz.handlemessage once to play effects on death."""
    global _ORIG_SPAZ_HANDLE
    if getattr(Spaz, '_kfx_hook_installed', False):
        return
    _ORIG_SPAZ_HANDLE = Spaz.handlemessage

    def _patched(self: Any, msg: Any) -> Any:
        if isinstance(msg, bs.DieMessage):
            try:
                if not getattr(self, '_dead', False):
                    pos = None
                    try:
                        pos = (
                            float(self.node.position[0]),
                            float(self.node.position[1]),
                            float(self.node.position[2]),
                        )
                    except Exception:
                        pos = None
                    _on_death(self, pos)
            except Exception:
                pass
        return _ORIG_SPAZ_HANDLE(self, msg)

    Spaz.handlemessage = _patched
    Spaz._kfx_hook_installed = True  # type: ignore[attr-defined]


def _find_client_id(act: Any, spaz: Any) -> int | None:
    for player in act.players:
        if getattr(player, 'actor', None) is spaz:
            try:
                sessplayer = player.sessionplayer
                if sessplayer is not None and bool(sessplayer):
                    return sessplayer.inputdevice.client_id
            except Exception:
                return None
    return None


def _on_death(spaz: Any, pos: Any) -> None:
    if pos is None:
        return
    act = _host_activity()
    if act is None:
        return
    client_id = _find_client_id(act, spaz)
    if client_id is None:
        return
    fx = _FX.get(client_id)
    if fx in FX_TYPES:
        _play(act, fx, pos)


# ---------------------------------------------------------------------------
# Chat commands
# ---------------------------------------------------------------------------


def _cmd_killfx(client_id: int, args: list[str], _act: Any) -> None:
    if not args:
        current = _FX.get(client_id, 'off')
        _reply(
            f'KillFX: {current} | pick one: '
            'killfx <explosion/rainbow/lightning/fireworks/off>'
        )
        return
    fx = args[0].lower()
    if fx in ('off', 'none', 'disable', 'normal'):
        _FX[client_id] = 'off'
        _reply('KillFX OFF - you die like a boring person again.')
        return
    if fx in FX_TYPES:
        _FX[client_id] = fx
        _reply(f'KillFX set to {fx.upper()}! You will go out in style...')
        return
    _reply(
        'Unknown effect. Choices: explosion / rainbow / lightning / '
        'fireworks / off'
    )


# ---------------------------------------------------------------------------
# Hooks
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
    with act.context:
        try:
            handler(client_id, parts[1:], act)
        except Exception:
            pass


_COMMANDS: dict[str, Any] = {
    'killfx': _cmd_killfx,
    'kfx': _cmd_killfx,
}


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------


def _install() -> None:
    if _INSTALLED[0]:
        return
    _INSTALLED[0] = True
    _hook_spaz()

    global _ORIG_FILTER_CHAT
    _ORIG_FILTER_CHAT = _bshooks.filter_chat_message
    _bshooks.filter_chat_message = _filter_chat_message
    # The native layer caches the hook functions; make it re-read ours.
    bs.reload_hooks()

    # The chat system is not up yet during boot; greet a bit later.
    babase.apptimer(
        7.0,
        lambda: _reply(
            'KillEffects loaded! Pick a death effect - type "killfx" '
            'in chat.'
        ),
    )


# ba_meta export babase.Plugin
class KillEffectsPlugin(babase.Plugin):
    """Registers the death-effect hook and chat command."""

    def on_app_running(self) -> None:
        _install()
