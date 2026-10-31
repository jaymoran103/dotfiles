"""preset_kit — the shared frame for a preset picker and editor.

A tool built on the kit keeps named presets for one thing, such as a
status line or a prompt. A preset says which elements show, in what
order, and the value of each setting. The kit gives every tool the same
command line, the same files and the same keys. A tool supplies its
elements, its built-in presets and a render function, and nothing else.

docs/preset-kit.md has the contract and a worked example.
"""

import json
import os
import re
import select
import sys
import termios
import tty

HOME = os.path.expanduser("~")
BOLD, DIM, REV = "\x1b[1m", "\x1b[2m", "\x1b[7m"
RED, GREEN, YELLOW = "\x1b[31m", "\x1b[32m", "\x1b[33m"
MIN_W, MIN_H = 64, 16
MAX_W, MAX_H = 120, 40   # a bigger window centres the frame, not stretch it


# --- what a tool supplies ---------------------------------------------------

class Element:
    """One thing a preset can show or set.

    kind "show" is in or out of the preset, and takes a place in its order.
    kind "choice" holds one of `choices`, and the first is its default.
    """

    def __init__(self, key, label, kind="show", choices=(), note=""):
        self.key, self.label, self.kind = key, label, kind
        self.choices, self.note = tuple(choices), note


class Tool:
    """Subclass this. Set the class fields and write render()."""

    name = ""           # the command; also names the config and state dirs
    title = ""          # a few words for the header
    elements = ()       # Elements, in the order the editor lists them
    builtins = {}       # preset name -> {"show": [keys], "set": {key: value}}
    default = "default"  # the built-in used when nothing is picked

    def render(self, preset, width):
        """Lines that show what the preset looks like. ANSI SGR is fine."""
        raise NotImplementedError

    def value(self, key):
        """Optional text beside an element in the editor, such as its
        current reading. Empty by default."""
        return ""

    # --- files ----------------------------------------------------------------
    # Presets of yours: ~/.config/<name>/presets/<preset>.json, which
    # install.sh links into dotfiles. The pick: ~/.local/state/<name>/active.

    @property
    def presets_dir(self):
        env = self.name.upper().replace("-", "_") + "_PRESETS_DIR"
        return os.environ.get(env) or os.path.join(HOME, ".config", self.name, "presets")

    @property
    def state_dir(self):
        base = os.environ.get("XDG_STATE_HOME") or os.path.join(HOME, ".local", "state")
        return os.path.join(base, self.name)

    def path(self, name):
        return os.path.join(self.presets_dir, name + ".json")

    def yours(self):
        try:
            files = os.listdir(self.presets_dir)
        except OSError:
            return []
        return sorted(f[:-5] for f in files if f.endswith(".json") and not f.startswith("."))

    def listing(self):
        """(name, source) pairs. Built-ins first, in their own order. A preset
        of yours with a built-in's name hides it, and its source is
        "changed"."""
        mine = self.yours()
        out = [(n, "changed" if n in mine else "built-in") for n in self.builtins]
        return out + [(n, "yours") for n in mine if n not in self.builtins]

    def source(self, name):
        return dict(self.listing()).get(name)

    def load(self, name):
        try:
            with open(self.path(name)) as f:
                return self.clean(json.load(f))
        except (OSError, ValueError):
            pass
        if name in self.builtins:
            return self.clean(self.builtins[name])
        return None

    def clean(self, preset):
        """Drop keys the tool no longer has and fill unset choices, so an old
        file still loads after the tool changes."""
        kinds = {e.key: e for e in self.elements}
        show = [k for k in preset.get("show", []) if k in kinds and kinds[k].kind == "show"]
        sets = dict(preset.get("set", {}))
        out = {}
        for e in self.elements:
            if e.kind == "choice":
                out[e.key] = sets.get(e.key) if sets.get(e.key) in e.choices else e.choices[0]
        return {"show": list(dict.fromkeys(show)), "set": out}

    def save(self, name, preset):
        os.makedirs(self.presets_dir, exist_ok=True)
        tmp = self.path(name) + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.clean(preset), f, indent=2)
            f.write("\n")
        os.replace(tmp, self.path(name))

    def delete(self, name):
        try:
            os.remove(self.path(name))
        except OSError:
            pass

    def active(self):
        try:
            with open(os.path.join(self.state_dir, "active")) as f:
                name = f.read().strip()
        except OSError:
            name = ""
        return name if self.source(name) else self.default

    def set_active(self, name):
        os.makedirs(self.state_dir, exist_ok=True)
        if name == self.default:
            try:
                os.remove(os.path.join(self.state_dir, "active"))
            except OSError:
                pass
            return
        with open(os.path.join(self.state_dir, "active"), "w") as f:
            f.write(name + "\n")

    def active_preset(self):
        return self.load(self.active()) or self.clean(self.builtins[self.default])


# --- the command line ---------------------------------------------------------

USAGE = """\
  {n}               picker and editor
  {n} <preset>      use <preset>
  {n} -l            list presets
  {n} -s            say which preset is in use
  {n} -r            go back to {d}
  {n} --print [p]   draw a preset, or the one in use
  {n} --save NAME   keep the preset in use as NAME"""


def main(tool, argv):
    """Exit 0 done, 1 unknown preset or bad name, 2 usage error."""
    def die(msg, code=1):
        sys.stderr.write(f"{tool.name}: {msg}\n")
        sys.exit(code)

    a = argv[0] if argv else None
    if a in ("-h", "--help"):
        print(f"{tool.name} — {tool.title}\n\n" + USAGE.format(n=tool.name, d=tool.default))
    elif a in ("-l", "--list"):
        on = tool.active()
        for name, src in tool.listing():
            print(f"{'•' if name == on else ' '} {name:<20} {src}")
    elif a in ("-s", "--status"):
        print(f"{tool.active()} · {tool.source(tool.active())}")
    elif a in ("-r", "--reset"):
        tool.set_active(tool.default)
        print(tool.default)
    elif a == "--print":
        name = argv[1] if len(argv) > 1 else tool.active()
        preset = tool.load(name) or die(f"no preset '{name}' (try -l)")
        width = shutil_width()
        for line in tool.render(preset, width):
            print(line if sys.stdout.isatty() else SGR.sub("", line))
    elif a == "--save":
        name = argv[1] if len(argv) > 1 else die("--save needs a name", 2)
        bad = name_problem(tool, name)
        if bad:
            die(bad)
        tool.save(name, tool.active_preset())
        print(f"saved {tool.path(name).replace(HOME, '~', 1)}")
    elif a and a.startswith("-"):
        die(f"unknown option {a} (try -h)", 2)
    elif a:
        if not tool.source(a):
            die(f"no preset '{a}' (try -l)")
        tool.set_active(a)
        print(a)
    else:
        if not os.isatty(sys.stdout.fileno()):
            die("the picker needs a terminal", 2)
        App(tool).run()


def shutil_width():
    try:
        return os.get_terminal_size(sys.stdout.fileno()).columns
    except OSError:
        return 1000   # a pipe gets the whole line


def name_problem(tool, name):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name or ""):
        return "use letters, digits, dot, dash or underscore"
    if tool.source(name):
        return f"{name} already exists"
    return None


# --- drawing --------------------------------------------------------------------

SGR = re.compile(r"\x1b\[[0-9;]*m")


class Canvas:
    """A grid of (char, style) cells, flushed in one write so nothing tears."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.cells = [[(" ", "")] * w for _ in range(h)]

    def put(self, y, x, text, style="", limit=None):
        if not 0 <= y < self.h:
            return
        if limit is not None:
            text = text[:max(0, limit)]
        row = self.cells[y]
        for i, ch in enumerate(text):
            if 0 <= x + i < self.w:
                row[x + i] = (ch, style)

    def put_ansi(self, y, x, line, limit):
        """Text with SGR escapes in it, as a tool's render() returns."""
        style, i = "", 0
        for part in re.split(r"(\x1b\[[0-9;]*m)", line):
            if SGR.fullmatch(part):
                style = "" if part in ("\x1b[0m", "\x1b[m") else style + part
                continue
            self.put(y, x + i, part, style, limit=limit - i)
            i += len(part)

    def centred(self, w, h):
        big = Canvas(w, h)
        oy, ox = (h - self.h) // 2, (w - self.w) // 2
        for y, row in enumerate(self.cells):
            big.cells[oy + y][ox:ox + self.w] = row
        return big

    def render(self):
        out = ["\x1b[H"]
        for y, row in enumerate(self.cells):
            style = None
            for ch, st in row:
                if st != style:
                    out.append("\x1b[0m" + st)
                    style = st
                out.append(ch)
            out.append("\x1b[0m")
            if y < self.h - 1:
                out.append("\r\n")
        return "".join(out)


def box(c, y, x, w, h, title, on, fill=False):
    st = "" if on else DIM
    c.put(y, x, "╭" + "─" * (w - 2) + "╮", st)
    for r in range(y + 1, y + h - 1):
        c.put(r, x, "│", st)
        if fill:
            c.put(r, x + 1, " " * (w - 2))
        c.put(r, x + w - 1, "│", st)
    c.put(y + h - 1, x, "╰" + "─" * (w - 2) + "╯", st)
    c.put(y, x + 2, f" {title} ", st + (BOLD if on else ""), limit=w - 4)


# --- keys -----------------------------------------------------------------------

SEQ = {"[A": "up", "[B": "down", "[C": "right", "[D": "left",
       "OA": "up", "OB": "down", "OC": "right", "OD": "left",
       "[1;2A": "S-up", "[1;2B": "S-down", "[1;2C": "right", "[1;2D": "left"}
PLAIN = {"\r": "enter", "\n": "enter", "\x7f": "bs", "\x08": "bs", "\x03": "ctrl-c", " ": "space"}
CSI = re.compile(r"\x1b(\[[0-9;]*[A-Za-z~]|O[A-Za-z])")


def keys(data):
    s, i = data.decode("utf-8", "ignore"), 0
    while i < len(s):
        m = CSI.match(s, i)
        if m:
            yield SEQ.get(m.group(1), "")
            i = m.end()
            continue
        yield "esc" if s[i] == "\x1b" else PLAIN.get(s[i], s[i])
        i += 1


HELP = {
    "list": (("↑↓", "move"), ("enter", "use it"), ("e →", "edit"), ("n", "new from this"),
             ("⌫ ⌫", "delete yours"), ("q esc", "quit")),
    "edit": (("↑↓", "move"), ("space", "show or hide"), ("←→", "change a setting"),
             ("⇧↑↓ K J", "reorder"), ("z  y", "undo  redo"), ("⌫ ⌫", "undo all"),
             ("esc ←", "back"), ("", "changes save as you go")),
}
HINTS = {
    "list": "↑↓ move · enter use · e edit · n new · ? keys",
    "edit": "space show/hide · ⇧↑↓ reorder · z undo · esc back · ? keys",
}


# --- the app ----------------------------------------------------------------------

class App:
    """Two levels. The list of presets, with the hovered one drawn on the
    right. Then the editor for one preset. Edits save as they happen, so esc
    only goes back. Undo all and delete are armed: ⌫ once says what goes."""

    def __init__(self, tool):
        self.t = tool
        self.tty = os.open("/dev/tty", os.O_RDWR)
        self.mode, self.done = "list", False
        self.rows = tool.listing()
        names = [n for n, _ in self.rows]
        self.li = names.index(tool.active()) if tool.active() in names else 0
        self.loff = self.ei = self.eoff = 0
        self.name = self.preset = None
        self.undo, self.redo, self.first = [], [], None
        self.prompt = self.msg = self.armed = None
        self.help = False

    def out(self, s):
        os.write(self.tty, s.encode())

    def say(self, text, style=""):
        self.msg = (text, style)

    def hovered(self):
        return self.rows[self.li][0]

    # --- editor rows ------------------------------------------------------------
    # Shown elements in their order, then hidden ones, then the settings.

    def erows(self):
        show = self.preset["show"]
        hidden = [e.key for e in self.t.elements if e.kind == "show" and e.key not in show]
        sets = [e.key for e in self.t.elements if e.kind == "choice"]
        return show + hidden + sets

    def element(self, key):
        return next(e for e in self.t.elements if e.key == key)

    # --- actions ----------------------------------------------------------------

    def use(self):
        name = self.hovered()
        self.t.set_active(name)
        self.say(f"✓ in use · {name} · sessions pick it up on their next refresh", GREEN)

    def open(self, name):
        self.name, self.preset = name, self.t.load(name)
        self.first = json.dumps(self.preset)
        self.was_builtin = self.t.source(name) == "built-in"
        self.undo, self.redo = [], []
        self.mode, self.ei, self.eoff = "edit", 0, 0

    def change(self, fn):
        before = json.dumps(self.preset)
        fn(self.preset)
        if json.dumps(self.preset) == before:
            return
        self.undo.append(before)
        self.redo = []
        self.store()

    def store(self):
        if self.was_builtin and json.dumps(self.preset) == self.first:
            self.t.delete(self.name)          # back to the built-in exactly
            self.say("✓ saved · same as the built-in", GREEN)
            return
        try:
            self.t.save(self.name, self.preset)
            self.say("✓ saved", GREEN)
        except OSError as e:
            self.say(f"save failed: {e.strerror}", RED)

    def step(self, src, dst):
        if not src:
            self.say("nothing to " + ("undo" if src is self.undo else "redo"), DIM)
            return
        dst.append(json.dumps(self.preset))
        self.preset = json.loads(src.pop())
        self.store()

    def new_from(self, base):
        def make(name):
            bad = name_problem(self.t, name.strip())
            if bad:
                self.say(bad, RED)
                return
            self.t.save(name.strip(), self.t.load(base))
            self.rows = self.t.listing()
            self.li = [n for n, _ in self.rows].index(name.strip())
            self.open(name.strip())
            self.say(f"✓ new preset {name.strip()}", GREEN)
        n = 2
        while self.t.source(f"{base}-{n}"):
            n += 1
        self.prompt = ["new preset", f"{base}-{n}", make]

    # --- keys -------------------------------------------------------------------

    def key(self, k):
        if k == "ctrl-c":
            self.done = True
            return
        if self.prompt:
            self.prompt_key(k)
            return
        if self.help:
            self.help = False
            if k in ("?", "esc"):
                return
        armed, self.armed, self.msg = self.armed, None, None
        if k == "?":
            self.help = True
            return
        k = {"k": "up", "j": "down", "K": "S-up", "J": "S-down"}.get(k, k)
        getattr(self, "key_" + self.mode)(k, armed)

    def prompt_key(self, k):
        label, text, then = self.prompt
        if k == "esc":
            self.prompt = None
        elif k == "enter":
            self.prompt = None
            then(text)
        elif k == "bs":
            self.prompt[1] = text[:-1]
        elif k == "space":
            self.prompt[1] = text + "-"
        elif len(k) == 1 and k.isprintable():
            self.prompt[1] = text + k

    def key_list(self, k, armed):
        name, src = self.rows[self.li]
        if k in ("up", "down"):
            self.li = (self.li + (1 if k == "down" else -1)) % len(self.rows)
        elif k == "enter":
            self.use()
        elif k in ("e", "right"):
            self.open(name)
        elif k == "n":
            self.new_from(name)
        elif k == "bs":
            if src == "built-in":
                self.say("built in · nothing to delete", DIM)
            elif armed != "bs":
                self.armed = "bs"
                then = "brings back the built-in" if src == "changed" else "deletes it"
                self.say(f"⌫ again {then} · {name}", RED)
            else:
                # A deleted pick falls back to the default by itself.
                self.t.delete(name)
                self.rows = self.t.listing()
                self.li = min(self.li, len(self.rows) - 1)
                self.say(f"✓ {'built-in back' if src == 'changed' else 'deleted'} · {name}", GREEN)
        elif k in ("q", "esc"):
            self.done = True

    def key_edit(self, k, armed):
        rows = self.erows()
        key = rows[self.ei]
        e = self.element(key)
        show = self.preset["show"]
        if k in ("up", "down"):
            self.ei = (self.ei + (1 if k == "down" else -1)) % len(rows)
        elif k in ("space", "enter") and e.kind == "show":
            self.change(lambda p: p["show"].remove(key) if key in p["show"] else p["show"].append(key))
            self.ei = self.erows().index(key)
        elif k in ("space", "enter", "left", "right") and e.kind == "choice":
            i = e.choices.index(self.preset["set"][key])
            i = (i + (-1 if k == "left" else 1)) % len(e.choices)
            self.change(lambda p: p["set"].__setitem__(key, e.choices[i]))
        elif k in ("S-up", "S-down") and key in show:
            j = show.index(key) + (1 if k == "S-down" else -1)
            if 0 <= j < len(show):
                def swap(p):
                    s = p["show"]
                    i = s.index(key)
                    s[i], s[j] = s[j], s[i]
                self.change(swap)
                self.ei = self.erows().index(key)
        elif k == "z":
            self.step(self.undo, self.redo)
        elif k == "y":
            self.step(self.redo, self.undo)
        elif k == "bs":
            if json.dumps(self.preset) == self.first:
                self.say("nothing to undo", DIM)
            elif armed != "bs":
                self.armed = "bs"
                self.say(f"⌫ again undoes every change since you opened {self.name}", RED)
            else:
                self.undo.append(json.dumps(self.preset))
                self.preset = json.loads(self.first)
                self.store()
                self.say(f"✓ back to how {self.name} was when you opened it", GREEN)
        elif k in ("esc", "left", "q"):
            self.mode = "list"
            self.rows = self.t.listing()
            self.li = [n for n, _ in self.rows].index(self.name)

    # --- layout -----------------------------------------------------------------

    def draw(self):
        tw, th = os.get_terminal_size(self.tty)
        w, h = min(tw, MAX_W), min(th, MAX_H)
        c = Canvas(w, h)
        if w < MIN_W or h < MIN_H:
            c.put(h // 2, 2, f"make the window at least {MIN_W}×{MIN_H} · now {w}×{h}", DIM)
            self.out(c.render())
            return
        lw = max(30, min(40, w * 2 // 5))
        bh = h - 2
        self.draw_header(c, w)
        box(c, 1, 0, lw, bh, "presets" if self.mode == "list" else self.name, True)
        box(c, 1, lw, w - lw, bh, "preview", False)
        inner = (2, 1, lw - 2, bh - 2)
        if self.mode == "list":
            self.draw_list(c, *inner)
            preset = self.t.load(self.hovered())
        else:
            self.draw_edit(c, *inner)
            preset = self.preset
        pw = w - lw - 4
        lines = self.t.render(preset, pw)
        for i, line in enumerate(lines[:bh - 2]):
            c.put_ansi(2 + i, lw + 2, line, pw)
        if self.mode == "list":
            self.draw_shows(c, 2 + len(lines) + 1, lw + 2, pw, bh - len(lines) - 3, preset)
        self.draw_footer(c, w, h - 1)
        if self.help:
            self.draw_help(c, w, h)
        self.out(c.centred(tw, th).render())

    def draw_header(self, c, w):
        c.put(0, 1, self.t.name, BOLD)
        x = len(self.t.name) + 3
        c.put(0, x, self.t.title, DIM, limit=w - x - 30)
        right = f"in use · {self.t.active()} "
        c.put(0, w - len(right), right, DIM)

    def draw_list(self, c, y, x, w, h):
        on = self.t.active()
        self.loff = max(min(self.loff, self.li), self.li - h + 1)
        for r in range(min(h, len(self.rows) - self.loff)):
            i = self.loff + r
            name, src = self.rows[i]
            mark = "•" if name == on else " "
            text = f"{mark} {name}".ljust(w - 10)[:w - 10]
            c.put(y + r, x + 1, text, REV if i == self.li else "")
            c.put(y + r, x + w - 9, src.rjust(8), DIM)

    def draw_edit(self, c, y, x, w, h):
        rows = self.erows()
        show = self.preset["show"]
        self.eoff = max(min(self.eoff, self.ei), self.ei - h + 1)
        for r in range(min(h, len(rows) - self.eoff)):
            i = self.eoff + r
            e = self.element(rows[i])
            on = i == self.ei
            if e.kind == "choice":
                mark, text = "·", f"{e.label}  ‹ {self.preset['set'][e.key]!r} ›"
                st = ""
            else:
                lit = e.key in show
                mark = f"{show.index(e.key) + 1:>2}" if lit else "  "
                text, st = e.label, "" if lit else DIM
            c.put(y + r, x + 1, mark, DIM)
            c.put(y + r, x + 4, text.ljust(w - 5)[:w - 5], (REV if on else "") + st)
            note = e.note or self.t.value(e.key)
            if note and len(text) + len(note) + 3 < w - 5:
                c.put(y + r, x + w - 1 - len(note), note, DIM)

    def draw_shows(self, c, y, x, w, h, preset):
        """What the hovered preset shows, in order, with each one's reading."""
        rows = [(f"{i + 1:>2}", self.element(k)) for i, k in enumerate(preset["show"])]
        rows += [(" ·", e) for e in self.t.elements if e.kind == "choice"]
        if h < 2 or not rows:
            return
        c.put(y, x, "shows", DIM)
        for r, (mark, e) in enumerate(rows[:h - 1]):
            val = repr(preset["set"][e.key]) if e.kind == "choice" else self.t.value(e.key)
            c.put(y + 1 + r, x, mark, DIM)
            c.put(y + 1 + r, x + 3, e.label, limit=w - 3)
            c.put(y + 1 + r, x + 24, val, DIM, limit=w - 24)

    def draw_footer(self, c, w, y):
        if self.prompt:
            label, text, _ = self.prompt
            c.put(y, 1, f"{label} › ", BOLD)
            c.put(y, len(label) + 4, text)
            c.put(y, len(label) + 4 + len(text), " ", REV)
            c.put(y, w - 22, "enter ok · esc cancel", DIM)
        elif self.msg:
            c.put(y, 1, self.msg[0], self.msg[1], limit=w - 2)
        else:
            c.put(y, 1, HINTS[self.mode], DIM, limit=w - 2)

    def draw_help(self, c, w, h):
        items = HELP[self.mode]
        bw = max(len(a) + len(b) for a, b in items) + 8
        bh = len(items) + 2
        y, x = (h - bh) // 2, (w - bw) // 2
        box(c, y, x, bw, bh, "keys", True, fill=True)
        for i, (k, what) in enumerate(items):
            c.put(y + 1 + i, x + 2, k.ljust(bw - 4 - len(what)), BOLD)
            c.put(y + 1 + i, x + bw - 2 - len(what), what, DIM if not k else "")

    # --- loop -------------------------------------------------------------------

    def run(self):
        old = termios.tcgetattr(self.tty)
        self.out("\x1b[?1049h\x1b[?25l\x1b[?7l")
        tty.setraw(self.tty)
        try:
            size, stale = None, True
            while not self.done:
                now = os.get_terminal_size(self.tty)
                if stale or now != size:
                    self.draw()
                    size, stale = now, False
                if select.select([self.tty], [], [], 0.25)[0]:
                    for k in keys(os.read(self.tty, 1024)):
                        self.key(k)
                        if self.done:
                            break
                    stale = True
        finally:
            termios.tcsetattr(self.tty, termios.TCSADRAIN, old)
            self.out("\x1b[?7h\x1b[?25h\x1b[?1049l")
            os.close(self.tty)
