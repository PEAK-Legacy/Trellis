from thread import get_ident
from peak.util.symbols import Symbol
from weakref import ref
from peak.util.roles import Role, Registry
from peak.util.decorators import decorate, struct, decorate_assignment, rewrap
import sys

__all__ = [
    'Cell', 'Constant', 'rule', 'rules', 'value', 'values', 'optional',
    'todo', 'todos', 'modifier', 'receiver', 'receivers', 'Component',
    'repeat', 'poll', 'without_observer', 'InputConflict', 
]

_states = {}
NO_VALUE = Symbol('NO_VALUE', __name__)
_sentinel = NO_VALUE

def _get_state():
    tid = get_ident()
    if tid not in _states:
        _states[tid] = state = [Pulse(1), None, Pulse(2)]
        state[0].cell = state[2].cell = Cell(current_pulse, 1)
    return _states[tid]

class Pulse(object):
    __slots__ = 'data', 'number', 'cell'
    def __init__(self, number, cell=None):
        self.data = []
        self.number = number
        self.cell = cell

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
    writable = False
    def __init__(self, rule=None, value=None, receiver=False):
        self._state = _get_state()
        self._listeners = []
        self._mailbox = Mailbox(self, None)
        self._changed_as_of = self._version = None
        self._current_val = value
        self._rule = rule
        self._reset = (_sentinel, value)[bool(receiver)]
        if receiver and rule is not None:
            raise TypeError("Receivers can't have rules")

    def get_value(self):
        pulse, observer, todo = state = self._state
        if observer is None:
            # XXX we should switch to current state here, if needed
            if pulse is not self._version:
                self.check_dirty(state)
                _cleanup(state)
            return self._current_val
        elif observer is not self:
            #if observer._state is not state:
            #    raise RuntimeError("Can't access cells in another task/thread")
            mailbox = observer._mailbox
            depends = mailbox.dependencies
            listeners = self._listeners
            if self not in depends: depends.append(self)
            r = ref(mailbox, listeners.remove)
            if r not in listeners: listeners.append(r)
        if pulse is not self._version:
            self.check_dirty(state)
        return self._current_val

        
    value = property(get_value)

    def check_dirty(self, state):
        pulse, observer, todo = state
        if pulse is self._version:
            return pulse is self._changed_as_of

        previous = self._current_val
        self._version = pulse
        freeze = False

        if self._reset is not _sentinel and previous != self._reset:
            new = self._reset
        else:
            new = self._writebuf
            if new is not _sentinel:
                self._writebuf = _sentinel
                if self._reset is not _sentinel:
                    todo.data.append(self)
            elif self._rule:
                for d in self._mailbox.dependencies:
                    if (not d or d._changed_as_of is pulse
                         or d._version is not pulse and d.check_dirty(state)
                    ):
                        self._mailbox = m = Mailbox(self)  # break old deps
                        state[1] = self
                        try:
                            new = self._rule()
                            freeze = not m.dependencies and self._can_freeze
                            break
                        finally:
                            state[1] = observer
                else:
                    return False
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
            if freeze:
                self._mailbox = self._listeners = None
                self.__class__ = Constant
            return True

        elif freeze:
            self._mailbox = self._listeners = None
            self.__class__ = Constant

    def __repr__(self):
        e = ('', ', receiver[%r]'% self._reset)[self._reset is not _sentinel]
        return "%s(%r, %r%s)" %(self.__class__.__name__,self._rule,self.value,e)

    def ensure_recalculation(self):
        """Ensure that this cell's rule will be (re)calculated"""
        pulse, observer, todo = self._state
        if observer is self:  # repeat()
            self._mailbox.dependencies.insert(0, None)
            todo.data.append(self)
        elif self._rule is None:
            raise TypeError("Can't recalculate a cell without a rule")
        #elif observer and observer._state is not self._state:
        #    raise RuntimeError("Can't access cells in another task/thread")
        elif pulse is self._version:
            raise RuntimeError("Already recalculated")
        else:  
            self._mailbox.dependencies.append(None)
            pulse.data.append(self)


class InputConflict(Exception):
    """Attempt to set a cell to two different values during the same pulse"""



class Constant(ReadOnlyCell):
    """An immutable cell that no longer depends on anything else"""

    __slots__ = ()
    value = ReadOnlyCell._current_val
    get_value = lambda self: self.value
    
    _can_freeze = False
    _mailbox = None

    def __init__(self, value):
        ReadOnlyCell._current_val.__set__(self, value)

    def __setattr__(self, name, value):
        raise AttributeError("Constants can't be changed")

    def check_dirty(self, state):
        return False

    def __repr__(self):
        return "Constant(%r)" % (self.value,)

def _cleanup(state):
    pulse, observer, todo = state #= state or _get_state()
    while observer is None:
        if pulse.data:
            for item in pulse.data:
                item.check_dirty(state)
            del pulse.data[:]

        if not todo.data:
            return    # no changes, stay in the current pulse

        # Begin a new pulse
        pulse.data = None   # don't keep a list around any longer
        pulse = state[0] = todo
        todo = state[2] = Pulse(pulse.number+1, pulse.cell)
        pulse.cell.ensure_recalculation()



class Cell(ReadOnlyCell):

    _can_freeze = False
    __slots__ = '_writebuf'
    writable = True

    def __new__(cls, rule=None, value=_sentinel, receiver=False):
        if value is _sentinel and rule is not None:
            return ReadOnlyCell(rule, None, receiver)
        return ReadOnlyCell.__new__(cls, rule, value, receiver)

    def __init__(self, rule=None, value=None, receiver=False):
        ReadOnlyCell.__init__(self, rule, value, receiver)
        self._writebuf = _sentinel

    def set_value(self, value):
        pulse, observer, todo = state = self._state
        #if observer is None:
        #    XXX we should switch to current state here, if needed
        #elif observer._state is not state:
        #    raise RuntimeError("Can't access cells in another task/thread")
        if pulse is not self._version:
            if self._version is None:
                self._current_val = value
            self.check_dirty(state)
        old = self._writebuf
        if old is not _sentinel and old is not value and old!=value:
            raise InputConflict(old, value) # XXX
        self._writebuf = value
        todo.data.append(self)
        if not observer:
            _cleanup(state)

    value = property(ReadOnlyCell.get_value, set_value)


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

class IsReceiver(_Defaulting):
    """Registry for flagging that a cell is an event"""

def default_factory(typ, ob, name):
    """Default factory for making cells"""
    rule = CellRules(typ).get(name)
    value = CellValues(typ).get(name, _sentinel)
    if rule is not None:
        rule = rule.__get__(ob, typ)
    if value is _sentinel:
        return Cell(rule, receiver=IsReceiver(typ).get(name, False))
    return Cell(rule, value, IsReceiver(typ).get(name, False))

class Cells(Role):
    __slots__ = ()
    role_key = classmethod(lambda cls: '__cells__')
    def __new__(cls, subject): return {}


def rule(func):
    """Define a rule cell attribute"""
    return _rule(func, __frame=sys._getframe(1))

def _rule(func, **kw):
    if isinstance(func, CellProperty):
        raise TypeError("@rule decorator must wrap a function directly")
    else:
        items = [(CellRules, func), (CellFactories, default_factory)]
        return _invoke_callback(items, func, **kw)

def value(value):
    """Define a value cell attribute"""
    return _value(value, __frame=sys._getframe(1))

def _value(value, **kw):
    items = [(CellFactories, default_factory)]
    return _invoke_callback(items, value=value, **kw)

def _set_multi(frame, kw, wrap, arg='func'):
    for k, v in kw.items():
        v = wrap(__name=k, __frame=frame, **{arg:v})
        frame.f_locals.setdefault(k, v)

def rules(**attrs):
    """Define multiple rule-cell attributes"""
    _set_multi(sys._getframe(1), attrs, _rule)

def values(**attrs):
    """Define multiple value-cell attributes"""
    _set_multi(sys._getframe(1), attrs, _value, 'value')

def receivers(**attrs):
    """Define multiple receiver-cell attributes"""
    _set_multi(sys._getframe(1), attrs, _receiver, 'value')

def todos(**attrs):
    """Define multiple todo-cell attributes"""
    _set_multi(sys._getframe(1), attrs, _todo)


def optional(func):
    """Define a rule-cell attribute that's not automatically activated"""
    return _invoke_callback([(IsOptional, True)], func)

def receiver(value):
    """Define a receiver-cell attribute"""
    return _receiver(value, __frame=sys._getframe(1))

def _receiver(value, **kw):
    items = [(IsReceiver, True), (CellFactories, default_factory)]
    return _invoke_callback(items, None, value, **kw)

def todo(func):
    """Define an attribute that can send "messages to the future" """
    return _todo(func, __frame=sys._getframe(1))

def _todo(func, **kw):
    if isinstance(func, CellProperty):
        raise TypeError("@todo decorator must wrap a function directly")
    else:
        items = [
            (CellRules, func), (CellFactories, todo_factory),
            (CellValues, None), (IsReceiver, True),
        ]
        return _invoke_callback(items, func, __proptype=TodoProperty, **kw)

def initattrs(ob, cls):
    for k, v in IsOptional(cls).iteritems():
        if not v: getattr(ob, k)

def without_observer(func, *args, **kw):
    """Run func(*args, **kw) without making the current rule depend on it"""
    o = _get_state()[1]
    if o:
        tmp, o._mailbox = o._mailbox, Mailbox(o)
        try:     return func(*args, **kw)
        finally: o._mailbox = tmp
    else:
        return func(*args, **kw)


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
        without_observer(initattrs, self, cls)


def repeat():
    """Schedule the current rule to be run again, repeatedly"""
    observer = current_observer()
    if observer:
        observer.ensure_recalculation()
    else:
        raise RuntimeError("repeat() must be called from a rule")
    
def poll():
    """Recalculate this rule the next time *any* other cell is set"""
    pulse, observer, todo = _get_state()
    if observer:
        return pulse.cell.value
    else:
        raise RuntimeError("poll() must be called from a rule")











class CellProperty(object):
    """Descriptor for cell-based attributes"""

    def __init__(self, name):
        self.__name__ = name

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.__name__)

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
                if not cell.writable:
                    return ob.__cells__.setdefault(name, Constant(value))
                cell = ob.__cells__.setdefault(name, cell)
            cell.value = value

    def __eq__(self, other):
        return type(other) is type(self) and other.__name__==self.__name__

    def __ne__(self, other):
        return type(other) is not type(self) or other.__name__!=self.__name__

def _invoke_callback(
    extras, func=_sentinel, value=_sentinel, __frame=None, __name=None,
    __proptype = CellProperty
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
        IsReceiver.for_frame(frame).defaults[name] = False
        IsOptional.for_frame(frame).defaults[name] = False
        CellFactories.for_frame(frame).defaults[name] = default_factory
        return __proptype(name)

    if name:
        return callback(frame, name, func, None)
    else:
        decorate_assignment(callback, frame=frame)
        return _sentinel












class TodoProperty(CellProperty):
    """Property representing a ``todo`` attribute"""

    decorate(property)
    def future(self):
        """Get a read-only property for the "future" of this attribute"""
        name = self.__name__
        def get(ob):
            try:
                cell = ob.__cells__[name]
            except KeyError:
                typ = type(ob)
                cell = CellFactories(typ)[name](typ, ob, name)
                cell = ob.__cells__.setdefault(name, cell)
            if cell._writebuf is _sentinel:
                if current_observer() is None:
                    raise RuntimeError("future can only be accessed from a @modifier")
                cell.value = CellRules(type(ob))[name].__get__(ob)()
            return cell._writebuf            
        return property(
            get, doc="The future value of the %r attribute" % name
        )

def todo_factory(typ, ob, name):
    """Factory for ``todo`` cells"""
    rule = CellRules(typ).get(name).__get__(ob, typ)
    return Cell(None, rule(), True)

def modifier(method):
    """Mark a method as performing modifications to Trellis data"""
    def decorated(*args, **kw):
        pulse, observer, todo = state = _get_state()
        state[1] = observer or Cell()
        try:
            return method(*args, **kw)
        finally:        
            state[1] = observer
            if observer is None:
                _cleanup(state)
    return rewrap(method, decorated)

