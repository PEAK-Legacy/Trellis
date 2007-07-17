from peak.context import get_ident, InputConflict
from peak.util.symbols import Symbol
from weakref import ref
from peak.util.roles import Role, Registry
from peak.util.decorators import decorate, struct, decorate_assignment
import sys

__all__ = [
    'Cell', 'Constant', 'repeat', 'rule', 'rules', 'event', 'events', 'value',
    'values', 'optional', 'cell_factory', 'cell_factories', 'Component',
]

_states = {}
NO_VALUE = Symbol('NO_VALUE', __name__)
_sentinel = NO_VALUE

def repeat():
    """Schedule the current rule to be run again, repeatedly"""
    pulse, observer, todo = _get_state()
    observer._mailbox.dependencies.insert(0, None)   # mark calling rule for recalc
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

class Mailbox(object):
    __slots__ = '__weakref__', 'owner', 'dependencies'
    def __init__(self, owner, *args):
        self.owner = ref(owner)
        self.dependencies = list(args)

class ReadOnlyCell(object):
    __slots__ = """
        _state _listeners _mailbox _current_val _rule _reset _changed_as_of
        _version __weakref__
    """.split()
    _writebuf = _sentinel
    _can_freeze = True

    def __init__(self, rule=None, value=None, event=False):
        self._state = _get_state()
        self._listeners = []
        self._mailbox = Mailbox(self, None)
        self._changed_as_of = self._version = None
        self._current_val = value
        self._rule = rule
        self._reset = (_sentinel, value)[bool(event)]

    def _get_value(self):
        pulse, observer, todo = self._state
        if pulse is not self._version:
            self.check_dirty(pulse)
            if observer is None: cleanup()
            if not self._mailbox.dependencies and self._can_freeze and (self._reset
                is _sentinel or self._changed_as_of is not pulse
            ):
                del self._mailbox, self._listeners
                self.__class__ = Constant
                return self._current_val

        if observer is not None and observer is not self:
            mailbox = observer._mailbox
            depends = mailbox.dependencies
            listeners = self._listeners
            if self not in depends: depends.append(self)
            r = ref(mailbox, listeners.remove)
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
            for d in self._mailbox.dependencies:
                if (not d or d._changed_as_of is pulse
                     or d._version is not pulse and d.check_dirty(pulse)
                ):
                    self._mailbox = Mailbox(self)  # break old dependencies
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
            for c in self._listeners:
                c = c()
                if c is not None:
                    c = c.owner()
                    if c is not None and c._version is not pulse:
                        pulse.data.append(c)
            return True


    def _set_rule(self, rule):
        pulse, observer, todo = self._state
        if pulse is not self._version:
            self.check_dirty(pulse)
        self._rule = rule
        self._mailbox = Mailbox(self, None)
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
    _mailbox = None

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
        pulse.data = None   # don't keep a list around any longer
        pulse = state[0] = todo
        todo = state[2] = Pulse(pulse.number+1)
        for item in pulse.data:
            item.check_dirty(pulse)


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

def current_pulse():    return _get_state()[0].number
def current_observer(): return _get_state()[1]

class CellValues(Registry):
    """Registry for cell values"""

class CellRules(Registry):
    """Registry for cell rules"""

class _Defaulting(Registry):
    def __init__(self, subject):
        self.defaults = {}
        return super(_Defaulting, self).__init__(subject)

    def created_for(self, cls):
        for k,v in self.defaults.items():
            self.setdefault(k, v)
        return super(_Defaulting, self).created_for(cls)

class CellFactories(_Defaulting):
    """Registry for cell factories"""

class IsOptional(_Defaulting):
    """Registry for flagging that an attribute need not be activated"""

class EventFlags(_Defaulting):
    """Registry for flagging that a cell is an event"""

def default_factory(typ, ob, name):
    """Default factory for making cells"""
    rule = CellRules(typ).get(name)
    value = CellValues(typ).get(name, _sentinel)
    event = EventFlags(typ).get(name, False)
    if rule is not None:
        rule = rule.__get__(ob, typ)
    if value is _sentinel:
        return Cell(rule, event=event)
    return Cell(rule, value, event)

class Cells(Role):
    __slots__ = ()
    role_key = classmethod(lambda cls: '__cells__')
    def __new__(cls, subject): return {}

def _invoke_callback(
    extras, func=_sentinel, value=_sentinel, __frame=None, __name=None
):
    frame = __frame or sys._getframe(2)
    name  = __name
    items = list(extras)

    if func is not _sentinel:
        items.append((CellRules, func))
        if func is not None and func.__name__!='<lambda>':
            name = name or func.__name__

    if value is not _sentinel:
        items.append((CellValues, value))

    def callback(frame, name, func, locals):
        for role, value in items:
            role.for_frame(frame).set(name, value)
        EventFlags.for_frame(frame).defaults[name] = False
        IsOptional.for_frame(frame).defaults[name] = False
        CellFactories.for_frame(frame).defaults[name] = default_factory
        return CellProperty(name)

    if name:
        return callback(frame, name, func, None)        
    else:
        decorate_assignment(callback, frame=frame)
        return _sentinel

def optional(func=_sentinel, value=_sentinel, **kw):
    if '__modifier' in kw:
        IsOptional.for_frame(kw['__frame']).set(kw['__name'], True)
        return CellProperty(kw['__name'])
    elif isinstance(func, CellProperty):
        IsOptional.for_enclosing_class().set(func.__name__, True)
        return func
    else:
        return _invoke_callback([(IsOptional, True)], func, value, **kw)



def event(func=None, value=_sentinel, **kw):
    if '__modifier' in kw:
        EventFlags.for_frame(kw['__frame']).set(kw['__name'], True)
        return CellProperty(kw['__name'])
    elif isinstance(func, CellProperty):
        EventFlags.for_enclosing_class().set(func.__name__, True)
        return func
    else:
        items = [(EventFlags, True), (CellFactories, default_factory)]
        return _invoke_callback(items, func, value, **kw)

def rule(func, **kw):
    if isinstance(func, CellProperty):
        raise TypeError("rule decorator must wrap a function directly")
    else:
        items = [(CellRules, func), (CellFactories, default_factory)]
        return _invoke_callback(items, func, **kw)

def cell_factory(func, **kw):
    if isinstance(func, CellProperty):
        raise TypeError("cell_factory decorator must wrap a function directly")
    else:
        items = [
            (CellFactories, Factory(func)), (CellValues, _sentinel),
            (EventFlags, False)
        ]
        if func.__name__ !='<lambda>': kw.setdefault('__name', func.__name__)
        return _invoke_callback(items, None, **kw)

def value(value, **kw):
    if isinstance(value, CellProperty):
        raise TypeError("value() must wrap a value directly")
    else:
        items = [(CellFactories, default_factory)]
        return _invoke_callback(items, value=value, **kw)






struct(__call__ = lambda self, typ, ob, name: self.func(ob))
def Factory(func):
    return func,

def _set_multi(frame, modifiers, kw, wrap, arg='func'):
    for k, v in kw.items():
        v = wrap(__name=k, __frame=frame, **{arg:v})
        frame.f_locals.setdefault(k, v)
        for m in modifiers:
            v = m(__name=k, __frame=frame, __modifier=True, **{arg:v})

def rules(*modifiers, **kw):
    _set_multi(sys._getframe(1), modifiers, kw, rule)

def events(*modifiers, **kw):
    _set_multi(sys._getframe(1), modifiers, kw, event)

def cell_factories(*modifiers, **kw):
    _set_multi(sys._getframe(1), modifiers, kw, cell_factory)

def values(*modifiers, **kw):
    _set_multi(sys._getframe(1), modifiers, kw, value, 'value')

class Component(object):
    """Base class for objects with Cell attributes"""
    __slots__ = ()
    def __init__(self, **kw):
        cls = type(self)
        self.__cells__ = Cells(self)
        for k, v in kw.iteritems():
            if not hasattr(cls, k):
                raise TypeError("%s() has no keyword argument %r"
                    % (cls.__name__, k)
                )
            setattr(self, k, v)
        for k, v in IsOptional(cls).iteritems():
            if not v:
                getattr(self, k)



class CellProperty(object):
    """Descriptor for cell-based attributes"""

    def __init__(self, name):
        self.__name__ = name

    def __repr__(self):
        return "CellProperty(%r)" % self.__name__

    def __get__(self, ob, typ=None):
        if ob is None:
            return self
        try:
            cell = ob.__cells__[self.__name__]
        except KeyError:
            name = self.__name__
            cell =  CellFactories(typ)[name](typ, ob, name)
            cell = ob.__cells__.setdefault(name, cell)
        return cell.value

    def __set__(self, ob, value):
        if isinstance(value, ReadOnlyCell):
            ob.__cells__[self.__name__] = value
        else:
            try:
                cell = ob.__cells__[self.__name__]
            except KeyError:
                name = self.__name__
                typ = type(ob)
                cell =  CellFactories(typ)[name](typ, ob, name)
                cell = ob.__cells__.setdefault(name, cell)
            cell.value = value

    def __eq__(self, other):
        return type(other) is CellProperty and other.__name__==self.__name__

    def __ne__(self, other):
        return type(other) is not CellProperty or other.__name__!=self.__name__



