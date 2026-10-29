"""The Open with menu: the rows that open a world, or one element of it, in a tool, in order.

Each row carries the word it says when it cannot open now. Pure: a menu draws these rows and decides no word
of its own, and a game, the npm SDK's ``openersFor`` and a test read the same rows. The rows come from the
OnlyWorlds tools list (``github.com/OnlyWorlds/tools``, ``tools.json`` format 1, its README's "Open with"),
baked into the package as ``TOOLS`` (``_tools.py``). The shared fixture, ``tests/fixtures/openers.fixture.json``,
is this module's own test, and ``openersFor`` answers every case the same way.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Literal, NoReturn, TypedDict

from .address import _ADDRESS_KEYS, AddressReading, element_address

__all__ = ["Opener", "Tool", "ToolOpen", "openers_for"]


class ToolOpen(TypedDict):
    """A tool's ``open`` in the tools list: its link templates and what they need first. ``world`` holds
    ``{world}`` (the world's id); ``element`` holds ``{id}`` and, if it needs them, ``{world}`` and ``{type}``
    (the type word); either None without one. ``needs`` is what the person must have first: ``account``
    (signed in to the tool), ``device`` (the world already in the tool on this device), or None for nothing,
    the one kind of row a public page offers."""

    world: str | None
    element: str | None
    needs: Literal["account", "device"] | None


class Tool(TypedDict):
    """The keys of one tools list row that ``openers_for`` reads; a row straight from ``tools.json`` carries more,
    and they are ignored. ``client`` is the tool's client name (``X-OW-Client``), which a surface names itself
    by; ``listed`` rows are offered, ``built`` and ``delisted`` rows never are; ``open`` None is never offered."""

    id: str
    name: str
    url: str
    client: str | None
    rung: Literal["built", "listed", "delisted"]
    open: ToolOpen | None


class Opener(TypedDict):
    """One row of the menu: ``id`` (``onlyworlds`` for the site's own row, else the tool's id in the list),
    ``name`` (``onlyworlds.com``, or the tool's name), ``href``, and ``state``, the row's word, None when it opens
    now and says nothing."""

    id: str
    name: str
    href: str
    state: str | None


_SURFACE_KEYS = ("tool", "audience", "signed_in", "browser", "phone")
_NEEDS = ("account", "device", None)
_PLACEHOLDER = re.compile(r"\{(world|type|id)\}")


def _fail(what: str) -> NoReturn:
    raise TypeError(f"openers_for: {what}")


def _template(row: str, key: str, value: object) -> str | None:
    """A template string or None."""
    if value is None or isinstance(value, str):
        return value
    _fail(f"tool {row}: open.{key} is a link template or None")


def openers_for(
    tools: Sequence[Mapping[str, Any]],
    kind: str,
    address: Mapping[str, Any] | AddressReading,
    surface: Mapping[str, Any],
) -> list[Opener]:
    """The rows of the Open with menu for a world (``kind="world"``) or one element of it (``"element"``), in order.

    First the site's own row (id ``onlyworlds``, name ``onlyworlds.com``, the world's or the element's page on
    www.onlyworlds.com, never a word, for every audience), then one row per ``tools`` row, in the list's order,
    that is ``listed`` and has a door for this kind. ``tools`` is the tools list's rows, ``TOOLS`` or the list as
    served; ``address`` is an ``AddressReading`` from ``parse_ow_link`` or what ``element_address`` takes, with the
    world's id. A lens and a moment on it ride on no href.

    A row with ``open`` None, or with no door for this kind, is not there. On an element, a tool with only a world
    door is a row to its world door that says "Opens the world". For the ``public`` audience only rows whose
    ``open.needs`` is None are there: a row that needs anything does not exist for the public.

    ``surface`` is a mapping of what the surface knows, and nothing is guessed: ``audience`` (``member``, a seat in
    the world, a guest included, or ``public``, the signed-out reader; required), ``signed_in`` (True, False, or
    None or absent when the surface cannot know), ``browser`` (False in a desktop app, which cannot see the
    browser's sign-in; default True), ``phone`` (default False) and ``tool`` (the client name of the surface's own
    tool, when it is a listed tool).

    Each row's ``state``, the first that holds: "You are here" for the surface's own tool (its ``client`` is
    ``tool``); then what ``needs`` asks of this surface: ``account`` outside a browser "Opens in your browser", in a
    browser signed out "Sign in to <name> first" (none when ``signed_in`` is None: a word shows only when the
    surface knows it is true), ``device`` on a phone "Needs the world on this phone"; then "Opens the world" (a
    world door on an element: a sign-in the row needs is the more urgent word); else None.

    Raises ``AddressError`` for an address without a world (``no_world``) or with a slug or anything else for its
    id (``bad_world``), and a type, id or pairing ``element_address`` refuses. A ``TypeError`` names the rest: a
    ``kind`` that is neither, an element's openers asked of an address with no element, an unknown key on the
    address or the surface, a missing or unknown ``audience``, a surface value of the wrong type, a tools row that
    is not one (a ``needs`` outside the list's format included). The npm SDK's ``openersFor`` gives the same rows.
    """
    if isinstance(tools, str | bytes) or not isinstance(tools, Sequence):
        _fail("tools is the tools list's rows, a sequence")
    if kind not in ("world", "element"):
        _fail(f"kind is 'world' or 'element'; got {kind!r}")
    a: Mapping[str, Any]
    if isinstance(address, AddressReading):
        a = {k: getattr(address, k) for k in _ADDRESS_KEYS}
    elif isinstance(address, Mapping):
        a = address
    else:
        _fail("the address is a mapping (form, world, type, id), as parse_ow_link reads it")
    for key in a:
        if key not in _ADDRESS_KEYS:
            _fail(f"unknown key {key!r} in the address. The keys are {', '.join(_ADDRESS_KEYS)}.")
    # The address's checks are the writer's, so a slug, a missing world and a bad type or id refuse as there.
    page = element_address({"form": "human", "world": a.get("world"), "type": a.get("type"), "id": a.get("id")})
    world = str(a["world"]).lower()
    has_element = a.get("type") is not None
    if kind == "element" and not has_element:
        _fail("an element's openers need an address with its type and id")
    values = {
        "world": world,
        "type": str(a["type"]) if has_element else "",
        "id": str(a["id"]).lower() if has_element else "",
    }

    if not isinstance(surface, Mapping):
        _fail("the surface is a mapping (audience, ...)")
    for key in surface:
        if key not in _SURFACE_KEYS:
            _fail(f"unknown key {key!r} in the surface. The keys are {', '.join(_SURFACE_KEYS)}.")
    tool = surface.get("tool")
    audience = surface.get("audience")
    signed_in = surface.get("signed_in")
    browser = surface.get("browser", True)
    phone = surface.get("phone", False)
    if audience not in ("member", "public"):
        _fail(f"surface audience is 'member' or 'public'; got {audience!r}")
    if tool is not None and not isinstance(tool, str):
        _fail("surface tool is a client name or None")
    if signed_in is not None and not isinstance(signed_in, bool):
        _fail("surface signed_in is True, False or None")
    if not isinstance(browser, bool):
        _fail("surface browser is a boolean")
    if not isinstance(phone, bool):
        _fail("surface phone is a boolean")

    def fill(template: str) -> str:
        return _PLACEHOLDER.sub(lambda m: values[m.group(1)], template)

    site = page if kind == "element" else element_address({"form": "human", "world": world})
    rows: list[Opener] = [{"id": "onlyworlds", "name": "onlyworlds.com", "href": site, "state": None}]
    for r in tools:
        if not isinstance(r, Mapping) or not isinstance(r.get("id"), str) or not isinstance(r.get("name"), str):
            _fail("each tools row is a mapping with an id and a name")
        rid, name = r["id"], r["name"]
        o = r.get("open")
        if o is None:
            continue
        if not isinstance(o, Mapping):
            _fail(f"tool {rid}: open is a mapping or None")
        world_door = _template(rid, "world", o.get("world"))
        element_door = _template(rid, "element", o.get("element"))
        needs = o.get("needs")
        if needs not in _NEEDS:
            _fail(f"tool {rid}: open.needs is 'account', 'device' or None; got {needs!r}")
        if r.get("rung") != "listed":
            continue
        if audience == "public" and needs is not None:
            continue
        template = world_door if kind == "world" or element_door is None else element_door
        if template is None:
            continue
        # The first that holds. A word the row needs (it cannot open now) comes before "Opens the world" (it
        # opens, somewhere else), so a world door alone that needs a sign-in says the sign-in.
        state: str | None = None
        if tool is not None and r.get("client") == tool:
            state = "You are here"
        elif needs == "account" and not browser:
            state = "Opens in your browser"
        elif needs == "account" and signed_in is False:
            state = f"Sign in to {name} first"
        elif needs == "device" and phone:
            state = "Needs the world on this phone"
        elif kind == "element" and element_door is None:
            state = "Opens the world"
        rows.append({"id": rid, "name": name, "href": fill(template), "state": state})
    return rows
