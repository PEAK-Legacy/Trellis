from peak import context
from peak.events import trellis
from peak.util import addons
from peak.util.extremes import Min, Max
import heapq, weakref, time

__all__ = [
    'Time', 'EPOCH', 'NOT_YET', 'EventLoop', 'WXEventLoop', 'TwistedEventLoop',
]

try:
    set
except NameError:
    from sets import Set as set
        


























class _Timer(object):
    """Value representing a moment in time"""

    __slots__ = '_when'

    def __init__(self, _when):
        self._when = _when

    def __getitem__(self, interval):
        """Get a timer that's offset from this one by `interval` seconds"""
        if self is NOT_YET: return self
        return _Timer(self._when + interval)

    def __sub__(self, other):
        """Get the interval in seconds between two timers"""
        if not isinstance(other, _Timer):
            raise TypeError("Can't subtract %r from timer" % (other,))
        return self._when - other._when

    def __eq__(self, other):
        if not isinstance(other, _Timer):
            return False
        return self._when == other._when

    def __ne__(self, other):
        return not self==other

    def __ge__(self, other):
        return not self < other

    def __nonzero__(self):
        return Time.reached(self)

    def __lt__(self, other):
        if not isinstance(other, _Timer):
            raise TypeError # for now
        return self._when < other._when

    def __hash__(self):
        return hash(self._when)

    def begins_with(self, flag):
        """Keep track of the moment when `flag` first becomes true"""
        if flag:
            return min(self, Time[0])
        return NOT_YET

EPOCH = _Timer(0)
NOT_YET = _Timer(Max)
    
































class EventLoop(trellis.Component, context.Service):
    """Run an application event loop"""

    trellis.values(
        running = False,
        stop_requested = False
    )
    trellis.rules(
        _call_queue = lambda self: []
    )

    def run(self):
        """Loop updating the time and invoking requested calls"""
        assert not self.running, "EventLoop is already running"
        queue = self._call_queue
        self.stop_requested = False
        self.running = True
        get_delay = Time.next_event_time
        try:
            while (queue or get_delay(True)) and not self.stop_requested:
                if queue:
                    f, args, kw = queue.pop(0)
                    f(*args, **kw)
                if not queue:
                    if Time.auto_update:
                        Time.tick()                                        
                    else:
                        Time.advance(get_delay(True) or 0)
        finally:
            self.running = False; self.stop_requested = False
            
    def stop(self):
        """Stop the event loop at the next opportunity"""
        assert self.running, "EventLoop isn't running"
        self.stop_requested = True

    def call(self, func, *args, **kw):
        """Call `func(*args, **kw)` at the next opportunity"""
        self._call_queue.append((func, args, kw))


class TwistedEventLoop(EventLoop):
    """Twisted version of the event loop"""

    context.replaces(EventLoop)    
    reactor = _delayed_call = None

    trellis.rules(
        _next_time = lambda self: Time.next_event_time(True)
    )

    def _ticker(self):
        if Time.auto_update and self.running:
            if self._next_time is not None:
                if self._delayed_call and self._delayed_call.active():
                    self._delayed_call.reset(self._next_time)
                else:
                    self._delayed_call = self.reactor.callLater(
                        self._next_time, Time.tick
                    )
    _ticker = trellis.rule(_ticker)

    def run(self):
        """Loop updating the time and invoking requested calls"""
        assert not self.running, "EventLoop is already running"
        if self.reactor is None:
            self.setup_reactor()
        self.stop_requested = False
        Time.tick()
        self.running = True
        try:
            self.reactor.run()
        finally:
            self.running = False
            self.stop_requested = False
            
    def stop(self):
        """Stop the event loop at the next opportunity"""
        assert self.running, "EventLoop isn't running"
        self.stop_requested = True
        self.reactor.stop()

    def call(self, func, *args, **kw):
        """Call `func(*args, **kw)` at the next opportunity"""
        if not self._call_queue:
            if self.reactor is None:
                self.setup_reactor()
                self.reactor.callLater(0, self._purge_queue)
        self._call_queue.append((func, args, kw))

    def _purge_queue(self):
        # twisted doesn't guarantee sequential callbacks, but this does...
        f, args, kw = self._call_queue.pop(0)
        f(*args, **kw)
        if self._call_queue:
            self.reactor.callLater(0, self._purge_queue)

    def setup_reactor(self):
        if self.reactor is None:
            from twisted.internet import reactor
            self.reactor = reactor






















class WXEventLoop(EventLoop):
    """wxPython version of the event loop

    This isn't adequately tested; the wx event loop is completely hosed when
    it comes to running without any windows, so it's basically impossible to
    unit test without mocking 'wx' (which I haven't tried to do.  Use at your
    own risk.  :(
    """
    context.replaces(EventLoop)    

    wx = _call_queue = None
    trellis.rules(
        _next_time = lambda self: Time.next_event_time(True)
    )
    def _ticker(self):
        if self.running:
            if Time.auto_update:
                if self._next_time is not None:
                    self.wx.FutureCall(self._next_time*1000, Time.tick)
    _ticker = trellis.rule(_ticker)

    def run(self):
        """Loop updating the time and invoking requested calls"""
        assert not self.running, "EventLoop is already running"
        if not self.wx:
            import wx
            self.wx = wx
        app = self.wx.GetApp()
        assert app is not None, "wx.App not created"
        self.running = True
        try:
            while not self.stop_requested:
                app.MainLoop()
                if app.ExitOnFrameDelete:   # handle case where windows exist
                    self.stop_requested = True
                else:
                    app.ProcessPendingEvents()  # ugh
        finally:
            self.running = False
            self.stop_requested = False

    def stop(self):
        """Stop the event loop at the next opportunity"""
        assert self.running, "EventLoop isn't running"
        self.stop_requested = True
        self.wx.GetApp().ExitMainLoop()

    def call(self, func, *args, **kw):
        """Call `func(*args, **kw)` at the next opportunity"""
        if not self.wx:
            import wx
            self.wx = wx
        self.wx.CallAfter(func, *args, **kw)





























class Time(trellis.Component, context.Service):
    """Manage current time and intervals"""

    trellis.values(
        _tick = EPOCH._when,
        auto_update = True
    )
    _now   = EPOCH._when

    trellis.rules(
        _schedule  = lambda self: [Max],
        _events    = lambda self: weakref.WeakValueDictionary(),
    )
    def _updated(self):
        if self._updated is None:
            updated = set()
        else:
            # Always return the same object, so this rule NEVER changes value!
            # This ensures that only the most-recently fired event rules recalc
            updated = self._updated
            updated.clear()

        while self._tick >= self._schedule[0]:
            key = heapq.heappop(self._schedule)
            if key in self._events:
                updated.add(key)
                self._events.pop(key).ensure_recalculation()
        return updated

    _updated = trellis.rule(_updated)   

    def reached(self, timer):
        when = timer._when
        if when not in self._events:
            if self._now >= when:
                return True
            heapq.heappush(self._schedule, when)
            self._events[when] = e = \
                trellis.Cell(lambda: e.value or when in self._updated, False)
        return self._events[when].value

    def __getitem__(self, interval):
        """Return a timer that's the given offset from the current time"""
        return _Timer(self._now + interval)

    def advance(self, interval):
        """Advance the current time by the given interval"""
        self._set(self._now + interval)

    def tick(self):
        """Update current time to match ``time.time()``"""
        self._set(self.time())

    def _set(self, when):
        self._now = when
        self._tick = when

    def _tick(self):
        if self.auto_update:
            tick = self._now = self.time()            
            trellis.poll()
            return tick
        return self._tick

    _tick = trellis.rule(_tick)

    def next_event_time(self, relative=False):
        """The time of the next event to occur, or ``None`` if none scheduled

        If `relative` is True, returns the number of seconds until the event;
        otherwise, returns the absolute ``time.time()`` of the event.
        """
        now = self._tick   # ensure recalc whenever time moves forward
        when = self._schedule[0]
        if when is Max:
            return None
        if relative:
            return when - now
        return when

    def time(self): return time.time()

