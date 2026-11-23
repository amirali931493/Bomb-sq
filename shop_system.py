# Released under the MIT License. See LICENSE file for details.
#
# ShopSystem - a chat-command coin shop for BombSquad 1.8.x (api 9).
#
# ba_meta require api 9
"""Coin shop for BombSquad 1.8.x.

Every kill earns you coins. Spend them in the party chat on powerups
for your next life. Your balance is saved to a json file in the mods
folder, so it survives game restarts.

Chat commands:

    shop        - show the item list and prices
    buy <item>  - buy an item (you must be alive)
    coins       - show your balance
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

MOD_NAME = 'ShopSystem'
DATA_FILE = 'bs_shop_data.json'

# ---------------------------------------------------------------------------
# Tunables (feel free to tweak these numbers)
# ---------------------------------------------------------------------------

COINS_PER_KILL = 5
START_COINS = 20  # welcome bonus for new players
MAX_COINS = 99999
KILL_WINDOW = 5.0  # hit -> death seconds for kill credit

# item name -> (powerup type, price, description)
SHOP_ITEMS = {
    'heal': ('health', 15, 'full health'),
    'shield': ('shield', 30, 'energy shield'),
    'ice': ('ice_bombs', 25, 'ice bombs'),
    'impact': ('impact_bombs', 25, 'impact bombs'),
    'sticky': ('sticky_bombs', 25, 'sticky bombs'),
    'triple': ('triple_bombs', 35, 'triple bombs'),
    'mine': ('land_mines', 30, 'three land mines'),
    'curse': ('curse', 5, '??? (good luck)'),
}

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_SENDING = [False]
_ORIG_FILTER_CHAT: Any = None
_ORIG_SPAZ_HANDLE: Any = None
_INSTALLED = [False]

_COINS: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _reply(text: str) -> None:
    """Chat reply, marked as coming from ShopSystem."""
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


def _pname(player: Any) -> str | None:
    try:
        name = player.getname(full=False, icon=False)
        if name:
            return str(name)
    except Exception:
        pass
    return None


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


def _client_name(act: Any, client_id: int) -> str | None:
    for player in _client_players(act, client_id):
        name = _pname(player)
        if name:
            return name
    return None


def _my_spaz(act: Any, client_id: int) -> Any:
    """First living spaz actor controlled by this client, or None."""
    for player in _client_players(act, client_id):
        actor = getattr(player, 'actor', None)
        if actor is None:
            continue
        if getattr(actor, 'node', None) is None:
            continue
        try:
            if actor._dead:  # pylint: disable=protected-access
                continue
        except Exception:
            pass
        return actor
    return None


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def _data_path() -> str:
    try:
        return os.path.join(bauiv1.app.env.python_directory_user, DATA_FILE)
    except Exception:
        return DATA_FILE


def _load() -> None:
    global _COINS
    _COINS = {}
    try:
        with open(_data_path(), 'r', encoding='utf-8') as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            _COINS = {k: v for k, v in raw.items() if isinstance(v, dict)}
    except Exception:
        _COINS = {}


def _save() -> None:
    try:
        with open(_data_path(), 'w', encoding='utf-8') as f:
            json.dump(_COINS, f)
    except Exception:
        pass


def _account(name: str) -> dict[str, Any]:
    key = name.lower()
    rec = _COINS.get(key)
    if rec is None:
        rec = {'coins': START_COINS, 'name': name}
        _COINS[key] = rec
        _reply(
            f'Welcome {name}! Here is a {START_COINS} coin welcome bonus.'
        )
    rec['name'] = name
    return rec


# ---------------------------------------------------------------------------
# Kill tracking (same mechanism as XPSystem)
# ---------------------------------------------------------------------------


def _hook_spaz() -> None:
    """Wrap Spaz.handlemessage once to pay coins for kills."""
    global _ORIG_SPAZ_HANDLE
    if getattr(Spaz, '_shop_hook_installed', False):
        return
    _ORIG_SPAZ_HANDLE = Spaz.handlemessage

    def _patched(self: Any, msg: Any) -> Any:
        if isinstance(msg, bs.HitMessage):
            try:
                src = msg.source_player
                if src is not None:
                    self._shop_attacker = src
                    self._shop_attack_time = bs.time()
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
    Spaz._shop_hook_installed = True  # type: ignore[attr-defined]


def _on_death(spaz: Any) -> None:
    victim_name = None
    try:
        player = spaz.getplayer(bs.Player)
        if player:
            victim_name = _pname(player)
    except Exception:
        victim_name = None

    attacker = getattr(spaz, '_shop_attacker', None)
    attack_time = getattr(spaz, '_shop_attack_time', None)
    if attacker is None or attack_time is None:
        return
    try:
        fresh = (bs.time() - float(attack_time)) <= KILL_WINDOW
    except Exception:
        fresh = False
    if not fresh:
        return
    try:
        killer_name = _pname(attacker)
    except Exception:
        killer_name = None
    if not killer_name or (
        victim_name and killer_name.lower() == victim_name.lower()
    ):
        return
    rec = _account(killer_name)
    rec['coins'] = min(MAX_COINS, rec.get('coins', 0) + COINS_PER_KILL)
    _save()


# ---------------------------------------------------------------------------
# Chat commands
# ---------------------------------------------------------------------------


def _cmd_shop(_client_id: int, _args: list[str], _act: Any) -> None:
    _reply(f'--- {MOD_NAME} ({COINS_PER_KILL} coins per kill) ---')
    line1 = '  '.join(
        f'{n}:{SHOP_ITEMS[n][1]}c' for n in ('heal', 'shield', 'ice', 'impact')
    )
    line2 = '  '.join(
        f'{n}:{SHOP_ITEMS[n][1]}c' for n in ('sticky', 'triple', 'mine', 'curse')
    )
    _reply(line1)
    _reply(line2)
    _reply('Buy with: buy <item>  (you must be alive)')


def _cmd_coins(client_id: int, _args: list[str], act: Any) -> None:
    name = _client_name(act, client_id)
    if name is None:
        _reply('Join a game first so I know who you are.')
        return
    rec = _account(name)
    _reply(f'{name}: {rec.get("coins", 0)} coins. Type "shop" for items.')


def _cmd_buy(client_id: int, args: list[str], act: Any) -> None:
    if not args:
        _reply('Usage: buy <' + '/'.join(SHOP_ITEMS) + '>')
        return
    name = _client_name(act, client_id)
    if name is None:
        _reply('Join a game first so I know who you are.')
        return
    item = args[0].lower()
    entry = SHOP_ITEMS.get(item)
    if entry is None:
        _reply('Unknown item. Type "shop" to see the list.')
        return
    putype, price, desc = entry
    spaz = _my_spaz(act, client_id)
    if spaz is None:
        _reply('You must be alive in a game to buy something.')
        return
    rec = _account(name)
    balance = rec.get('coins', 0)
    if balance < price:
        _reply(f'Not enough coins ({balance}c). {item} costs {price}c.')
        return
    rec['coins'] = balance - price
    _save()
    try:
        spaz.handlemessage(bs.PowerupMessage(putype))
    except Exception:
        rec['coins'] = balance
        _save()
        _reply('Purchase failed - try again.')
        return
    if putype == 'curse':
        _reply(f'{name} bought CURSE for {price}c... hehe. Good luck!')
    else:
        _reply(
            f'{name} bought {item.upper()} ({desc})! '
            f'Balance: {rec["coins"]}c'
        )


def _cmd_shophelp(_client_id: int, _args: list[str], _act: Any) -> None:
    _reply(f'--- {MOD_NAME} ---')
    _reply('shop = items | buy <item> = purchase | coins = your balance')
    _reply(f'Every kill earns {COINS_PER_KILL} coins. New players start '
           f'with {START_COINS}.')


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
    'shop': _cmd_shop,
    'store': _cmd_shop,
    'buy': _cmd_buy,
    'coins': _cmd_coins,
    'bal': _cmd_coins,
    'balance': _cmd_coins,
    'shophelp': _cmd_shophelp,
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
        6.5,
        lambda: _reply(
            'ShopSystem loaded! Kills earn coins - type "shop" in chat.'
        ),
    )


# ba_meta export babase.Plugin
class ShopSystemPlugin(babase.Plugin):
    """Registers the coin shop and chat hook when the app starts."""

    def on_app_running(self) -> None:
        _install()
