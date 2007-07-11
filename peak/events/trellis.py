from peak.context import Service, get_ident, InputConflict
from peak.util.symbols import Symbol
from weakref import ref

__all__ = ['Cell', 'Constant', 'repeat']

_states = {}

NO_VALUE = Symbol('NO_VALUE', __name__)

_sentinel = NO_VALUE

def current_pulse():
    return _get_state()[0].number

def current_observer():
    return _get_state()[1]

def repeat():
    """Schedule the current rule to be run again, repeatedly"""
    pulse, observer, todo = _get_state()
    observer._depends.insert(0, None)   # mark calling rule for recalc
    todo.data.append(observer)          # and schedule it for the next pulse
    return True

def _get_state():
    tid = get_ident()
    if tid not in _states:
        _states[tid] = [Pulse(1), None, Pulse(2)]
    return _states[tid]

class Pulse(object):
    __slots__ = 'data', 'number'
    def __init__(self, number):
        self.data = []
        self.number = number





class ReadOnlyCell(object):
    __slots__ = """
        _state _listeners _depends _current_val _rule _reset _changed_as_of
        _version __weakref__
    """.split()

    _writebuf = _sentinel
    _can_freeze = True

    def __init__(self, rule=None, value=None, event=False):
        self._state = _get_state()
        self._listeners = []
        self._depends = None,; self._changed_as_of = self._version = None
        self._current_val = value
        self._rule = rule
        self._reset = (_sentinel, value)[bool(event)]

    def _get_value(self):
        pulse, observer, todo = self._state
        if pulse is not self._version:
            self.check_dirty(pulse)
            if observer is None: cleanup()
            if not self._depends and self._can_freeze and (self._reset
                is _sentinel or self._changed_as_of is not pulse
            ):
                del self._depends, self._listeners
                self.__class__ = Constant
                return self._current_val

        if observer is not None and observer is not self:
            depends = observer._depends
            listeners = self._listeners
            if self not in depends: depends.append(self)
            r = ref(observer, listeners.remove)
            if r not in listeners: listeners.append(r)

        return self._current_val

    value = property(_get_value)


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
            for d in deps:
                if (not d or d._changed_as_of is pulse
                     or d._version is not pulse and d.check_dirty(pulse)
                ):
                    self._depends = []
                    tmp, old_observer, todo = state = self._state
                    state[1] = self
                    try:
                        new = self._rule()
                        break
                    finally:
                        state[1] = old_observer
            else:
                new = previous
        else:
            return False

        if new is not previous and new != previous:
            self._current_val = new
            self._changed_as_of = pulse
            listeners, self._listeners = self._listeners, []
            for c in listeners:
                c = c()
                if c is not None and c._version is not pulse:
                    pulse.data.append(c)
            return True


    def _set_rule(self, rule):
        pulse, observer, todo = self._state
        if pulse is not self._version:
            self.check_dirty(pulse)
        self._rule = rule
        self._depends = None,
        todo.data.append(self)
        if not observer: cleanup()

    rule = property(lambda s:s._rule, _set_rule)
    del _set_rule

    def __repr__(self):
        e = ('', ', event[%r]'% self._reset)[self._reset is not _sentinel]
        return "%s(%r, %r%s)" %(self.__class__.__name__,self.rule,self.value,e)


class Constant(ReadOnlyCell):
    """An immutable cell that no longer depends on anything else"""

    __slots__ = ()
    value = ReadOnlyCell._current_val

    _can_freeze = False
    _depends = None

    def __init__(self, value):
        ReadOnlyCell._current_val.__set__(self, value)

    def __setattr__(self, name, value):
        raise AttributeError("Constants can't be changed")

    def check_dirty(self, pulse):
        return False

    def __repr__(self):
        return "Constant(%r)" % (self.value,)




def cleanup():
    pulse, observer, todo = state = _get_state()
    while todo.data:
        pulse = state[0] = todo
        todo = state[2] = Pulse(pulse.number+1)
        for item in pulse.data:
            item.check_dirty(pulse)
        pulse.data = None   # don't keep a list around any longer
        

class Cell(ReadOnlyCell):

    _can_freeze = False
    __slots__ = '_writebuf'

    def __new__(cls, rule=None, value=_sentinel, event=False):
        if value is _sentinel and rule is not None:
            return ReadOnlyCell(rule, None, event)
        return ReadOnlyCell.__new__(cls, rule, value, event)

    def __init__(self, rule=None, value=None, event=False):
        ReadOnlyCell.__init__(self, rule, value, event)
        self._writebuf = _sentinel

    def _set_value(self, value):
        pulse, observer, todo = self._state
        if pulse is not self._version:
            self.check_dirty(pulse)
        old = self._writebuf
        if old is not _sentinel and old is not value and old!=value:
            raise InputConflict(old, value) # XXX
        self._writebuf = value
        todo.data.append(self)
        if not observer: cleanup()

    value = property(ReadOnlyCell.value.fget, _set_value)
    del _set_value




