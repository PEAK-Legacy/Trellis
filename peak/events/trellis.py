from peak.context import Service, get_ident, InputConflict
from peak.util.symbols import NOT_GIVEN
from weakref import ref

_states = {}
_sentinel = NOT_GIVEN   # XXX should get our own symbol for this


def current_pulse():
    return _states.setdefault(get_ident(), [1, None])[0]

def current_observer():
    return _states.setdefault(get_ident(), [1, None])[1]




























class Cell(object):

    def __init__(self, rule=None, value=None, event=False):
        tid = get_ident()
        if tid not in _states:
            _states[tid] = [1, None]
        self._state = _states[tid]
        self._listeners = []
        self._depends = self._changed_as_of = self._version = None
        self._current_val = value
        self._rule = rule
        self._reset = (_sentinel, value)[bool(event)]
        self._writebuf = _sentinel

    def _get_value(self):
        pulse, observer = self._state
        if pulse is not self._version:
            self.check_dirty(pulse)

        if observer is not None and observer is not self:
            depends = observer._depends
            listeners = self._listeners
            if self not in depends: depends.append(self)
            r = ref(observer, listeners.remove)
            if r not in listeners: listeners.append(r)

        return self._current_val

    def _set_value(self, value):
        pulse, observer = self._state
        if pulse is not self._version:
            self.check_dirty(pulse)
        old = self._writebuf
        if old is not _sentinel and old is not value and old!=value:
            raise InputConflict(old, value) # XXX
        self._writebuf = value
        EventLoop.do_once(self._advance, pulse+1) # schedule propagation

    value = property(_get_value, _set_value)
    del _get_value, _set_value

    def check_dirty(self, pulse):
        if pulse is self._version:
            return pulse is self._changed_as_of

        if self._reset is not _sentinel:
            previous = self._current_val = self._reset
        else:
            previous = self._current_val

        self._version = pulse
        new = self._writebuf
        if new is not _sentinel:
            self._writebuf = _sentinel

        elif self._rule:
            deps = self._depends
            if deps is None:    # make sure the rule gets run the first time!
                new = self.recalculate()
            else:
                for d in deps:
                    if d._changed_as_of is pulse or d._version is not pulse \
                    and d.check_dirty(pulse):
                        new = self.recalculate()
                        break
                else:
                    new = previous
        else:
            return False

        if new is not previous and new != previous:
            self._current_val = new
            self._changed_as_of = pulse
            do = EventLoop.do_once
            listeners, self._listeners = self._listeners, []
            # XXX become constant here if needed + possible
            for c in listeners:
                c = c()
                if c is not None and c._version is not pulse:
                    do(c.check_dirty, pulse)
            return True

    def _advance(self, pulse):        
        if self._state[0] != pulse:
            # XXX EventLoop.pulse = pulse
            self._state[0] = pulse
        self.check_dirty(pulse)

    def recalculate(self):
        self._depends = []
        pulse, old_observer = self._state
        self._state[1] = self
        try:
            return self._rule()
        finally:
            self._state[1] = old_observer

        
class Constant(Cell):
    """An immutable cell that no longer depends on anything else"""

    #__slots__ = ()
    #_notifiers = ()
    value = None    # Cell._current_val

    def __init__(self, value):
        self.value = value  # Cell._current_val.__set__(self, value)

    def __setattr__(self, name, value):
        if 'value' in self.__dict__: # XXX hasattr(self,'_cache'):
            raise AttributeError("Constants can't be changed")
        object.__setattr__(self, name, value)

    def check_dirty(self, pulse):
        return False








class EventLoop(Service):
    """Thing that runs tasks"""

    _exit = None

    def __init__(self):
        self.queue = []

    def running(self):
        return self._exit is not None

    def todo(self):
        return len(self.queue)

    def will_do(self, func, *args, **kw):
        return (func,args,kw) in self.queue

    def do(self, func, *args, **kw):
        q = self.queue
        q.append((func,args,kw))
        if self._exit is not None:
            return

        self._exit = ()
        try:
            while q:
                func, args, kw = q.pop(0)
                retval = func(*args, **kw)
                if self._exit:
                    return self._exit[0]
            return retval
        finally:
            retval = self._exit = None

    def do_once(self, func, *args, **kw):
        if (func,args,kw) not in self.queue:
            self.do(func, *args, **kw)




    def cancel(self, func, *args, **kw):
        q = self.queue
        action = (func,args,kw)
        if action in q:
            q.remove(action)

    def exit(self, value=None):
        self._exit = value,

    def clear(self):
        self.queue[:] = []






























