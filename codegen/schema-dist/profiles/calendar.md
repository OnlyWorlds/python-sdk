# Extension profile: `atlas_calendar`

**What it is.** A world's own calendar: the names a world gives to its time line (months, weeks, eras, leap days). It changes no date. Every date field in OnlyWorlds stays a plain integer in the world's `time_basic_unit`; the calendar only says how to read that integer aloud.

**Key name.** `atlas_calendar`. It keeps its name from before the profile grammar (`x_<profile>_<field>`), because three readers already use it: Atlas, the TypeScript SDK (`CALENDAR_FIELD`) and the Unity SDK.

**On which element.** Any element may carry it; a reader finds calendars by the field being present, never by type or supertype. By convention it sits on a Construct with supertype `calendar`, and that is where Atlas makes one. A world can hold several. Which one a tool speaks is the tool's own choice; Atlas speaks the only one when there is one, and offers a choice when there are more.

**The value.** A JSON object (a reader also accepts the same object as a JSON string, strict JSON only; a writer writes the object):

| Key | Meaning |
|---|---|
| `version` | `1`, or `2` when any `intercalary` entry carries `except` or `offset` (below). A reader that knows only `1` refuses a `2` whole (no calendar, the raw step shown), rather than reading a Gregorian leap rule as a plain every-4 one without saying so. Any other value: not a calendar. |
| `grain` | The world's `time_basic_unit` when the calendar was made (`"day"`, `"year"`, ...). One step of the time line. Required: a value without a string `grain` is not a calendar. |
| `step_name` | The culture's word for one step ("Sol"). Optional; defaults to `grain`. |
| `bundles.months` | `names` and `lengths` (same length, each length a whole number of steps from 1). |
| `bundles.year` | `steps`: a year's length, only for a calendar without months. |
| `bundles.week` | `length`, `names`, and `mode`: `free` (default, runs across months, step 0 is `names[0]`) or `nested` (restarts each month). |
| `intercalary` | Days that belong to no month: `name`, `after_month` (0 = before month 1), `every_years` (a leap rule: present in years where the year index divides by it), `except` (optional, version 2: a strictly ascending list of whole numbers, each larger than and a multiple of `every_years` and of the entry before it, read in order, each flipping the rule for the years it divides; `every_years` 4 with `except` [100, 400] reads "every 4, not every 100, yet every 400"; the last matching divisor decides; Gregorian is `every_years` 4, `except` [100, 400], `offset` 1), `offset` (optional, version 2: a whole number, default 0, added to the year index before the rule and its exceptions are applied, so the rule reads the year the calendar shows; a calendar with no year 0 writes `offset` 1, the same shift before and after the epoch), `in_week` (default true). |
| `eras` | `name`, `abbrev`, `start` (a step), `end`, `restart` (default true: years count from the era), `year_base` (0 or 1, default 1), `direction` (`up`, or `down` for a count toward a pivot, like BC), `closed` (shown for old dates, never offered for new ones). |
| `format`, `format_intercalary` | Templates with `{day} {month} {weekday} {year} {era} {step}` (and `{intercalary}`). Defaults: `{day} {month}, {year} {era}` with months, `{year} {era}` without, `{intercalary}, {year} {era}` for a day outside the months. |

**How a reader turns a date into words.**
1. The date is an integer step. Step 0 opens year 0, and that is fixed: a calendar has no epoch offset. A world that wants day 0 elsewhere stores its dates shifted.
2. Division is Euclidean floor throughout, so negative steps (a backstory) read like positive ones.
3. A year is the months' lengths plus any leap days its year index earns; year index = how many whole years from step 0. The leap rule is a floored modulo on the year index plus `offset`, so with no offset year 0 is a leap year and negative years follow the same rule; then each divisor in `except`, in order, flips the answer for the years it divides, and the last that matches decides.
4. The era is the one whose range holds the step. An era without `end` runs to the start of the next `up` era in the list; `down` eras are skipped, since a `down` era never holds a step at or above its pivot (an `up` era at 0 listed before a `down` era with its pivot at 0 is not emptied by it: step 5 reads 6 AF with `year_base` 1, whatever the list order). Where eras overlap, the latest start wins; at equal starts an `up` era wins over a `down` one (a missing or `null` direction is `up`); between two of the same direction, the later in the list wins. An `up` era counts its years from the year its `start` falls in, from `year_base`. A `down` era counts back from the year holding the step just before its pivot, which is `year_base`, so a pivot in the middle of a year leaves no year 0.
5. Fill the template. A known token with no value (no week, no era) prints empty, and one `,` `;` `·` or space on each side of it closes up; a dash never does. An unknown token prints as written.

The TypeScript SDK holds this whole as `breakdownStep` and `formatStep` (and `parseDate` back); a reader in another language can port those functions, and the SDK's source is the reference.

**`null` is absent.** Anywhere in the value (`eras`, `intercalary`, `bundles.months`, an era's `direction`), `null` reads as if the key were not there, as it does everywhere in the standard.

**Accepted as the SDK reads them.** Fewer weekday names than the week's length (no weekday is printed); months and `bundles.year` together (the months win); an `after_month` past the last month (that day sits in no month); neither months nor a year length (each step is one year).

**What a reader may ignore.** Unknown keys anywhere in the value. `closed` (it only governs date entry). `grain` in the arithmetic (it does not change how a step is read, but it must be present). `step_name` and the format templates, if the reader prints its own way.

**Not a calendar.** A reader refuses the value, and shows bare numbers, never an error, when:
- `version` is not 1 or 2 (a reader that knows only 1 refuses 2 whole);
- `grain` is not a string;
- the months' `names` and `lengths` are not lists of the same, non-zero length, or a month name is not a string;
- a month length, `bundles.year.steps`, `bundles.week.length` or an `every_years` is not a whole number from 1; an `except` is not a strictly ascending list of whole numbers, each larger than and a multiple of `every_years` and of the one before (`[4]` under `every_years` 4 selects no year), or an `offset` is not a whole number;
- `bundles.week.names` is not a list of strings;
- `eras` is present and not a list (`false`, `0` and `""` included), or an era lacks a string `name` or a whole-number `start`, or its `end` or `year_base` is present and not a whole number;
- `intercalary` is present and not a list (`false`, `0` and `""` included), or an entry lacks a string `name` or a whole `after_month`.

Every reader refuses the same values, or one tool shows a calendar where another shows numbers.

**What a writer must keep.** Everything it did not change, unknown keys included. A re-key never rewrites the value (it holds no element ids).

**Conformance.** `calendar.fixture.json`, beside this page: 64 cases, 52 generated from `@onlyworlds/sdk` 4.42.2 and 14 for the amendment from 4.76.0 (two of them replace `refuse-version` and `era-overlap-down-later-start`), 30 calendars with 186 steps and the words and breakdown each one reads as, and 34 values a reader must refuse. The steps of the two LegendKeeper calendars (`v2-except-chain-gregorian`, `v2-offset-harptos`) were each checked against LegendKeeper's own reading of that day. A reader conforms when it passes every case.

Source: the TypeScript SDK's calendar kernel (`@onlyworlds/sdk` 4.42.2: `readCalendarConfig`, `breakdownStep`, `formatStep`), written from Atlas's calendar, which made the field. Amended 2026-10-25 (version 2: `except` and `offset` on an intercalary entry; an open era's end skips `down` eras), from a probe of LegendKeeper's own date arithmetic over its preset calendars (Gregorian, Harptos and Scrolls were the three that would not read exact) and an era-order fault found in two readers the same day.
