"""The calendar profile (schema-dist ``profiles/calendar.md``): read a world's ``atlas_calendar``, and read
its integer steps aloud as that calendar's dates, and back.

A calendar names a world's time line; it never changes a date. Every date field stays a plain integer in
the world's ``time_basic_unit``, and this module only says how to read that integer: ``format_step`` and
``breakdown_step`` turn a step into words and parts, ``parse_date`` turns written words back into a step.
``read_calendar_value`` is the one reader of the field: it refuses what the profile refuses (None: show
bare numbers, never an error), and every other function here takes what it accepts.

The npm SDK's calendar kernel (``@onlyworlds/sdk``, ``src/calendar/``) is the reference and this is a
port of it: the same answers for the same input, the profile's fixture replayed by ``tests/test_calendar.py``.
Where Python and JavaScript read the same thing differently, this module reads it as JavaScript does:

- numbers are JavaScript's: the arithmetic is IEEE double arithmetic in the reference's order (floored
  division and modulo as ``Math.floor(a / b)`` and ``((a % b) + b) % b``, a sum added left to right, not
  ``sum()``), and an integer past the double range reads as infinity, as ``JSON.parse`` reads it. A whole
  number comes back as ``int``; only a step that is not a whole finite number (``inf``, a fraction, a
  bare number of more than 308 digits in ``parse_date``) gives back a ``float`` where an ``int`` is typed;
- "whole number" is ``Number.isInteger`` (``2.0`` is whole, ``True`` is not a number) and the profile's
  whole numbers are ``Number.isSafeInteger`` (at most 2**53 - 1 in size);
- trimming and ``\\s`` are JavaScript's white space (U+FEFF included; U+001C to U+001F and U+0085 not),
  ``\\d`` is ASCII 0 to 9, ``$`` is the end of the text, and a string's length counts UTF-16 code units;
- a JSON string is read as ``JSON.parse`` reads it (no ``NaN`` or ``Infinity``);
- a value that is not text where the reference calls a string method (a ``format`` that is a number, an
  era ``abbrev`` that is not a string when ``parse_date`` reaches it) raises ``TypeError`` as it throws.

An options object becomes keyword arguments (an unknown one is Python's own ``TypeError``), JavaScript's
``undefined`` for a calendar never chosen is leaving ``active_id`` out, and an unexported helper the
reference takes as an optional argument (``weekdayForStep``'s ``pre``) is internal.

========================== ===========================
Python                     TypeScript (``@onlyworlds/sdk``)
========================== ===========================
``CALENDAR_FIELD``          ``CALENDAR_FIELD``
``CALENDAR_SUPERTYPE``      ``CALENDAR_SUPERTYPE``
``read_calendar_value``     ``readCalendarValue``
``world_calendars``         ``worldCalendars``
``resolve_calendar``        ``resolveCalendar``
``read_calendar_config``    ``readCalendarConfig``
``validate_calendar_config`` ``validateCalendarConfig``
``floor_div``               ``floorDiv``
``floor_mod``               ``floorMod``
``is_leap_year``            ``isLeapYear``
``intercalary_in_year``     ``intercalaryInYear``
``year_start_step``         ``yearStartStep``
``year_length``             ``yearLength``
``absolute_year``           ``absoluteYear``
``resolve_era_domains``     ``resolveEraDomains``
``era_for_step``            ``eraForStep``
``display_year``            ``displayYear``
``abs_year_for_era_year``   ``absYearForEraYear``
``weekday_for_step``        ``weekdayForStep``
``breakdown_step``          ``breakdownStep``
``format_step``             ``formatStep``
``format_year_label``       ``formatYearLabel``
``format_mid_label``        ``formatMidLabel``
``format_duration``         ``formatDuration``
``approx_year_length``      ``approxYearLength``
``month_start_steps``       ``monthStartSteps``
``parse_date``              ``parseDate``
``is_parse_error``          ``isParseError``
``CalendarConfig``          ``CalendarConfig``
``CalendarBundles``         (``CalendarConfig['bundles']``)
``CalendarYear``            (``CalendarConfig['bundles']['year']``)
``CalendarMonths``          ``CalendarMonths``
``CalendarWeek``            ``CalendarWeek``
``CalendarIntercalary``     ``CalendarIntercalary``
``CalendarEra``             ``CalendarEra``
``StepBreakdown``           ``StepBreakdown`` (snake_case fields)
``EraDomain``               ``EraDomain``
``MonthStart``              (``monthStartSteps``' row)
``ParseResult``             ``ParseResult``
``ParseError``              ``ParseError`` (a result, not an exception)
``WorldCalendar``           ``WorldCalendar``
========================== ===========================
"""

from __future__ import annotations

import json
import math
import re
import warnings
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from functools import cmp_to_key
from typing import Any, Final, Literal, NamedTuple, Required, TypedDict, cast

#: The supertype a calendar Construct carries by the profile's convention: display only, never detection.
CALENDAR_SUPERTYPE: Final = "calendar"

#: The calendar profile's field. A calendar is any element carrying it; read it only through
#: ``read_calendar_value``.
CALENDAR_FIELD: Final = "atlas_calendar"


# ---- The value's shape (as JSON gives it; null anywhere reads as absent) ----


class CalendarEra(TypedDict, total=False):
    name: Required[str]
    abbrev: str | None
    #: An up era's first step (inclusive); a down era's pivot (exclusive upper bound).
    start: Required[int]
    #: An up era's end (exclusive), by default the next up era's start; a down era's lower bound (inclusive).
    end: int | None
    #: True (default): years count from the era. False: a label; ``{year}`` shows the absolute year index.
    restart: bool | None
    #: A restarting era's first year number: 0 or 1 (default 1).
    year_base: Literal[0, 1] | None
    #: ``up`` (default) or ``down`` (counts toward the pivot, like BC).
    direction: Literal["up", "down"] | None
    #: Shown for old dates, never offered for new ones.
    closed: bool | None


class CalendarMonths(TypedDict):
    names: list[str]
    lengths: list[int]


class CalendarWeek(TypedDict, total=False):
    length: Required[int]
    names: Required[list[str]]
    #: ``free`` (default): runs across months, step 0 is ``names[0]``. ``nested``: restarts each month.
    mode: Literal["free", "nested"] | None


class CalendarYear(TypedDict):
    steps: int


class CalendarBundles(TypedDict, total=False):
    #: A year's length, only for a calendar without months.
    year: CalendarYear | None
    months: CalendarMonths | None
    week: CalendarWeek | None


#: A day outside the months. ``after_month``: 0 = before month 1, k = after month k. ``every_years``: present
#: only in the years the leap rule selects. ``except`` (version 2): divisors that flip the rule in order, each
#: a larger multiple of the one before. ``offset`` (version 2): added to the year index before the rule reads
#: it (1 for a calendar with no year 0). ``in_week``: counts in the free-running week (default true).
CalendarIntercalary = TypedDict(
    "CalendarIntercalary",
    {
        "name": Required[str],
        "after_month": Required[int],
        "every_years": int | None,
        "except": list[int] | None,
        "offset": int | None,
        "in_week": bool | None,
    },
    total=False,
)


class CalendarConfig(TypedDict, total=False):
    version: Required[int]
    grain: Required[str]
    step_name: str | None
    eras: list[CalendarEra] | None
    bundles: CalendarBundles | None
    intercalary: list[CalendarIntercalary] | None
    format: str | None
    format_intercalary: str | None


@dataclass(frozen=True)
class StepBreakdown:
    """A step taken apart; a part is None where the calendar has no such structure."""

    step: int
    #: Absolute year index, zero-based from step 0.
    abs_year: int
    #: The era's display year (its restart arithmetic applied), or ``abs_year`` with no era or ``restart`` false.
    year: int
    #: The era object from the config, or None.
    era: Mapping[str, Any] | None
    #: 1-based month, None on a day outside the months or with no months.
    month: int | None
    month_name: str | None
    #: 1-based day within the month.
    day: int | None
    #: The day outside the months' name, when the step is one.
    intercalary: str | None
    weekday: str | None


@dataclass(frozen=True)
class EraDomain:
    era: Mapping[str, Any]
    #: Inclusive; ``-inf`` for a down era with no end.
    lo: float
    #: Exclusive; ``inf`` for an up era with no end and no later up era.
    hi: float


class MonthStart(TypedDict):
    month: int
    name: str
    step: int


class ParseResult(TypedDict):
    step: int


class ParseError(TypedDict):
    """``parse_date``'s refusal, with its reason: a result, not an exception."""

    error: str


@dataclass(frozen=True)
class WorldCalendar:
    #: The calendar element's id.
    id: str
    #: The element's name, or ``(unnamed calendar)``.
    name: str
    config: CalendarConfig


# ---- JavaScript's reading of a JSON value ----


class _Undefined:
    """JavaScript's ``undefined``: a key that is not there (None is ``null``)."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "undefined"


_UNDEF: Final = _Undefined()

#: JavaScript's white space for ``trim()`` and ``\s``: WhiteSpace and LineTerminator. Python's
#: ``str.strip()`` and ``re``'s ``\s`` also take U+001C to U+001F and U+0085, and leave U+FEFF.
_JS_SPACE: Final = "".join(
    map(chr, (0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x20, 0xA0, 0x1680, *range(0x2000, 0x200B), 0x2028, 0x2029))
) + "".join(map(chr, (0x202F, 0x205F, 0x3000, 0xFEFF)))
_S: Final = "[" + re.escape(_JS_SPACE) + "]"
_MIDDOT: Final = chr(0xB7)
_SEP: Final = "[" + re.escape(_JS_SPACE) + ",;" + _MIDDOT + "]"


def _js_trim(s: str) -> str:
    return s.strip(_JS_SPACE)


def _utf16_len(s: str) -> int:
    return len(s.encode("utf-16-le", "surrogatepass")) // 2


def _nullish(v: object) -> bool:
    return v is None or v is _UNDEF


def _none(v: Any) -> Any:
    return None if v is _UNDEF else v


def _is_num(v: object) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool)


def _num(v: float) -> float:
    """A Python number as a JavaScript number: an int past the double range is infinity."""
    if isinstance(v, float):
        return v
    try:
        return float(v)
    except OverflowError:
        return math.inf if v > 0 else -math.inf


def _is_integer(v: object) -> bool:
    """``Number.isInteger``: a number, finite and whole (``True`` is not a number)."""
    return _is_num(v) and _num(cast(float, v)).is_integer()


def _is_safe_integer(v: object) -> bool:
    """``Number.isSafeInteger``."""
    return _is_integer(v) and abs(_num(cast(float, v))) <= 2**53 - 1


def _is_positive_int(v: object) -> bool:
    return _is_safe_integer(v) and _num(cast(float, v)) >= 1


def _truthy(v: object) -> bool:
    """JavaScript's truthiness: an empty list or object is true, 0, NaN and "" are false."""
    if v is None or v is _UNDEF or v is False:
        return False
    if v is True:
        return True
    if _is_num(v):
        f = _num(cast(float, v))
        return not (f == 0 or f != f)
    if isinstance(v, str):
        return v != ""
    return True


def _prop(obj: object, key: str) -> Any:
    """``obj?.key`` on a JSON value: an object's key, a list's or string's ``length`` (UTF-16 code units
    for a string), else undefined."""
    if isinstance(obj, Mapping):
        return obj.get(key, _UNDEF)
    if key == "length":
        if isinstance(obj, str):
            return _utf16_len(obj)
        if isinstance(obj, list):
            return len(obj)
    return _UNDEF


def _get(obj: object, key: str) -> Any:
    """``obj.key``: a TypeError on null or undefined, as JavaScript's."""
    if _nullish(obj):
        raise TypeError(f"Cannot read properties of {obj!r} (reading '{key}')")
    return _prop(obj, key)


def _bundle(cfg: object, key: str) -> Any:
    return _prop(_prop(cfg, "bundles"), key)


def _items(v: object) -> list[Any]:
    """``for (const x of v)``: a list's items, a string's characters; anything else is not iterable."""
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        return list(v)
    raise TypeError(f"{v!r} is not iterable")


def _list_or_empty(v: object) -> list[Any]:
    """``v ?? []`` where the reader has made ``v`` a list (anything else has no ``.filter`` there)."""
    if _nullish(v):
        return []
    if not isinstance(v, list):
        raise TypeError(f"{v!r} is not a list")
    return v


def _js_num_str(x: float) -> str:
    """``String(x)`` for a number (ECMAScript Number::toString, radix 10)."""
    if x != x:
        return "NaN"
    if x == 0:
        return "0"
    if math.isinf(x):
        return "Infinity" if x > 0 else "-Infinity"
    if x < 0:
        return "-" + _js_num_str(-x)
    _, digit_tuple, exp = Decimal(repr(x)).normalize().as_tuple()
    digits = "".join(map(str, digit_tuple))
    k = len(digits)
    n = cast(int, exp) + k
    if k <= n <= 21:
        return digits + "0" * (n - k)
    if 0 < n <= 21:
        return digits[:n] + "." + digits[n:]
    if -6 < n <= 0:
        return "0." + "0" * (-n) + digits
    e = n - 1
    mantissa = digits if k == 1 else digits[0] + "." + digits[1:]
    return f"{mantissa}e{'+' if e >= 0 else '-'}{abs(e)}"


def _js_string(v: object) -> str:
    """``String(v)`` for a JSON value."""
    if v is _UNDEF:
        return "undefined"
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if _is_num(v):
        return _js_num_str(_num(cast(float, v)))
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return ",".join("" if _nullish(x) else _js_string(x) for x in v)
    return "[object Object]"


_HEX = re.compile(r"0[xX][0-9a-fA-F]+")
_OCT = re.compile(r"0[oO][0-7]+")
_BIN = re.compile(r"0[bB][01]+")
_DECIMAL = re.compile(r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")


def _to_number(v: object) -> float:
    """``Number(v)`` for a JSON value (the coercion of ``-``, ``<`` and a sort comparator)."""
    if v is _UNDEF:
        return math.nan
    if v is None or v is False:
        return 0.0
    if v is True:
        return 1.0
    if _is_num(v):
        return _num(cast(float, v))
    if isinstance(v, list):
        v = _js_string(v)
    if not isinstance(v, str):
        return math.nan
    t = _js_trim(v)
    if t == "":
        return 0.0
    if t in ("Infinity", "+Infinity"):
        return math.inf
    if t == "-Infinity":
        return -math.inf
    for pattern, base in ((_HEX, 16), (_OCT, 8), (_BIN, 2)):
        if pattern.fullmatch(t):
            return _num(int(t[2:], base))
    return float(t) if _DECIMAL.fullmatch(t) else math.nan


def _to_primitive(v: object) -> object:
    if isinstance(v, list):
        return _js_string(v)
    if isinstance(v, Mapping):
        return "[object Object]"
    return v


def _js_lt(a: object, b: object) -> bool:
    """``a < b``: two strings by UTF-16 code units, else as numbers (NaN is never less)."""
    pa, pb = _to_primitive(a), _to_primitive(b)
    if isinstance(pa, str) and isinstance(pb, str):
        return pa.encode("utf-16-be", "surrogatepass") < pb.encode("utf-16-be", "surrogatepass")
    return _to_number(pa) < _to_number(pb)


def _js_le(a: object, b: object) -> bool:
    """``a <= b``."""
    pa, pb = _to_primitive(a), _to_primitive(b)
    if isinstance(pa, str) and isinstance(pb, str):
        return not _js_lt(pb, pa)
    return _to_number(pa) <= _to_number(pb)


def _strict_eq(a: object, b: object) -> bool:
    """``a === b``."""
    if _is_num(a) and _is_num(b):
        return _num(cast(float, a)) == _num(cast(float, b))
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    return a is b


def _js_sorted(items: Iterable[Any], compare: Callable[[Any, Any], float]) -> list[Any]:
    """``[...items].sort(compare)``: stable, a NaN comparison counting as equal (CPython and V8 both sort
    by TimSort, calling the comparator in the same order)."""

    def sign(a: Any, b: Any) -> int:
        r = compare(a, b)
        return -1 if r < 0 else 1 if r > 0 else 0

    return sorted(items, key=cmp_to_key(sign))


# ---- JavaScript's arithmetic ----


def _div(a: float, b: float) -> float:
    if b == 0:
        if a == 0 or a != a:
            return math.nan
        return math.copysign(math.inf, a) * math.copysign(1.0, b)
    return a / b


def _floor(x: float) -> float:
    return float(math.floor(x)) if math.isfinite(x) else x


def _rem(a: float, b: float) -> float:
    """JavaScript's ``%``: the remainder takes the dividend's sign."""
    if a != a or b != b or math.isinf(a) or b == 0:
        return math.nan
    if math.isinf(b):
        return a
    return math.fmod(a, b)


def _round(x: float) -> float:
    """``Math.round``: halves toward positive infinity."""
    if not math.isfinite(x):
        return x
    r = _floor(x)
    return r + 1 if x - r >= 0.5 else r


def _floor_div(a: float, b: float) -> float:
    return _floor(_div(a, b))


def _floor_mod(a: float, b: float) -> float:
    return _rem(_rem(a, b) + b, b)


def _at(seq: object, i: float) -> Any:
    """``seq[i]``: undefined unless ``i`` is a whole index inside a list."""
    if isinstance(seq, list) and i.is_integer() and 0 <= i < len(seq):
        return seq[int(i)]
    return _UNDEF


def _out(x: float) -> int:
    """A JavaScript number handed back: an int when whole, else the float itself (inf, nan, a fraction)."""
    if x.is_integer():
        return int(x)
    return cast(int, x)


def _in(v: float) -> float:
    """A number argument as JavaScript holds it."""
    if not _is_num(v):
        raise TypeError(f"expected a number, got {v!r}")
    return _num(v)


def floor_div(a: float, b: float) -> int:
    """Euclidean floor division: ``Math.floor(a / b)``."""
    return _out(_floor_div(_in(a), _in(b)))


def floor_mod(a: float, b: float) -> int:
    """The modulo that stays periodic for negatives: ``floor_mod(-1, 4) == 3``."""
    return _out(_floor_mod(_in(a), _in(b)))


# ---- Validation (the builder's loud check) and the reader ----


def validate_calendar_config(cfg: Mapping[str, Any]) -> list[str]:
    """Every problem a calendar builder must fix before writing ``cfg``, in words; [] when none.
    Stricter than the reader: an overlap of eras or a nameless era is an error here and still reads."""
    if _nullish(cfg):
        raise TypeError("validate_calendar_config: a config is an object")
    errors: list[str] = []
    version = _prop(cfg, "version")
    if not _strict_eq(version, 1) and not _strict_eq(version, 2):
        errors.append(f"Unsupported calendar version: {_js_string(version)}")
    grain = _prop(cfg, "grain")
    if not _truthy(grain) or not isinstance(grain, str):
        errors.append("Grain is required")

    months = _bundle(cfg, "months")
    if _truthy(months):
        names, lengths = _prop(months, "names"), _prop(months, "lengths")
        if (
            not isinstance(names, list)
            or not isinstance(lengths, list)
            or len(names) == 0
            or len(names) != len(lengths)
        ):
            errors.append("months.names and months.lengths must be same-length non-empty arrays")
        elif any(not _is_integer(n) or _js_lt(n, 1) for n in lengths):
            errors.append("Every month length must be a whole number, 1 or more")
        if _truthy(_bundle(cfg, "year")):
            errors.append("year.steps is legal only when no months are defined (year length is derived from months)")
    elif _truthy(_bundle(cfg, "year")):
        steps = _get(_bundle(cfg, "year"), "steps")
        if not _is_integer(steps) or _js_lt(steps, 1):
            errors.append("year.steps must be a positive integer")

    week = _bundle(cfg, "week")
    if _truthy(week):
        length = _prop(week, "length")
        if not _is_integer(length) or _js_lt(length, 1):
            errors.append("The week length must be a whole number, 1 or more")
        else:
            wnames = _prop(week, "names")
            if not isinstance(wnames, list) or not _strict_eq(len(wnames), length):
                errors.append("Give the week as many day names as its length")

    inter_raw = _prop(cfg, "intercalary")
    inter: Any = [] if _nullish(inter_raw) else inter_raw
    if _js_lt(0, _prop(inter, "length")) and not _truthy(months):
        errors.append("Festival days need months")
    # Months without a names list (``0``, ``""``, ``False``, ``{}``) count as none here; their error is
    # appended above (``Array.isArray(months?.names) ? months.names.length : 0`` there).
    names = None if _nullish(months) else _prop(months, "names")
    month_count: Any = len(names) if isinstance(names, list) else 0
    for ic in _items(inter):
        name = _js_string(_get(ic, "name"))
        after = _get(ic, "after_month")
        if not _is_integer(after) or _js_lt(after, 0) or _js_lt(month_count, after):
            errors.append(f'Festival day "{name}": pick the month it follows')
        every = _get(ic, "every_years")
        if not _nullish(every) and (not _is_integer(every) or _js_lt(every, 1)):
            errors.append(f'Festival day "{name}": every N yrs must be a whole number, 1 or more')
        rule = _leap_rule_problem(ic)
        if rule:
            errors.append(f'Festival day "{name}": {rule}')
        if _strict_eq(version, 1) and (not _nullish(_get(ic, "except")) or not _nullish(_get(ic, "offset"))):
            errors.append(f'Festival day "{name}": except and offset need calendar version 2')

    eras_raw = _prop(cfg, "eras")
    eras: Any = [] if _nullish(eras_raw) else eras_raw
    for era in _items(eras):
        name = _js_string(_get(era, "name"))
        if not _truthy(_get(era, "name")):
            errors.append("Every era needs a name")
        start, end = _get(era, "start"), _get(era, "end")
        if not (_is_num(start) and math.isfinite(_num(start))):
            errors.append(f'Era "{name}": start must be a number')
        if not _nullish(end) and not (_is_num(end) and math.isfinite(_num(end))):
            errors.append(f'Era "{name}": end must be a number')
        direction = _get(era, "direction")
        direction = "up" if _nullish(direction) else direction
        if _strict_eq(direction, "up") and not _nullish(end) and _js_le(end, start):
            errors.append(f'Era "{name}": end must be after start')
        if _strict_eq(direction, "down") and not _nullish(end) and _js_le(start, end):
            errors.append(f'Era "{name}": a counting-down era must end below its start')
    domains = _era_domains(_items(eras))
    for i, a in enumerate(domains):
        for b in domains[i + 1 :]:
            if _js_lt(a.lo, b.hi) and _js_lt(b.lo, a.hi):
                errors.append(
                    f'Eras "{_js_string(_prop(a.era, "name"))}" and "{_js_string(_prop(b.era, "name"))}" overlap'
                )
    return errors


def read_calendar_config(value: object) -> CalendarConfig | None:
    """The reader: ``value`` itself when it is a usable calendar object, else None (show bare numbers).
    Refuses exactly what the profile's "Not a calendar" list refuses."""
    if not isinstance(value, Mapping):
        return None
    cfg = value
    version = _prop(cfg, "version")
    if (not _strict_eq(version, 1) and not _strict_eq(version, 2)) or not isinstance(_prop(cfg, "grain"), str):
        return None
    months = _bundle(cfg, "months")
    if _truthy(months):
        names, lengths = _prop(months, "names"), _prop(months, "lengths")
        if (
            not isinstance(names, list)
            or not isinstance(lengths, list)
            or len(names) != len(lengths)
            or len(names) == 0
            or not all(isinstance(n, str) for n in names)
        ):
            return None
    eras = _prop(cfg, "eras")
    if not _nullish(eras) and not isinstance(eras, list):
        return None
    if isinstance(eras, list) and any(
        not isinstance(_prop(e, "name"), str)
        or not _is_safe_integer(_prop(e, "start"))
        or (not _nullish(_prop(e, "end")) and not _is_safe_integer(_prop(e, "end")))
        or (
            not _nullish(_prop(e, "year_base"))
            and not _strict_eq(_prop(e, "year_base"), 0)
            and not _strict_eq(_prop(e, "year_base"), 1)
        )
        for e in eras
    ):
        return None
    inter = _prop(cfg, "intercalary")
    if not _nullish(inter) and (
        not isinstance(inter, list)
        or any(not isinstance(_prop(i, "name"), str) or not _is_integer(_prop(i, "after_month")) for i in inter)
    ):
        return None
    # Every divisor and step size a positive integer, or the year arithmetic can loop forever.
    if _truthy(months) and not all(_is_positive_int(n) for n in _prop(months, "lengths")):
        return None
    year = _bundle(cfg, "year")
    if not _nullish(year) and not _is_positive_int(_prop(year, "steps")):
        return None
    week = _bundle(cfg, "week")
    if not _nullish(week):
        wnames = _prop(week, "names")
        if (
            not _is_positive_int(_prop(week, "length"))
            or not isinstance(wnames, list)
            or not all(isinstance(n, str) for n in wnames)
        ):
            return None
    entries: list[Any] = inter if isinstance(inter, list) else []
    if any(not _nullish(_prop(i, "every_years")) and not _is_positive_int(_prop(i, "every_years")) for i in entries):
        return None
    # Version 2's leap keys (version 1 ignores them, as it ignores any unknown key).
    if _strict_eq(version, 2) and any(_leap_rule_problem(i) is not None for i in entries):
        return None
    return cast(CalendarConfig, cfg)


def _leap_rule_problem(ic: object) -> str | None:
    """Why an entry's version-2 leap keys can't be read, or None. ``except`` a list of whole numbers, each
    above and a multiple of the one before (the first of ``every_years``); ``offset`` a whole number;
    neither without ``every_years``. None reads as absent."""
    ex, off = _prop(ic, "except"), _prop(ic, "offset")
    if _nullish(ex) and _nullish(off):
        return None
    every = _prop(ic, "every_years")
    if _nullish(every):
        return "except and offset need every_years"
    if not _nullish(off) and not _is_safe_integer(off):
        return "offset must be a whole number"
    if not _nullish(ex):
        if not isinstance(ex, list):
            return "except must be a list"
        prev = _to_number(every)
        for d in ex:
            if not _is_positive_int(d) or _num(d) <= prev or _rem(_num(d), prev) != 0:
                return "each except must be a multiple of the number before it, and larger"
            prev = _num(d)
    return None


# ---- Year arithmetic ----


class _LeapRule(NamedTuple):
    n: float
    except_: list[float]
    offset: float


def _is_v2(cfg: object) -> bool:
    return _strict_eq(_prop(cfg, "version"), 2)


def _leap_rule(cfg: object, ic: object) -> _LeapRule:
    v2 = _is_v2(cfg)
    ex = _prop(ic, "except") if v2 else False
    off = _prop(ic, "offset") if v2 else False
    return _LeapRule(
        n=_to_number(_prop(ic, "every_years")),
        except_=[_to_number(d) for d in _items(ex)] if _truthy(ex) else [],
        offset=_to_number(off) if _truthy(off) else 0.0,
    )


def _leap_rules(cfg: object, inter: list[Any]) -> list[_LeapRule]:
    return [_leap_rule(cfg, i) for i in inter if not _nullish(_get(i, "every_years"))]


def _year_shape(cfg: object) -> tuple[float, list[_LeapRule]]:
    """The base year length (months and the days outside them that are not leap days, or
    ``bundles.year.steps``, or 1) and the leap entries' rules."""
    months = _bundle(cfg, "months")
    inter = _list_or_empty(_prop(cfg, "intercalary"))
    rules = _leap_rules(cfg, inter)
    if _truthy(months):
        base = 0.0
        for length in _items(_get(months, "lengths")):
            base = base + _to_number(length)  # reduce((a, b) => a + b, 0): left to right, never sum()
        return base + len([i for i in inter if _nullish(_get(i, "every_years"))]), rules
    steps = _prop(_bundle(cfg, "year"), "steps")
    return (1.0 if _nullish(steps) else _to_number(steps)), rules


def _rule_holds(r: _LeapRule, y: float) -> bool:
    big_y = y + r.offset
    on = _floor_mod(big_y, r.n) == 0
    for d in r.except_:
        if _floor_mod(big_y, d) == 0:
            on = not on
    return on


def _multiples_in(a: float, b: float, m: float, offset: float) -> float:
    """How many k in [a, b) have floor_mod(k + offset, m) == 0."""
    return _floor_div(b - 1 + offset, m) - _floor_div(a - 1 + offset, m)


def _leap_years_before(y: float, r: _LeapRule) -> float:
    """Signed count of the years k the rule selects with 0 <= k < y, minus those with y <= k < 0, in
    closed form: each except is a multiple of the divisor before it, so the terms alternate."""
    a, b, sign = (0.0, y, 1.0) if y >= 0 else (y, 0.0, -1.0)
    count = _multiples_in(a, b, r.n, r.offset)
    s = -1.0
    for d in r.except_:
        count += s * _multiples_in(a, b, d, r.offset)
        s = -s
    return sign * count


def is_leap_year(y: int, n: int) -> bool:
    """The version-1 rule: ``floor_mod(y, n) == 0``."""
    return _floor_mod(_in(y), _in(n)) == 0


def _in_year(cfg: object, ic: object, y: float) -> bool:
    return _nullish(_get(ic, "every_years")) or _rule_holds(_leap_rule(cfg, ic), y)


def intercalary_in_year(cfg: Mapping[str, Any], ic: Mapping[str, Any], y: int) -> bool:
    """Whether the day outside the months falls in absolute year ``y``: always without ``every_years``,
    else by its rule (``except`` and ``offset`` under version 2)."""
    return _in_year(cfg, ic, _in(y))


def _year_start(cfg: object, y: float) -> float:
    base, rules = _year_shape(cfg)
    start = y * base
    for r in rules:
        start += _leap_years_before(y, r)
    return start


def year_start_step(cfg: Mapping[str, Any], y: int) -> int:
    """The first step of absolute year ``y``; ``year_start_step(cfg, 0) == 0``."""
    return _out(_year_start(cfg, _in(y)))


def _year_length(cfg: object, y: float) -> float:
    base, rules = _year_shape(cfg)
    length = base
    for r in rules:
        if _rule_holds(r, y):
            length += 1
    return length


def year_length(cfg: Mapping[str, Any], y: int) -> int:
    """The length in steps of absolute year ``y``."""
    return _out(_year_length(cfg, _in(y)))


def _mean_leap(r: _LeapRule) -> float:
    """A rule's mean leap days per year: 1/n - 1/e1 + 1/e2 - ..."""
    m = _div(1, r.n)
    s = -1.0
    for d in r.except_:
        m += _div(s, d)
        s = -s
    return m


#: Correction laps allowed per direction: a valid config needs a few; the cap stops a malformed one hanging.
_MAX_YEAR_CORRECTION: Final = 10_000


def _abs_year(cfg: object, step: float) -> float:
    base, rules = _year_shape(cfg)
    mean = base
    for r in rules:
        mean = mean + _mean_leap(r)
    y = _floor_div(step, mean)
    if not math.isfinite(y):
        return y
    i = 0
    while i < _MAX_YEAR_CORRECTION and step < _year_start(cfg, y):
        y -= 1
        i += 1
    i = 0
    while i < _MAX_YEAR_CORRECTION and step >= _year_start(cfg, y + 1):
        y += 1
        i += 1
    return y


def absolute_year(cfg: Mapping[str, Any], step: int) -> int:
    """The absolute year index of a step: zero-based, step 0 opens year 0."""
    return _out(_abs_year(cfg, _in(step)))


# ---- Eras ----


def _direction(era: object) -> Any:
    d = _get(era, "direction")
    return "up" if _nullish(d) else d


def _era_domains(eras: list[Any]) -> list[EraDomain]:
    ordered = _js_sorted(eras, lambda a, b: _to_number(_get(a, "start")) - _to_number(_get(b, "start")))
    out: list[EraDomain] = []
    for i, era in enumerate(ordered):
        end = _get(era, "end")
        if _strict_eq(_direction(era), "down"):
            # [end or -inf, start): counts toward the pivot; the pivot belongs to the next (up) era.
            out.append(EraDomain(era, -math.inf if _nullish(end) else end, _get(era, "start")))
        else:
            # An open end runs to the next UP era's start: a down era holds no step at or above its pivot.
            next_up = next((e for e in ordered[i + 1 :] if _strict_eq(_direction(e), "up")), None)
            hi = end
            if _nullish(hi):
                hi = math.inf if next_up is None or _nullish(_get(next_up, "start")) else _get(next_up, "start")
            out.append(EraDomain(era, _get(era, "start"), hi))
    return out


def resolve_era_domains(eras: list[Mapping[str, Any]]) -> list[EraDomain]:
    """Each era's range of steps, ordered by start."""
    return _era_domains(_items(eras))


def _era_for(cfg: object, step: float) -> Any:
    eras = _list_or_empty(_prop(cfg, "eras"))
    if len(eras) == 0:
        return None
    holding = [d for d in _era_domains(eras) if _js_le(d.lo, step) and _js_lt(step, d.hi)]
    if not holding:
        return None
    place = {id(e): i for i, e in enumerate(eras)}

    def down(e: object) -> float:
        return 1.0 if _strict_eq(_direction(e), "down") else 0.0

    def compare(a: EraDomain, b: EraDomain) -> float:
        by_start = _to_number(_get(b.era, "start")) - _to_number(_get(a.era, "start"))
        if _truthy(by_start):
            return by_start
        by_direction = down(a.era) - down(b.era)
        if by_direction:
            return by_direction
        return float(place.get(id(b.era), 0) - place.get(id(a.era), 0))

    return _js_sorted(holding, compare)[0].era


def era_for_step(cfg: Mapping[str, Any], step: int) -> Mapping[str, Any] | None:
    """The era holding a step. Overlaps resolve to the latest start, then an up era over a down one,
    then the later era in the list."""
    return cast("Mapping[str, Any] | None", _era_for(cfg, _in(step)))


def _display_year(cfg: object, step: float, era: object) -> float:
    abs_year = _abs_year(cfg, step)
    if era is None or _get(era, "restart") is False:
        return abs_year
    base_raw = _get(era, "year_base")
    base = 1.0 if _nullish(base_raw) else _to_number(base_raw)
    start = _to_number(_get(era, "start"))
    if _strict_eq(_direction(era), "down"):
        # Counted back from the year holding the step just before the pivot, which is year ``base``.
        return _abs_year(cfg, start - 1) - abs_year + base
    return abs_year - _abs_year(cfg, start) + base


def display_year(cfg: Mapping[str, Any], step: int, era: Mapping[str, Any] | None) -> int:
    """The year a step shows under ``era`` (the absolute year with none, or with ``restart`` false)."""
    return _out(_display_year(cfg, _in(step), era))


def _abs_year_for_era_year(cfg: object, era: object, y: float) -> float:
    if _get(era, "restart") is False:
        return y
    base_raw = _get(era, "year_base")
    base = 1.0 if _nullish(base_raw) else _to_number(base_raw)
    start = _to_number(_get(era, "start"))
    if _strict_eq(_direction(era), "down"):
        return _abs_year(cfg, start - 1) - (y - base)
    return _abs_year(cfg, start) + (y - base)


def abs_year_for_era_year(cfg: Mapping[str, Any], era: Mapping[str, Any], y: int) -> int:
    """The absolute year of an era's display year ``y``: ``display_year`` inverted."""
    if _get(era, "restart") is False:
        return y
    return _out(_abs_year_for_era_year(cfg, era, _in(y)))


# ---- The year's days: months, and the days outside them ----


class _Slot(NamedTuple):
    kind: Literal["month", "intercalary"]
    month: int
    day: int
    intercalary: Any


def _year_slots(cfg: object, y: float) -> list[_Slot]:
    months = _bundle(cfg, "months")
    if not _truthy(months):
        return []
    inter = _list_or_empty(_prop(cfg, "intercalary"))
    names, lengths = _get(months, "names"), _get(months, "lengths")
    slots: list[_Slot] = []

    def push(after: int) -> None:
        for ic in inter:
            if _strict_eq(_get(ic, "after_month"), after) and _in_year(cfg, ic, y):
                slots.append(_Slot("intercalary", 0, 0, ic))

    push(0)
    m = 1
    while _js_le(m, _get(names, "length")):
        days = _to_number(_at(lengths, m - 1))
        d = 1
        while d <= days:
            slots.append(_Slot("month", m, d, None))
            d += 1
        push(m)
        m += 1
    return slots


class _Position(NamedTuple):
    abs_year: float
    offset: float
    slot: _Slot | None
    slots: list[_Slot] | None


def _position(cfg: object, step: float) -> _Position:
    y = _abs_year(cfg, step)
    offset = step - _year_start(cfg, y)
    if not _truthy(_bundle(cfg, "months")):
        return _Position(y, offset, None, None)
    slots = _year_slots(cfg, y)
    slot = _at(slots, offset)
    return _Position(y, offset, None if slot is _UNDEF else slot, slots)


# ---- Weekday ----


def _weekday(cfg: object, step: float, pos: _Position) -> Any:
    week = _bundle(cfg, "week")
    if not _truthy(week):
        return None
    length, names = _get(week, "length"), _get(week, "names")
    if _js_lt(length, 1) or not _strict_eq(_get(names, "length"), length):
        return None
    mode = _get(week, "mode")
    if _strict_eq("free" if _nullish(mode) else mode, "nested"):
        if pos.slot is None or pos.slot.kind != "month":
            return None
        return _none(_at(names, _floor_mod(pos.slot.day - 1, _to_number(length))))
    # Free: the counted steps leave out in_week false days outside the months; counted 0 is names[0].
    if pos.slot is not None and pos.slot.kind == "intercalary" and _prop(pos.slot.intercalary, "in_week") is False:
        return None
    skipped = [i for i in _list_or_empty(_prop(cfg, "intercalary")) if _get(i, "in_week") is False]
    y = pos.abs_year
    skipped_before = y * len([i for i in skipped if _nullish(_get(i, "every_years"))])
    for r in _leap_rules(cfg, skipped):
        skipped_before += _leap_years_before(y, r)
    skipped_in_year = 0.0
    if pos.slots is not None:
        i = 0
        while i < pos.offset:
            s = _at(pos.slots, i)
            if s is _UNDEF:
                raise TypeError("Cannot read properties of undefined (reading 'kind')")
            if s.kind == "intercalary" and _prop(s.intercalary, "in_week") is False:
                skipped_in_year += 1
            i += 1
    counted = step - skipped_before - skipped_in_year
    return _none(_at(names, _floor_mod(counted, _to_number(length))))


def weekday_for_step(cfg: Mapping[str, Any], step: int) -> str | None:
    """The weekday of a step, or None: no week, a nested week outside the months, a day out of the week,
    or fewer names than the week's length."""
    s = _in(step)
    return cast("str | None", _weekday(cfg, s, _position(cfg, s)))


# ---- Breakdown and format ----


class _Parts(NamedTuple):
    abs_year: float
    year: float
    era: Any
    slot: _Slot | None
    month_name: Any
    weekday: Any


def _parts(cfg: object, step: float) -> _Parts:
    pos = _position(cfg, step)
    era = _era_for(cfg, step)
    months = _bundle(cfg, "months")
    slot = pos.slot
    month_name = (
        _none(_at(_get(months, "names"), slot.month - 1))
        if slot is not None and slot.kind == "month" and _truthy(months)
        else None
    )
    return _Parts(pos.abs_year, _display_year(cfg, step, era), era, slot, month_name, _weekday(cfg, step, pos))


def breakdown_step(cfg: Mapping[str, Any], step: int) -> StepBreakdown:
    """A step taken apart: absolute year, display year, era, month, day, the day outside the months, weekday."""
    s = _in(step)
    p = _parts(cfg, s)
    month = p.slot is not None and p.slot.kind == "month"
    return StepBreakdown(
        step=_out(s),
        abs_year=_out(p.abs_year),
        year=_out(p.year),
        era=p.era,
        month=p.slot.month if p.slot is not None and month else None,
        month_name=p.month_name,
        day=p.slot.day if p.slot is not None and month else None,
        intercalary=_get(p.slot.intercalary, "name") if p.slot is not None and not month else None,
        weekday=p.weekday,
    )


_KNOWN_TOKENS: Final = ("day", "month", "weekday", "year", "era", "step", "intercalary")
_DEFAULT_FORMAT_MONTHS: Final = "{day} {month}, {year} {era}"
_DEFAULT_FORMAT_PLAIN: Final = "{year} {era}"
_DEFAULT_FORMAT_INTERCALARY: Final = "{intercalary}, {year} {era}"

#: A known token that resolved to nothing, so the collapse can absorb it with the separators around it.
#: U+E000, a private-use code point, as the reference's (never NUL).
_EMPTY_KNOWN: Final = chr(0xE000)
_TOKEN = re.compile(r"\{([a-z_]+)\}")
_COLLAPSE = re.compile(_S + "*[,;" + _MIDDOT + "]?" + _S + "*" + _EMPTY_KNOWN + _S + "*[,;" + _MIDDOT + "]?" + _S + "*")
_SPACES = re.compile(_S + "{2,}")
_EDGES = re.compile(r"\A" + _SEP + "+|" + _SEP + r"+\Z")


def _render(template: object, values: dict[str, Any]) -> str:
    """Substitute, then collapse: a known token with no value prints empty and the separators beside it
    close up; an unknown token prints as written."""
    if not isinstance(template, str):
        raise TypeError(f"a format template is a string, got {template!r}")

    def token(m: re.Match[str]) -> str:
        if m.group(1) not in _KNOWN_TOKENS:
            return m.group(0)
        v = values[m.group(1)]
        return _EMPTY_KNOWN if _nullish(v) or v == "" else _js_string(v)

    out = _TOKEN.sub(token, template)
    out = _js_trim(_SPACES.sub(" ", _COLLAPSE.sub(" ", out)))
    return _EDGES.sub("", out)


def _era_label(era: object) -> Any:
    abbrev = _get(era, "abbrev")
    return _get(era, "name") if _nullish(abbrev) else abbrev


def format_step(cfg: Mapping[str, Any], step: int) -> str:
    """A step in the calendar's words (its ``format``, else the profile's default). Total: every number
    formats under every config ``read_calendar_value`` accepts."""
    s = _in(step)
    p = _parts(cfg, s)
    month = p.slot is not None and p.slot.kind == "month"
    intercalary = _get(p.slot.intercalary, "name") if p.slot is not None and not month else None
    values: dict[str, Any] = {
        "day": str(p.slot.day) if p.slot is not None and month else None,
        "month": p.month_name,
        "weekday": p.weekday,
        "year": _js_num_str(p.year),
        "era": _era_label(p.era) if p.era is not None else None,
        "step": _js_num_str(s),
        "intercalary": intercalary,
    }
    if not _nullish(intercalary):
        template = _prop(cfg, "format_intercalary")
        template = _DEFAULT_FORMAT_INTERCALARY if _nullish(template) else template
    else:
        template = _prop(cfg, "format")
        if _nullish(template):
            template = _DEFAULT_FORMAT_MONTHS if _truthy(_bundle(cfg, "months")) else _DEFAULT_FORMAT_PLAIN
    return _render(template, values)


def _year_label(cfg: object, step: float) -> str:
    era = _era_for(cfg, step)
    year = _display_year(cfg, step, era)
    label = _era_label(era) if era is not None else ""
    return f"{_js_num_str(year)} {_js_string(label)}" if _truthy(label) else _js_num_str(year)


def format_year_label(cfg: Mapping[str, Any], step: int) -> str:
    """``{year} {era}`` for an axis tick zoomed wide; the absolute year alone outside every era."""
    return _year_label(cfg, _in(step))


def format_mid_label(cfg: Mapping[str, Any], step: int) -> str:
    """``11 Greening 454``: day, month and year with no era word (``Hearthmoot 454`` on a day outside the
    months); the year label with no months."""
    s = _in(step)
    p = _parts(cfg, s)
    intercalary = _get(p.slot.intercalary, "name") if p.slot is not None and p.slot.kind == "intercalary" else None
    if not _nullish(intercalary):
        return f"{_js_string(intercalary)} {_js_num_str(p.year)}"
    if p.month_name is not None and p.slot is not None and p.slot.kind == "month":
        return f"{p.slot.day} {_js_string(p.month_name)} {_js_num_str(p.year)}"
    return _year_label(cfg, s)


def _base_year_length(cfg: object) -> Any:
    months = _bundle(cfg, "months")
    if not _truthy(months):
        return _UNDEF
    total = 0.0
    for length in _items(_get(months, "lengths")):
        total = total + _to_number(length)
    inter = _list_or_empty(_prop(cfg, "intercalary"))
    return total + len([i for i in inter if _nullish(_get(i, "every_years"))])


def approx_year_length(cfg: Mapping[str, Any]) -> int | None:
    """The base year length in steps (leap days left out), or None with no year above the step."""
    base = _base_year_length(cfg)
    if base is not _UNDEF:
        return _out(base)
    steps = _prop(_bundle(cfg, "year"), "steps")
    return None if _nullish(steps) else cast(int, _out(steps) if _is_num(steps) else steps)


def format_duration(cfg: Mapping[str, Any], steps: float) -> str:
    """A duration spoken: ``19 years`` once it reaches the base year (one decimal below 10 years), else
    ``12 days`` in the calendar's word for a step."""
    n = abs(_in(steps))
    word = _prop(cfg, "step_name")
    if _nullish(word):
        word = _prop(cfg, "grain")
    if _nullish(word):
        word = "step"
    if not isinstance(word, str):
        raise TypeError(f"a step's name is a string, got {word!r}")
    unit = _js_trim(word) or "step"

    def plural(w: str, v: float) -> str:
        return w if v == 1 else f"{w}s"

    year_len = _base_year_length(cfg)
    if year_len is _UNDEF:
        year_len = _prop(_bundle(cfg, "year"), "steps")
        if _nullish(year_len):
            year_len = 1.0 if unit.lower() == "year" else None
    if not _nullish(year_len) and _js_lt(1, year_len) and _js_le(year_len, n):
        years = _div(n, _to_number(year_len))
        rounded = _round(years) if years >= 10 else _div(_round(years * 10), 10)
        return f"{_js_num_str(rounded)} {plural('year', rounded)}"
    shown = _div(_round(n * 100), 100)
    return f"{_js_num_str(shown)} {plural(unit, shown)}"


def month_start_steps(cfg: Mapping[str, Any], y: int) -> list[MonthStart]:
    """The first step of each month in absolute year ``y``, in order; [] with no months."""
    year = _in(y)
    months = _bundle(cfg, "months")
    if not _truthy(months):
        return []
    inter = _list_or_empty(_prop(cfg, "intercalary"))
    names, lengths = _get(months, "names"), _get(months, "lengths")
    offset = float(len([i for i in inter if _strict_eq(_get(i, "after_month"), 0) and _in_year(cfg, i, year)]))
    start = _year_start(cfg, year)
    out: list[MonthStart] = []
    m = 1
    while _js_le(m, _get(names, "length")):
        out.append({"month": m, "name": _none(_at(names, m - 1)), "step": _out(start + offset)})
        offset += _to_number(_at(lengths, m - 1)) + len(
            [i for i in inter if _strict_eq(_get(i, "after_month"), m) and _in_year(cfg, i, year)]
        )
        m += 1
    return out


# ---- Parse ----

_INT = re.compile(r"-?[0-9]+")
_COMMA_DOT = re.compile(r"[,.]")
_RUN = re.compile(_S + "+")
_YEAR_WORD = re.compile(" year ")


def _parse_int(text: str) -> float:
    """``parseInt(text, 10)`` for ``-?[0-9]+``: past the double range it is infinity (``int()`` has a
    digit limit; ``parseInt`` has none)."""
    negative = text.startswith("-")
    digits = text.lstrip("-").lstrip("0")
    value = math.inf if len(digits) > 400 else _num(int(digits)) if digits else 0.0
    return -value if negative else value


def _normalize(s: object) -> str:
    """Words matched as written, case and punctuation aside: ``S.R.`` matches ``s r``."""
    if not isinstance(s, str):
        raise TypeError(f"a calendar word is a string, got {s!r}")
    return f" {_js_trim(_RUN.sub(' ', _COMMA_DOT.sub(' ', s.lower())))} "


def _default_era(cfg: object, now: float | None) -> Any:
    """The era an input that names none reads in: the one holding the now, else the latest-started open
    era, else the latest-started."""
    eras = _list_or_empty(_prop(cfg, "eras"))
    if len(eras) == 0:
        return None
    if now is not None:
        holder = _era_for(cfg, now)
        if holder is not None:
            return holder
    open_eras = [e for e in eras if not _truthy(_get(e, "closed"))]
    pool = open_eras if open_eras else eras
    return _js_sorted(pool, lambda a, b: _to_number(_get(b, "start")) - _to_number(_get(a, "start")))[0]


def _length_of(key: object) -> float:
    return _to_number(_prop(key, "length"))


def parse_date(cfg: Mapping[str, Any], text: str, *, now: int | None = None) -> ParseResult | ParseError:
    """Written words to a step, or a ``ParseError`` with its reason.

    A bare number (``"-454"``) is always the raw step. Otherwise calendar words are matched without
    regard to case: ``"454 AE"``, ``"Year 12 FT"``, ``"Frostwane 454"``, ``"12 Frostwane 454"``,
    ``"Shieldmeet 1372"``; a partial date opens its period. A month and a day with no year read in the
    year holding ``now``, and with no ``now`` are refused, never guessed. ``format_step`` of the result is
    ``format_step`` of the step that was written; the step itself is not promised back.
    """
    if not isinstance(text, str):
        raise TypeError(f"parse_date: the text is a string, got {text!r}")
    now_n = None if now is None else _in(now)
    raw = _js_trim(text)
    if raw == "":
        return {"error": "empty date"}
    if _INT.fullmatch(raw):
        return {"step": _out(_parse_int(raw))}

    months = _bundle(cfg, "months")
    inter = _list_or_empty(_prop(cfg, "intercalary"))
    era: Any = None
    month_index: int | None = None
    intercalary: Any = None
    # Names are eaten before numbers are read: a name may hold digits ("2 Yule").
    rest = _YEAR_WORD.sub(" ", _normalize(raw))

    def eat(name: object) -> bool:
        nonlocal rest
        needle = _normalize(name)
        if needle in rest:
            rest = rest.replace(needle, " ", 1)
            return True
        return False

    # Eras first, longest names first, so "After Empire" beats "Empire".
    candidates: list[tuple[Any, Any]] = []
    for e in _list_or_empty(_prop(cfg, "eras")):
        candidates.append((_get(e, "name"), e))
        if _truthy(_get(e, "abbrev")):
            candidates.append((_get(e, "abbrev"), e))
    for key, e in _js_sorted(candidates, lambda a, b: _length_of(b[0]) - _length_of(a[0])):
        if eat(key):
            era = e
            break
    for ic in _js_sorted(inter, lambda a, b: _length_of(_get(b, "name")) - _length_of(_get(a, "name"))):
        if eat(_get(ic, "name")):
            intercalary = ic
            break
    if intercalary is None and _truthy(months):
        names = _get(months, "names")
        m = 1
        while _js_le(m, _get(names, "length")):
            if eat(_at(names, m - 1)):
                month_index = m
                break
            m += 1

    # What remains must be numbers only.
    numbers: list[float] = []
    for part in [p for p in _RUN.split(_js_trim(rest)) if p]:
        if not _INT.fullmatch(part):
            return {"error": f'unrecognized: "{part}"'}
        numbers.append(_parse_int(part))

    # With a month: [day?, year?]; with a day outside the months: [year?]; else [year].
    day: float | None = None
    year: float | None = None
    if month_index is not None:
        length = _to_number(_at(_get(months, "lengths"), month_index - 1))
        if len(numbers) == 2:
            # Day first and day second both occur: the day is the one that fits; a tie reads day first.
            a, b = numbers
            if 1 <= a <= length:
                day, year = a, b
            elif 1 <= b <= length:
                day, year = b, a
            else:
                month_name = _js_string(_at(_get(months, "names"), month_index - 1))
                return {"error": f"no day in {month_name} matches {_js_num_str(a)}/{_js_num_str(b)}"}
        elif len(numbers) == 1:
            # One number beside a month: a plausible day reads in the now's year; else it is the year.
            n = numbers[0]
            if 1 <= n <= length:
                day = n
            else:
                year = n
        elif len(numbers) != 0:
            return {"error": "too many numbers"}
    elif intercalary is not None:
        if len(numbers) > 1:
            return {"error": "too many numbers"}
        year = numbers[0] if numbers else None
    else:
        if len(numbers) != 1:
            return {"error": "expected a year"}
        year = numbers[0]

    def resolve_in_year(abs_year: float) -> ParseResult | ParseError:
        start = _year_start(cfg, abs_year)
        if month_index is None and intercalary is None:
            return {"step": _out(start)}
        slots = _year_slots(cfg, abs_year)
        if intercalary is not None:
            idx = next((i for i, s in enumerate(slots) if s.kind == "intercalary" and s.intercalary is intercalary), -1)
            if idx == -1:
                return {"error": f"{_js_string(_get(intercalary, 'name'))} does not occur in that year"}
            return {"step": _out(start + idx)}
        want = 1.0 if day is None else day
        idx = next(
            (i for i, s in enumerate(slots) if s.kind == "month" and s.month == month_index and s.day == want), -1
        )
        if idx == -1:
            return {"error": "that day does not exist in that month"}
        return {"step": _out(start + idx)}

    if year is None:
        if now_n is None:
            return {"error": "add a year (the world clock has no now set)"}
        return resolve_in_year(_abs_year(cfg, now_n))

    target = era if era is not None else _default_era(cfg, now_n)
    if target is None:
        return resolve_in_year(year)

    # The era's reading first; a step outside the era's own range (format shows absolute years outside
    # every era) falls back to the absolute reading, so format(parse(format(n))) holds.
    via_era = resolve_in_year(_abs_year_for_era_year(cfg, target, year))
    if "error" in via_era:
        return via_era
    if _era_for(cfg, _num(via_era["step"])) is target:
        return via_era
    via_abs = resolve_in_year(year)
    # A typed era names the date's era: an absolute reading that lands in an era is a date the input
    # never named, and is refused; the fallback stays for a step in no era.
    if era is not None and "error" not in via_abs and _era_for(cfg, _num(via_abs["step"])) is not None:
        return {"error": f"not a date in {_js_string(_get(era, 'name'))}"}
    return via_abs


def is_parse_error(result: ParseResult | ParseError) -> bool:
    """Whether ``parse_date`` refused."""
    return "error" in result


# ---- A world's calendars ----


def read_calendar_value(raw: object) -> CalendarConfig | None:
    """The tolerant ``atlas_calendar`` read: an object, or the same object as a JSON string (strict JSON:
    no ``NaN``, no ``Infinity``, no single quotes). None for anything that is not a calendar."""
    if raw is None:
        return None
    value: object = raw
    if isinstance(raw, str):
        try:
            value = _json_parse(raw)
        except ValueError:
            return None
    return read_calendar_config(value)


def _refuse_constant(name: str) -> object:
    raise ValueError(f"{name} is not JSON")


def _json_int(text: str) -> float:
    """An integer literal as ``JSON.parse`` reads it: past the double range it is infinity (and ``int()``
    refuses more than 4300 digits; a JSON integer has no leading zeros, so 401 digits is already past)."""
    if len(text) > 401:
        return -math.inf if text.startswith("-") else math.inf
    value = int(text)
    return value if math.isfinite(_num(value)) else _num(value)


#: One token of strict JSON (RFC 8259, what ``JSON.parse`` takes), white space before it.
_JSON_TOKEN = re.compile(
    r'[ \t\n\r]*(?:(\{)|(\})|(\[)|(\])|(,)|(:)|("(?:[^"\\\x00-\x1f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*")'
    r"|(-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)|(true|false|null))"
)
_JSON_LITERALS: Final[dict[str, object]] = {"true": True, "false": False, "null": None}


def _json_parse(text: str) -> object:
    """``JSON.parse``: strict JSON, no ``NaN`` or ``Infinity``, at any depth. ``json.loads`` first; past
    Python's C recursion limit (a value nested some thousand deep, which V8 parses) a loop with its own stack."""
    try:
        return json.loads(text, parse_constant=_refuse_constant, parse_int=_json_int)
    except RecursionError:
        return _json_parse_flat(text)


def _json_parse_flat(text: str) -> object:
    """Strict JSON with an explicit stack in place of recursion; a ValueError when it is not JSON."""
    root: object = _UNDEF
    stack: list[tuple[list[Any] | dict[str, Any], list[str]]] = []  # a container, and its pending key
    state = "value"  # value, first_value (after "["), first_key (after "{"), key, colon, after
    pos = 0

    def attach(v: object) -> None:
        nonlocal root
        if not stack:
            root = v
            return
        container, key = stack[-1]
        if isinstance(container, list):
            container.append(v)
        else:
            container[key[0]] = v

    while True:
        if state == "after" and not stack:
            if text[pos:].strip(" \t\n\r"):
                raise ValueError("JSON: text after the value")
            return root
        m = _JSON_TOKEN.match(text, pos)
        if m is None:
            raise ValueError(f"JSON: no token at {pos}")
        pos, kind, token = m.end(), m.lastindex, m.group(m.lastindex or 0)
        if state in ("value", "first_value"):
            if kind == 4 and state == "first_value":
                stack.pop()
                state = "after"
            elif kind in (1, 3):
                child: list[Any] | dict[str, Any] = {} if kind == 1 else []
                attach(child)
                stack.append((child, [""]))
                state = "first_key" if kind == 1 else "first_value"
            elif kind in (7, 8, 9):
                attach(json.loads(token, parse_int=_json_int) if kind != 9 else _JSON_LITERALS[token])
                state = "after"
            else:
                raise ValueError(f"JSON: unexpected {token!r}")
        elif state in ("first_key", "key"):
            if kind == 2 and state == "first_key":
                stack.pop()
                state = "after"
            elif kind == 7:
                stack[-1][1][0] = json.loads(token)
                state = "colon"
            else:
                raise ValueError(f"JSON: unexpected {token!r}")
        elif state == "colon":
            if kind != 6:
                raise ValueError(f"JSON: unexpected {token!r}")
            state = "value"
        else:  # after a value, inside a container
            container = stack[-1][0]
            if kind == 5:
                state = "value" if isinstance(container, list) else "key"
            elif (kind == 4 and isinstance(container, list)) or (kind == 2 and isinstance(container, dict)):
                stack.pop()
            else:
                raise ValueError(f"JSON: unexpected {token!r}")


def world_calendars(elements: Iterable[Mapping[str, Any]]) -> list[WorldCalendar]:
    """Every usable calendar in a world: the elements carrying a valid ``atlas_calendar``, found by the
    field and never by type or supertype. A malformed config is skipped, never an error."""
    out: list[WorldCalendar] = []
    for el in elements:
        config = read_calendar_value(_none(_get(el, CALENDAR_FIELD)))
        if config is None:
            continue
        name = _get(el, "name")
        out.append(WorldCalendar(_none(_get(el, "id")), name if _truthy(name) else "(unnamed calendar)", config))
    return out


class _NotChosen:
    __slots__ = ()

    def __repr__(self) -> str:
        return "not chosen"


_NOT_CHOSEN: Final = _NotChosen()


def resolve_calendar(
    elements: Iterable[Mapping[str, Any]],
    active_id: str | _NotChosen | None = _NOT_CHOSEN,
    *,
    fallback_to_only: bool = False,
) -> WorldCalendar | None:
    """The chosen calendar among the elements, or None (bare numbers): a None, dangling or invalid choice.

    Leave ``active_id`` out when no calendar was ever chosen: then with ``fallback_to_only`` a world that
    holds exactly one calendar speaks it. None is an explicit "no calendar" and stays None; with several
    calendars and no choice nothing is guessed.
    """
    if active_id is _NOT_CHOSEN and _truthy(fallback_to_only):
        found = world_calendars(elements)
        return found[0] if len(found) == 1 else None
    if isinstance(active_id, _NotChosen) or not _truthy(active_id):
        return None
    return next((c for c in world_calendars(elements) if _strict_eq(c.id, active_id)), None)


def resolve_calendar_lens(
    elements: Iterable[Mapping[str, Any]],
    active_id: str | _NotChosen | None = _NOT_CHOSEN,
    *,
    fallback_to_only: bool = False,
) -> WorldCalendar | None:
    """Deprecated since 0.69.0: the old name of ``resolve_calendar``, with the same answers.

    "Lens" now names a cut of a world, not a chosen calendar. Warns with ``DeprecationWarning``.
    """
    warnings.warn(
        "resolve_calendar_lens is renamed resolve_calendar; the old name will be removed",
        DeprecationWarning,
        stacklevel=2,
    )
    return resolve_calendar(elements, active_id, fallback_to_only=fallback_to_only)
