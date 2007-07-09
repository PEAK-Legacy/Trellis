from peak.context import Service, get_ident, InputConflict
from peak.util.symbols import Symbol
from weakref import ref

__all__ = ['Cell', 'Constant']

_states = {}

NO_VALUE = Symbol('NO_VALUE', __name__)

_sentinel = NO_VALUE

def current_pulse():
    return _get_state()[0]

def current_observer():
    return _get_state()[1]

def current_runner():
    return _get_state()[2]

def _get_state():
    tid = get_ident()
    if tid not in _states:
        _states[tid] = [1, None, False]
    return _states[tid]















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
        self._depends = self._changed_as_of = self._version = None
        self._current_val = value
        self._rule = rule
        self._reset = (_sentinel, value)[bool(event)]

    def _get_value(self):
        pulse, observer, runner = self._state
        if pulse is not self._version:
            if not runner:
                run(self.check_dirty, pulse)   # block until stable state
            else:
                self.check_dirty(pulse)
            if not self._depends and self._can_freeze and (self._reset
                is _sentinel or self._changed_as_of is not pulse
            ):
                return self.freeze()

        if observer is not None and observer is not self:
            depends = observer._depends
            listeners = self._listeners
            if self not in depends: depends.append(self)
            r = ref(observer, listeners.remove)
            if r not in listeners: listeners.append(r)
        return self._current_val

    value = property(_get_value)
    del _get_value


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
            runner = self._state[2] or run
            listeners, self._listeners = self._listeners, []

            for c in listeners:
                c = c()
                if c is not None and c._version is not pulse:
                    runner(c.check_dirty, pulse)
            return True

    def _advance(self, pulse):
        if self._state[0] != pulse:
            # XXX EventLoop.pulse = pulse
            self._state[0] = pulse
        self.check_dirty(self._state[0])

    def recalculate(self):
        self._depends = []
        pulse, old_observer, runner = self._state
        self._state[1] = self
        try:
            return self._rule()
        finally:
            self._state[1] = old_observer

    def _set_rule(self, rule):
        pulse, observer, runner = self._state
        if pulse is not self._version:
            self.check_dirty(pulse)
        self._rule = rule
        self._depends = None
        (runner or run)(self._advance, pulse+1) # schedule propagation

    rule = property(lambda s:s._rule, _set_rule)
    del _set_rule

    def freeze(self):
        pulse, observer, runner = self._state
        if pulse is not self._version:
            self.check_dirty(pulse)
        del self._depends, self._listeners
        self.__class__ = Constant
        return self._current_val

    def __repr__(self):
        e = ('', ', event[%r]'% self._reset)[self._reset is not _sentinel]
        return "%s(%r, %r%s)" %(self.__class__.__name__,self.rule,self.value,e)




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
        pulse, observer, runner = self._state
        if pulse is not self._version:
            self.check_dirty(pulse)
        old = self._writebuf
        if old is not _sentinel and old is not value and old!=value:
            raise InputConflict(old, value) # XXX
        self._writebuf = value
        (runner or run)(self._advance, pulse+1) # schedule propagation

    value = property(ReadOnlyCell.value.fget, _set_value)
    del _set_value















class Constant(ReadOnlyCell):
    """An immutable cell that no longer depends on anything else"""

    __slots__ = ()
    value = ReadOnlyCell._current_val

    def __init__(self, value):
        ReadOnlyCell._current_val.__set__(self, value)

    def __setattr__(self, name, value):
        raise AttributeError("Constants can't be changed")

    def check_dirty(self, pulse):
        return False

    def __repr__(self):
        return "Constant(%r)" % (self.value,)


def run(func, *args):
    """Trivial co-operative multitasking"""
    state = _get_state()
    old_runner = state[2]
    if old_runner:
        return old_runner(func, *args)

    queue = [(func,args)]

    def runner(func, *args):
        cmd = (func,args)
        if cmd not in queue:
            queue.append(cmd)

    state[2] = runner
    try:
        while queue:
            func, args = queue.pop(0)
            func(*args)
    finally:
        state[2] = old_runner

