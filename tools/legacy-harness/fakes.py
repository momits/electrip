"""Stand-ins for GTK, GObject, pygame and threading so that the logic in
legacy/ runs headless and deterministic on a virtual clock.

Only what legacy/src/electrip/control_ui.py and pygame_io.py use is faked.
The pygame mixer follows pygame 1.9.4 (src/mixer.c) on top of SDL_mixer:
a channel holds a current sound and at most one queued sound, and every end
of playback (natural end, halt, replacement by play) posts the channel's end
event and starts the queued sound.
"""

import heapq
import itertools
import sys
import threading
import types
from collections import deque

# Real time base for time.time(): Loco computes its acceleration from the
# difference to its last update, which starts at 0 like in Electrip 1.
EPOCH = 1_000_000_000.0


def to_us(seconds):
    return round(seconds * 1_000_000)


class Loop:
    """GLib main loop on a virtual clock in microseconds.

    Timers, idle callbacks and fake threads run strictly one after another,
    so a run depends only on the inputs.
    """

    def __init__(self):
        self.now = 0
        self.timers = []
        self.seq = itertools.count()
        self.idle = deque()
        self.ready = deque()
        self.sources = set()
        self.ids = itertools.count(1)
        self.back = threading.Semaphore(0)
        self.pump = None
        self.errors = []

    def time(self):
        return EPOCH + self.now / 1_000_000

    def at(self, t, fn):
        heapq.heappush(self.timers, (t, next(self.seq), fn))

    def timeout_add(self, ms, fn, *args):
        source = next(self.ids)
        self.sources.add(source)

        def fire():
            if source in self.sources:
                if fn(*args):
                    self.at(self.now + ms * 1000, fire)
                else:
                    self.sources.discard(source)

        self.at(self.now + ms * 1000, fire)
        return source

    def idle_add(self, fn, *args):
        source = next(self.ids)
        self.sources.add(source)
        self.idle.append((source, fn, args))
        return source

    def source_remove(self, source):
        self.sources.discard(source)
        return True

    def run_until(self, end):
        while True:
            self.settle()
            if not self.timers or self.timers[0][0] > end:
                break
            self.now, _, fn = heapq.heappop(self.timers)
            fn()
        self.now = end

    def settle(self):
        """Runs ready threads, pygame events and idle callbacks until
        nothing is left at the current instant."""
        for _ in range(100_000):
            if self.ready:
                thread = self.ready.popleft()
                thread.go.release()
                self.back.acquire()
            elif self.pump and Pygame.events:
                self.pump()
            elif self.idle:
                source, fn, args = self.idle.popleft()
                if source in self.sources:
                    if fn(*args):
                        self.idle.append((source, fn, args))
                    else:
                        self.sources.discard(source)
            else:
                return
        raise RuntimeError("main loop does not settle at t=%d us" % self.now)


LOOP = Loop()
_current = threading.local()


class Thread:
    """threading.Thread that runs only while the main loop waits for it."""

    def __init__(self, target=None):
        # EventHandlerThread.__init__ calls this without a target.
        self.target = target
        self.go = threading.Semaphore(0)
        self.token = None

    def start(self):
        threading.Thread(target=self._body, daemon=True).start()
        LOOP.ready.append(self)

    def _body(self):
        self.go.acquire()
        _current.thread = self
        try:
            self.target()
        except Exception as e:  # reported by the harness after the run
            LOOP.errors.append(repr(e))
        LOOP.back.release()

    def block(self):
        LOOP.back.release()
        self.go.acquire()


class Event:
    """threading.Event whose timeouts run on the virtual clock."""

    def __init__(self):
        self.flag = False
        self.waiters = []

    def is_set(self):
        return self.flag

    def set(self):
        self.flag = True
        for thread in self.waiters:
            thread.token = None
            LOOP.ready.append(thread)
        self.waiters = []

    def clear(self):
        self.flag = False

    def wait(self, timeout):
        if self.flag:
            return True
        thread = getattr(_current, "thread", None)
        if thread is None:
            raise RuntimeError("Event.wait outside a fake thread")
        token = thread.token = object()
        self.waiters.append(thread)
        LOOP.at(LOOP.now + to_us(timeout), lambda: self._expire(thread, token))
        thread.block()
        return self.flag

    def _expire(self, thread, token):
        if thread.token is token:
            thread.token = None
            self.waiters.remove(thread)
            LOOP.ready.append(thread)


threading_module = types.SimpleNamespace(Thread=Thread, Event=Event)
time_module = types.SimpleNamespace(time=LOOP.time)


# ---------------------------------------------------------------- GObject


class GObjectBase:
    def __init__(self, *args, **kwargs):
        pass

    def _handlers(self):
        return self.__dict__.setdefault("_handler_list", [])

    def connect(self, signal, fn, *data):
        handler = next(LOOP.ids)
        self._handlers().append((handler, signal, fn, data))
        return handler

    def disconnect(self, handler):
        self.__dict__["_handler_list"] = [h for h in self._handlers() if h[0] != handler]

    def emit(self, signal, *args):
        for handler in list(self._handlers()):
            if handler[1] == signal and handler in self._handlers():
                handler[2](self, *args, *handler[3])


class _Names(type):
    """Enum stand-in: any attribute is its own name."""

    def __getattr__(cls, name):
        return name


class Enum(metaclass=_Names):
    pass


class Widget(GObjectBase):
    sensitive = True

    @classmethod
    def new(cls, *args):
        return cls(*args)

    def set_sensitive(self, value):
        self.sensitive = value

    def get_sensitive(self):
        return self.sensitive


def _noop(*args, **kwargs):
    return Widget()


for _name in """add add_with_viewport attach get_allocation get_hadjustment
        hide queue_draw remove set_column_spacing set_digits set_ellipsize
        set_fill_level set_from_pixbuf set_from_stock set_halign set_hexpand
        set_inverted set_label set_label_align set_label_widget
        set_margin_bottom set_margin_top set_name set_orientation set_property
        set_restrict_to_fill_level set_row_spacing set_show_fill_level
        set_size_request set_text set_tooltip_text set_valign set_value_pos
        set_vexpand set_width_chars show show_all start stop
        add_widget get_style_context add_class remove_class""".split():
    setattr(Widget, _name, _noop)


class Adjustment:
    def __init__(self, value, lower, upper, step, page, page_size):
        self.lower = lower
        self.upper = upper - page_size


class Scale(Widget):
    value = 0.0
    adjustment = Adjustment(0, 0, 1, 0, 0, 0)

    def set_adjustment(self, adjustment):
        self.adjustment = adjustment

    def get_value(self):
        return self.value

    def set_value(self, value):
        value = min(max(value, self.adjustment.lower), self.adjustment.upper)
        if value != self.value:
            self.value = value
            self.emit("value-changed")

    def get_fill_level(self):
        return 0


class ToggleButton(Widget):
    active = False

    def get_active(self):
        return self.active

    def set_active(self, active):
        if active != self.active:
            self.active = active
            self.emit("toggled")
            self.emit("notify::active", None)

    def clicked(self):
        # The class handler of "clicked" toggles before user handlers run.
        self.set_active(not self.active)
        self.emit("clicked")


def _module(name, **attrs):
    module = types.ModuleType(name)
    module.__dict__.update(attrs)
    return module


class GError(Exception):
    pass


def install_gi():
    gobject = _module(
        "GObject",
        GObject=GObjectBase,
        SIGNAL_RUN_FIRST=1,
        SIGNAL_RUN_LAST=2,
        timeout_add=LOOP.timeout_add,
        idle_add=LOOP.idle_add,
        source_remove=LOOP.source_remove,
    )
    widgets = {n: type(n, (Widget,), {}) for n in
               "Frame Grid Label Image EventBox ScrolledWindow SizeGroup Spinner".split()}
    gtk = _module("Gtk", Adjustment=Adjustment, Scale=Scale, ToggleButton=ToggleButton,
                  STOCK_MISSING_IMAGE="missing", **widgets)
    for enum in "Orientation Align PositionType IconSize SizeGroupMode".split():
        setattr(gtk, enum, Enum)
    glib = _module("gi.repository.GLib", GError=GError)
    repository = _module("gi.repository", GObject=gobject, Gtk=gtk, GLib=glib,
                         Pango=_module("Pango", EllipsizeMode=Enum),
                         GdkPixbuf=_module("GdkPixbuf", Pixbuf=Enum, InterpType=Enum))
    sys.modules["gi"] = _module("gi", repository=repository)
    sys.modules["gi.repository"] = repository
    sys.modules["gi.repository.GLib"] = glib


# ----------------------------------------------------------------- pygame

# Event types of pygame 1.9 (SDL 1.2).
JOYAXISMOTION, JOYHATMOTION, JOYBUTTONDOWN, JOYBUTTONUP = 7, 9, 10, 11


class Sound:
    def __init__(self, name, length):
        self.name = name
        self.length = length

    def set_volume(self, volume):
        pass

    def get_length(self):
        return self.length

    def fadeout(self, ms):
        # Mix_FadeOutGroup: all channels that play this sound.
        for channel in Mixer.channels.values():
            if channel.playing and channel.sound is self:
                channel.fade_out(ms)


class Channel:
    """pygame.mixer.Channel per pygame 1.9.4 and SDL_mixer.

    Playback ends in three ways. A natural end or a finished fade-out calls
    pygame's endsound_callback with the channel already silent: it posts the
    end event and starts the queued sound. Halting (stop, or play on a busy
    channel) calls it while the channel still plays: pygame then starts the
    queued sound, SDL_mixer ends it again at once with a second end event,
    and the channel ends up silent with an empty queue.
    """

    def __init__(self, nr):
        self.nr = nr
        self.sound = None  # pygame's channeldata.sound
        self.queued = None
        self.playing = False
        self.fading = False
        self.endevent = None
        self.end = 0
        self.run = 0  # invalidates timers of earlier playback

    def set_endevent(self, event_type):
        self.endevent = event_type

    def get_busy(self):
        return self.playing

    def get_sound(self):
        return self.sound

    def play(self, sound, fade_ms=0):
        if self.playing:
            self._halt("replaced")
        self._start(sound, fade_ms)

    def queue(self, sound):
        if self.sound is None:
            self._start(sound)
        else:
            self.queued = sound

    def stop(self):
        if self.playing:
            self._halt("stop")

    def fade_out(self, ms):
        if not self.fading:
            self.fading = True
            Mixer.log(self, "fade_out", ms=ms)
            end = LOOP.now + ms * 1000
            if end < self.end:
                self._at(end, "faded")

    def _start(self, sound, fade_ms=0):
        self.sound = sound
        self.queued = None
        self.playing = True
        self.fading = False
        self.end = LOOP.now + to_us(sound.length)
        self._at(self.end, "end")
        Mixer.log(self, "start", **({"fade_in_ms": fade_ms} if fade_ms else {}))

    def _at(self, t, how):
        self.run += 1
        run = self.run
        LOOP.at(t, lambda: run == self.run and self._ended(how))

    def _ended(self, how):
        Mixer.log(self, how)
        self.playing = False
        self.run += 1
        self._post()
        if self.queued:
            self._start(self.queued)
        else:
            self.sound = None

    def _halt(self, how):
        Mixer.log(self, how)
        self.playing = False
        self.run += 1
        self._post()
        if self.queued:
            self._post()
        self.sound = self.queued = None

    def _post(self):
        if self.endevent:
            Pygame.events.append(types.SimpleNamespace(type=self.endevent))


class Mixer:
    channels = {}
    lengths = {}
    record = None

    @staticmethod
    def Channel(nr):
        return Mixer.channels.setdefault(nr, Channel(nr))

    @staticmethod
    def Sound(path):
        return Sound(path, Mixer.lengths[path])

    @staticmethod
    def log(channel, what, **extra):
        Mixer.record(dict(ch=channel.nr, sound=channel.sound.name, ev=what, **extra))


class Joystick:
    axes = {}

    def __init__(self, nr):
        self.nr = nr

    def init(self):
        pass

    def get_id(self):
        return self.nr

    def get_name(self):
        return "virtual gamepad"

    def get_numaxes(self):
        return 4

    def get_numbuttons(self):
        return 12

    def get_axis(self, axis):
        return Joystick.axes.get(axis, 0.0)


class Pygame:
    events = deque()

    @staticmethod
    def wait():
        # An empty queue ends EventHandlerThread.run.
        from electrip.constants import STOP_EVENT

        return Pygame.events.popleft() if Pygame.events else types.SimpleNamespace(type=STOP_EVENT)

    @staticmethod
    def post(event):
        Pygame.events.append(event)


def install_pygame():
    noop = _noop
    locals_ = _module("pygame.locals", JOYAXISMOTION=JOYAXISMOTION, JOYHATMOTION=JOYHATMOTION,
                      JOYBUTTONDOWN=JOYBUTTONDOWN, JOYBUTTONUP=JOYBUTTONUP)
    mixer = _module("pygame.mixer", Channel=Mixer.Channel, Sound=Mixer.Sound,
                    pre_init=noop, set_num_channels=noop, quit=noop)
    joystick = _module("pygame.joystick", init=noop, get_count=lambda: 1, Joystick=Joystick)
    event = _module("pygame.event", wait=Pygame.wait, post=Pygame.post,
                    Event=lambda event_type, **kw: types.SimpleNamespace(type=event_type, **kw))
    pygame = _module("pygame", init=noop, error=Exception, mixer=mixer, joystick=joystick,
                     event=event, locals=locals_)
    sys.modules.update({"pygame": pygame, "pygame.locals": locals_, "pygame.mixer": mixer})
