from peak import context
from peak.events import trellis
from peak.util import addons, decorators
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
        stop_requested = False, _call_queue = None
    )
    trellis.rules(
        _call_queue = lambda self: [],
        _next_time = lambda self: Time.next_event_time(True),
    )
    _callback_active = False

    def run(self):
        """Loop updating the time and invoking requested calls"""
        assert not self.running, "EventLoop is already running"
        assert not trellis.ctrl.active, "Event loop can't be run atomically"
        trellis.atomically(self._setup)
        self.stop_requested = False
        self.running = True
        try:
            self._loop()
        finally:
            self.running = False
            self.stop_requested = False
            
    def stop(self):
        """Stop the event loop at the next opportunity"""
        assert self.running, "EventLoop isn't running"
        self.stop_requested = True

    decorators.decorate(trellis.modifier)
    def call(self, func, *args, **kw):
        """Call `func(*args, **kw)` at the next opportunity"""
        self._call_queue.append((func, args, kw))
        self._setup()
        trellis.on_undo(self._call_queue.pop)
        self._callback_if_needed()



    def poll(self):
        """Execute up to a single pending call"""
        self.flush(1)

    def flush(self, count=0):
        """Execute the specified number of pending calls (0 for all)"""
        assert not trellis.ctrl.active, "Event loop can't be run atomically"
        queue = self._split_queue(count)
        for (f, args, kw) in queue:
            f(*args, **kw)
        self._callback_if_needed()
        if Time.auto_update:
            Time.tick()                                        
        else:
            Time.advance(self._next_time or 0)

    decorators.decorate(trellis.modifier)
    def _callback_if_needed(self):
        if self._call_queue and not self._callback_active:
            self._arrange_callback(self._callback)
            self._callback_active = True
        
    decorators.decorate(trellis.modifier)
    def _split_queue(self, count):
        queue = self._call_queue
        count = count or len(queue)
        if queue:
            head, self._call_queue = queue[:count], queue[count:]
            return head
        return ()

    def _callback(self):
        self._callback_active = False
        self.flush(1)







    def _loop(self):
        """Subclasses should invoke their external loop here"""
        queue = self._call_queue
        while (queue or self._next_time) and not self.stop_requested:
            self.flush(1)

    def _setup(self):
        """Subclasses should import/setup their external loop here

        Note: must be inherently thread-safe, or else use a cell attribute in
        order to benefit from locking.  This method is called atomically, but
        you should not log any undo actions."""

    def _arrange_callback(self, func):
        """Subclasses should register `func` to be called by external loop

        Note: Must be safe to call this from a 'foreign' thread."""
























class TwistedEventLoop(EventLoop):
    """Twisted version of the event loop"""

    context.replaces(EventLoop)    
    reactor = _delayed_call = None

    def _ticker(self):
        if self.running:
            if Time.auto_update:
                if self._next_time is not None:
                    if self._delayed_call and self._delayed_call.active():
                        self._delayed_call.reset(self._next_time)
                    else:
                        self._delayed_call = self.reactor.callLater(
                            self._next_time, Time.tick
                        )
            if self.stop_requested:
                self.reactor.stop()

    _ticker = trellis.observer(_ticker)

    def _loop(self):
        """Loop updating the time and invoking requested calls"""
        Time.tick()
        self.reactor.run()

    def _arrange_callback(self, func):
        self.reactor.callLater(0, func)

    def _setup(self):
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
    wx = None

    def _ticker(self):
        if self.running:
            if Time.auto_update:
                if self._next_time is not None:
                    self.wx.FutureCall(self._next_time*1000, Time.tick)
            if self.stop_requested:
                self.wx.GetApp().ExitMainLoop()
    _ticker = trellis.observer(_ticker)

    def _loop(self):
        """Loop updating the time and invoking requested calls"""
        app = self.wx.GetApp()
        assert app is not None, "wx.App not created"
        while not self.stop_requested:
            app.MainLoop()
            if app.ExitOnFrameDelete:   # handle case where windows exist
                self.stop_requested = True
            else:
                app.ProcessPendingEvents()  # ugh

    def _arrange_callback(self, func):
        """Call `func(*args, **kw)` at the next opportunity"""
        self.wx.CallAfter(func)
            
    def _setup(self):
        if not self.wx:
            import wx
            self.wx = wx


class Time(trellis.Component, context.Service):
    """Manage current time and intervals"""

    trellis.values(
        _tick = EPOCH._when,
        auto_update = True,
        _schedule = None,
    )
    _now   = EPOCH._when

    trellis.rules(
        _schedule = lambda self: [Max],
        _events = lambda self: weakref.WeakValueDictionary(),
    )
    def _updated(self):
        while self._tick >= self._schedule[0]:
            key = heapq.heappop(self._schedule)
            if key in self._events:
                self._events.pop(key).value = True

    _updated = trellis.rule(_updated)   

    def reached(self, timer):
        when = timer._when
        if when not in self._events:
            if self._now >= when:
                return True
            if trellis.ctrl.current_listener is not None:
                heapq.heappush(self._schedule, when)
                trellis.ctrl.changed(self.__cells__['_schedule'])
                self._events[when] = e = trellis.Value(False)
            else:
                return False
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
        trellis.change_attr(self, '_now', when)
        self._tick = when
    _set = trellis.modifier(_set)

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

