from weakref import ref

try:
    from threading import local
except ImportError:
    try:
        from dummy_threading import local
    except ImportError:
        from _threading_local import local


class TrellisState(local):
    version = 0
    computing = None

state = TrellisState()


class Notifier(object):
    __slots__ = '__weakref__', 'target', 'count'

    def __init__(self, target):
        self.target = ref(target)
        self.count = 0

















class Value(object):
    """Holder for a value that can change"""

    __slots__ = [
        '_cache', 'rule', '_notifiers', 'as_of', 'needs', '__weakref__',
        'notifier',
    ]

    def __init__(self, rule):
        self.rule = rule
        self.needs = 0
        self.as_of = -1
        self._notifiers = []

    def read(self, value):
        if value is not None:
            notifiers = self._notifiers
            r = ref(value.notifier, lambda r: notifiers.remove(r))
            if r not in self._notifiers:
                self._notifiers.append(r)
                value.notifier.count += 1

    def value(self):
        old = state.computing
        try:
            state.computing = self
            if self.as_of < self.needs:
                self.notifier = Notifier(self)  # clear old dependencies
                self._set_value(self.rule(), 0)
                if not self.notifier.count:
                    self.become_constant()
                    return self._cache
                self.as_of = state.version
            self.read(old) # mark the dependency on the new current value
            return self._cache
        finally:
            state.computing = old

    value = property(value)


    def _set_value(self, value, incr=1):
        try:
            c = self._cache
        except AttributeError:
            pass
        else:
            if c==value:
                return
        self._cache = value
        self.as_of = state.version = state.version + incr
        self.changed()

    def listeners(self):
        notifiers = filter(None, [n() for n in self._notifiers])
        return      filter(None, [n.target() for n in notifiers])

    def changed(self):
        listeners = self.listeners()
        del self._notifiers[:]       # reset fired dependencies

        as_of = self.as_of

        for v in listeners:
            v.needs = as_of     # mark 'em all dirty
        for v in listeners:
            v.value     # force 'em to recompute

    def become_constant(self):
        del self._notifiers, self.needs, self.rule, self.notifier
        self.__class__ = Constant











class Input(Value):
    """A mutable value intended for inputs from non-trellis components"""

    __slots__ = ()

    def __init__(self, value):
        self._notifiers = []
        self.needs = self.as_of = None
        self.value = value
        self.notifier = Notifier(self)

    def get_value(self):
        self.read(state.computing)
        return self._cache

    def set_value(self, value):
        try:
            c = self._cache
        except AttributeError:
            pass
        else:
            if c==value:
                return
        self._cache = value
        self.as_of = state.version = state.version + 1
        self.changed()

    value = property(get_value, Value._set_value.im_func)













class Constant(Input):
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



























