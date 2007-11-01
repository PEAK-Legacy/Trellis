from peak import context
from peak.events import trellis
import heapq, weakref, time

__all__ = [
    'Time', 'EPOCH', 'NOT_YET'
]

class _ExtremeType(object):     # Courtesy of PEP 326
    def __init__(self, cmpr, rep):
        object.__init__(self)
        self._cmpr = cmpr
        self._rep = rep

    def __cmp__(self, other):
        if isinstance(other, self.__class__) and\
           other._cmpr == self._cmpr:
            return 0
        return self._cmpr

    def __repr__(self):
        return self._rep

    def __lt__(self,other):
        return self.__cmp__(other)<0

    def __le__(self,other):
        return self.__cmp__(other)<=0

    def __gt__(self,other):
        return self.__cmp__(other)>0

    def __eq__(self,other):
        return self.__cmp__(other)==0

    def __ge__(self,other):
        return self.__cmp__(other)>=0

    def __ne__(self,other):
        return self.__cmp__(other)<>0
        
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

Max = _ExtremeType(1, "Max")
Min = _ExtremeType(-1, "Min")

NOT_YET = _Timer(Max)
    




























class Time(trellis.Component, context.Service):
    """Manage current time and intervals"""

    _tick = trellis.value(EPOCH._when)
    auto_update = trellis.value(True)
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
        self._set(time.time())

    def _set(self, when):
        self._now = when
        self._tick = when

    def _tick(self):
        if self.auto_update:
            tick = self._now = time.time()            
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



