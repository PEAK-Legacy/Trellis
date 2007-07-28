from thread import get_ident
from weakref import ref
from peak.util import symbols, roles, decorators
import sys

__all__ = [
    'Cell', 'Constant', 'rule', 'rules', 'value', 'values', 'optional',
    'todo', 'todos', 'modifier', 'receiver', 'receivers', 'Component',
    'discrete', 'repeat', 'poll', 'without_observer', 'InputConflict', 
]

_states = {}
NO_VALUE = symbols.Symbol('NO_VALUE', __name__)
_sentinel = NO_VALUE

def _get_state():
    try:
        return _states[get_ident()]
    except KeyError:
        _Controller()
        return _states[get_ident()]

class _Controller:
    def __init__(self):
        _states.setdefault(get_ident(), [1, None, self])
        now = self.now = []
        later = self.later = []
        self.notify = now.append
        self.change = later.append
        self.cell = Cell(current_pulse, 1)
    
class Mailbox(object):
    __slots__ = '__weakref__', 'owner', 'dependencies'
    def __init__(self, owner, *args):
        self.owner = ref(owner)
        self.dependencies = list(args)





class ReadOnlyCell(object):
    """Base class for all cell types, also a read-only cell"""
    __slots__ = """
        _state _listeners _mailbox _current_val _rule _reset _changed_as_of
        _version __weakref__
    """.split()
    _writebuf = _sentinel
    _can_freeze = True
    _writable = False

    def __init__(self, rule=None, value=None, discrete=False):
        self._state = _get_state()
        self._listeners = []
        self._mailbox = Mailbox(self, None)
        self._changed_as_of = self._version = None
        self._current_val = value
        self._rule = rule
        self._reset = (_sentinel, value)[bool(discrete)]

    def get_value(self):
        """Get the value of this cell"""
        pulse, observer, ctrl = state = self._state
        if observer is None:
            # XXX we should switch to current state here, if needed
            if pulse is not self._version:
                self._check_dirty(state)
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
            self._check_dirty(state)
        return self._current_val

    value = property(get_value)

    def _check_dirty(self, state):
        pulse, observer, ctrl = state
        if pulse is self._version:
            # We are already up to date, indicate whether we've changed
            return pulse is self._changed_as_of

        self._version = pulse   # Ensure circular rules terminate

        new = self._writebuf
        if new is not _sentinel:
            # We were assigned a value in the previous pulse
            self._writebuf = _sentinel
            have_new = True
        else:
            have_new = False
            if self._rule:
                # We weren't assigned a value, see if we need to recalc
                for d in self._mailbox.dependencies:
                    if (not d or d._changed_as_of is pulse
                         or d._version is not pulse and d._check_dirty(state)
                    ):  # one of our dependencies changed, recalc
                        self._mailbox = m = Mailbox(self)  # break old deps
                        state[1] = self    # we are the observer while calc-ing
                        try:
                            new = self._rule()
                            have_new = True
                            if not m.dependencies and self._can_freeze:
                                have_new = _sentinel    # flag for freezing
                            break
                        finally:
                            state[1] = observer # put back the old observer

        if have_new:
            previous = self._current_val
            if self._reset is not _sentinel and new is not self._reset:
                # discrete cells are always "changed" if new non-reset value
                previous = self._reset
                ctrl.change(self)  # make sure we have a chance to reset

        elif self._reset is not _sentinel:
            # discrete cells reset if there's no new value set or calc'd
            new = self._reset
            have_new = True
            previous = self._current_val

        else:
            # No new value and not discrete?  Then no change.
            return False

        # We have a new value, but has it actually changed?
        if new is not previous and new != previous:

            # Yes, update our state and notify listeners
            self._current_val = new
            self._changed_as_of = pulse
            notify = ctrl.notify

            for c in self._listeners:
                c = c()
                if c is not None:
                    c = c.owner()
                    if c is not None and c._version is not pulse:
                        notify(c)
                        
            if have_new is _sentinel:
                # We no longer have any dependencies, so turn Constant
                self._mailbox = self._listeners = self._rule = None
                self.__class__ = Constant

            return have_new     # <- faster than a 'return True'

        # implicit 'return None' is faster than explicitly returning False


    def __repr__(self):
        e = ('', ', discrete[%r]'% self._reset)[self._reset is not _sentinel]
        return "%s(%r, %r%s)" % (
            self.__class__.__name__, self._rule, self.value, e
        )

    def ensure_recalculation(self):
        """Ensure that this cell's rule will be (re)calculated"""
        pulse, observer, ctrl = self._state

        if observer is self:
            # repeat()
            self._mailbox.dependencies.insert(0, None)
            ctrl.change(self)

        elif self._rule is None:
            raise TypeError("Can't recalculate a cell without a rule")

        #elif observer and observer._state is not self._state:
        #    raise RuntimeError("Can't access cells in another task/thread")

        elif pulse is self._version:
            raise RuntimeError("Already recalculated")

        else:  
            self._mailbox.dependencies.append(None)
            ctrl.notify(self)


class InputConflict(Exception):
    """Attempt to set a cell to two different values during the same pulse"""
















class Constant(ReadOnlyCell):
    """An immutable cell that no longer depends on anything else"""
    __slots__ = ()
    value = ReadOnlyCell._current_val
    def get_value(self):
        """Get the value of this cell"""
        return self.value
    
    _can_freeze = False
    _mailbox = None

    def __init__(self, value):
        ReadOnlyCell._current_val.__set__(self, value)

    def __setattr__(self, name, value):
        """Constants can't be changed"""
        raise AttributeError("Constants can't be changed")

    def _check_dirty(self, state):
        return False

    def __repr__(self):
        return "Constant(%r)" % (self.value,)

def _cleanup(state):
    pulse, observer, ctrl = state
    while observer is None:
        if ctrl.now:
            for item in ctrl.now:
                item._check_dirty(state)
            del ctrl.now[:]
        if not ctrl.later:
            return    # no changes, stay in the current pulse

        # Begin a new pulse
        state[0] += 1
        ctrl.now = ctrl.later; ctrl.notify = ctrl.change
        ctrl.later = later = []; ctrl.change = later.append
        ctrl.cell.ensure_recalculation()


class Cell(ReadOnlyCell):
    """Spreadsheet-like cell with automatic updating"""
    _can_freeze = False
    __slots__ = '_writebuf'
    _writable = True

    def __new__(cls, rule=None, value=_sentinel, discrete=False):
        if value is _sentinel and rule is not None:
            return ReadOnlyCell(rule, None, discrete)
        return ReadOnlyCell.__new__(cls, rule, value, discrete)

    def __init__(self, rule=None, value=None, discrete=False):
        ReadOnlyCell.__init__(self, rule, value, discrete)
        self._writebuf = _sentinel

    def set_value(self, value):
        """Set the value of this cell"""
        pulse, observer, ctrl = state = self._state
        #if observer is None:
        #    XXX we should switch to current state here, if needed
        #elif observer._state is not state:
        #    raise RuntimeError("Can't access cells in another task/thread")
        if pulse is not self._version:
            if self._version is None:
                self._current_val = value
            self._check_dirty(state)
        old = self._writebuf
        if old is not _sentinel and old is not value and old!=value:
            raise InputConflict(old, value) # XXX
        self._writebuf = value
        ctrl.change(self)
        if not observer:
            _cleanup(state)

    value = property(ReadOnlyCell.get_value, set_value)


def current_pulse():    return _get_state()[0]
def current_observer(): return _get_state()[1]


class CellValues(roles.Registry):
    """Registry for cell values"""

class CellRules(roles.Registry):
    """Registry for cell rules"""

class _Defaulting(roles.Registry):
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

class IsDiscrete(_Defaulting):
    """Registry for flagging that a cell is an event"""

def default_factory(typ, ob, name):
    """Default factory for making cells"""
    rule = CellRules(typ).get(name)
    value = CellValues(typ).get(name, _sentinel)
    if rule is not None:
        rule = rule.__get__(ob, typ)
    if value is _sentinel:
        return Cell(rule, discrete=IsDiscrete(typ).get(name, False))
    return Cell(rule, value, IsDiscrete(typ).get(name, False))

class Cells(roles.Role):
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
    _set_multi(sys._getframe(1), attrs, _discrete, 'value')

def todos(**attrs):
    """Define multiple todo-cell attributes"""
    _set_multi(sys._getframe(1), attrs, _todo)


def optional(func):
    """Define a rule-cell attribute that's not automatically activated"""
    return _invoke_callback([(IsOptional, True)], func)

def receiver(value):
    """Define a receiver-cell attribute"""
    return _discrete(None, value, __frame=sys._getframe(1))

def _discrete(func=_sentinel, value=_sentinel, **kw):
    items = [(IsDiscrete, True), (CellFactories, default_factory)]
    return _invoke_callback(items, func, value, **kw)

def todo(func):
    """Define an attribute that can send "messages to the future" """
    return _todo(func, __frame=sys._getframe(1))

def _todo(func, **kw):
    if isinstance(func, CellProperty):
        raise TypeError("@todo decorator must wrap a function directly")
    else:
        items = [
            (CellRules, func), (CellFactories, todo_factory),
            (CellValues, None), (IsDiscrete, True),
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
    pulse, observer, ctrl = _get_state()
    if observer:
        return ctrl.cell.value
    else:
        raise RuntimeError("poll() must be called from a rule")


def discrete(func):
    """Define a discrete rule attribute"""
    return _discrete(func, __frame=sys._getframe(1))






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
                if not cell._writable:
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
        IsDiscrete.for_frame(frame).defaults[name] = False
        IsOptional.for_frame(frame).defaults[name] = False
        CellFactories.for_frame(frame).defaults[name] = default_factory
        return __proptype(name)

    if name:
        return callback(frame, name, func, None)
    else:
        decorators.decorate_assignment(callback, frame=frame)
        return _sentinel












class TodoProperty(CellProperty):
    """Property representing a ``todo`` attribute"""
    decorators.decorate(property)
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
    def wrap(__method,__get_state,__cleanup,__Cell):
        """
        __pulse, __observer, __ctrl = __state = __get_state()
        if __observer:
            return __method($args)
        __state[1] = __Cell()
        try:
            return __method($args)
        finally:
            __state[1] = __observer; __cleanup(__state)"""
    return decorators.template_function(wrap)(method,_get_state,_cleanup,Cell)

