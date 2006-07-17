from weakref import ref

try:
    from thread import get_ident
except ImportError:
    from dummy_thread import get_ident

computing = {}

def current_observer():
    return computing.get(get_ident())

def with_observer(value, rule, *args):
    t = get_ident()
    old = computing.get(t)
    try:
        computing[t] = value
        return rule(*args)
    finally:
        computing[t] = old

class Notifier(object):
    __slots__ = '__weakref__', 'target', 'backlinks'

    def __init__(self, target):
        self.target = ref(target)
        self.backlinks = []

def run_deferred(deferred):
    for cb, args in deferred:
        cb(*args)










class Trellis(object):
    """Synchronizes recalculation and updates"""
    pulse = 0
    propagating = 0

    def __init__(self):
        self.deferred = []
        self.dirty = {}

    def with_propagation(self, routine, *args):
        if self.propagating:
            return routine(*args)
        self.pulse += 1
        self.propagating = True
        try:
            routine(*args)
            while self.dirty:
                for v in self.dirty.keys():
                    v.ensure_clean()
        finally:
            self.propagating = False
        # if anything was deferred, do it now
        if self.deferred:
            deferred, self.deferred = self.deferred, []
            self.with_propagation(run_deferred, deferred)

    def changed(self, value):
        if not self.propagating:
            return self.with_propagation(self.changed, value)
        value.pulse = self.pulse
        for value in value.pop_outputs():
            self.dirty[value] = 1

    def call_between_pulses(self, cb, *args):
        if self.propagating:
            self.deferred.append((cb,args))
        else:
            cb(*args)

state = Trellis()

class ValueHolder(object):
    """Holder for a value that can change"""

    __slots__ = [
        '_cache', '_notifiers', 'pulse', '__weakref__', 'notifier',
    ]

    def __init__(self):
        self.pulse = -1
        self._notifiers = []
        self.notifier = Notifier(self)

    def read(self, value):
        if value is not None:
            notifiers = self._notifiers
            r = ref(value.notifier, lambda r: notifiers.remove(r))
            if r not in self._notifiers:
                self._notifiers.append(r)
                value.notifier.backlinks.append(self)

    def _set_value(self, value, incr=1):
        try:
            c = self._cache
        except AttributeError:
            pass
        else:
            if c==value:
                return
        self._cache = value
        state.changed(self)

    def pop_outputs(self):
        listeners = self.listeners()
        del self._notifiers[:]       # clear the dependencies we're firing
        return listeners

    def listeners(self):
        notifiers = filter(None, [n() for n in self._notifiers])
        return      filter(None, [n.target() for n in notifiers])


class Value(ValueHolder):
    """Holder for a value that can change"""
    __slots__ = 'rule'

    def __init__(self, rule):
        ValueHolder.__init__(self)
        self.rule = rule

    def is_dirty(self):
        if self.pulse == state.pulse:   return False
        elif self in state.dirty:       return True
        elif not hasattr(self,'_cache'):
            self._cache = with_observer(self, self.rule)
            return False
        else:
            for dep in self.notifier.backlinks:
                if dep.is_dirty():
                    return True

    def ensure_clean(self):
        if self.is_dirty():
            self.notifier = Notifier(self)  # clear old deps
            self._set_value(with_observer(self, self.rule))
        self.pulse = state.pulse
        if self in state.dirty:
            del state.dirty[self]
        if not self.notifier.backlinks:
            self.become_constant()

    def value(self):
        if self.pulse < state.pulse:
            self.ensure_clean()
        self.read(current_observer())   # subscribe my reader to me
        return self._cache
    value = property(value)

    def become_constant(self):
        del self._notifiers, self.rule, self.notifier
        self.__class__ = Constant


class Input(ValueHolder):
    """A mutable value intended for inputs from non-trellis components"""

    __slots__ = ()

    def __init__(self, value):
        ValueHolder.__init__(self)
        self.notifier = Notifier(self)
        self.value = value

    def get_value(self):
        self.read(current_observer())
        return self._cache

    def set_value(self, value):
        state.call_between_pulses(self._set_value, value)

    value = property(get_value, set_value)

    def is_dirty(self):
        return False    # XXX should have a test to prove this is needed

class Constant(Value):
    """An immutable value that no longer depends on anything else"""

    __slots__ = ()
    value = Input._cache
    _notifiers = ()

    def __init__(self, value):
        self.value = value

    def __setattr__(self, name, value):
        if hasattr(self,'_cache'):
            raise AttributeError("Constants can't be changed")
        object.__setattr__(self, name, value)

    def read(self, value): pass



