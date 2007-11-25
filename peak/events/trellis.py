from thread import get_ident
from weakref import ref
from peak.util import symbols, addons, decorators
import sys, UserDict, UserList, sets

__all__ = [
    'Cell', 'Constant', 'rule', 'rules', 'value', 'values', 'optional',
    'todo', 'todos', 'modifier', 'receiver', 'receivers', 'Component',
    'discrete', 'repeat', 'poll', 'InputConflict', 'action', 'ActionCell',
    'Dict', 'List', 'Set', 'task', 'resume', 'Pause', 'Return', 'TaskCell',
    'dirty',
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
        self.action = DummyAction()

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
    _writable = _const_type = False
    _is_action = False

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
            observer.observe(self)
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
        state[1] = self    # we are the observer while calculating/comparing
        try:
            new = self._writebuf
            have_new = False
            if new is not _sentinel:
                # We were assigned a value in the previous pulse
                self._writebuf = _sentinel
                have_new = True
            if self._rule and (not have_new or self._changed_as_of==-1):
                # We weren't assigned a value, see if we need to recalc
                for d in self._mailbox.dependencies:
                    if (not d or d._changed_as_of is pulse
                         or d._version is not pulse and d._check_dirty(state)
                    ):  # one of our dependencies changed, recalc
                        self._mailbox = m = Mailbox(self)  # break old deps
                        if self._changed_as_of==-1: self._rule(); dirty()
                        else: new = self._rule()
                        have_new = True
                        if not m.dependencies and self._can_freeze:
                            have_new = _sentinel    # flag for freezing
                        break   
            if have_new:
                previous = self._current_val
                if self._reset is not _sentinel and new is not self._reset:
                    # discrete cells are always "changed" if new non-reset value
                    previous = self._reset
                    ctrl.change(self)  # make sure we have a chance to reset
            elif self._reset is not _sentinel:
                # discrete cells reset if there's no new value set or calc'd
                new = self._reset
                previous = self._current_val
                have_new = (new != previous)
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
                self.__class__ = self._const_type or Constant
    
            return have_new

        finally:
            state[1] = observer # put back the old observer


    def __repr__(self):
        e = ('', ' [out-of-date]')[self._version is not _get_state()[0]]
        e += ('', ', discrete[%r]'% self._reset)[self._reset is not _sentinel]
        return "%s(%r, %r%s)" % (
            self.__class__.__name__, self._rule, self._current_val, e
        )

    def observe(self, dep):
        mailbox = self._mailbox
        depends = mailbox.dependencies
        listeners = dep._listeners
        if dep not in depends: depends.append(dep)
        r = ref(mailbox, listeners.remove)
        if r not in listeners: listeners.append(r)

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


class ActionCell(ReadOnlyCell):
    """Cell type for @action rules and @modifier functions"""
    __slots__ = ()
    _is_action = True

    def get_value(self):
        pulse, observer, ctrl = self._state
        if observer is None:
            return ReadOnlyCell.get_value(self)
        raise RuntimeError("No rule may depend on the result of an action")

    value = property(get_value)
    def __init__(self, rule): ReadOnlyCell.__init__(self,rule,None,False)

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
        #ReadOnlyCell._state.__set__(self, _get_state())

    def __setattr__(self, name, value):
        """Constants can't be changed"""
        raise AttributeError("Constants can't be changed")
    def _check_dirty(self, state): return False
    def observe(self, dep): pass
    def __repr__(self):
        return "%s(%r)" % (type(self).__name__, self.value)
    def ensure_recalculation(self):
        raise TypeError("Can't recalculate a cell without a rule")

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
            if self._version is None:   # new, unread/unwritten cell
                self._writebuf = self._current_val = value; self._changed_as_of = -1
                ctrl.notify(self)   # schedule for recalc in this pulse
                if not observer:
                    _cleanup(state)
                return
            self._check_dirty(state)
        if observer is not None and not observer._is_action:
            raise RuntimeError("Cells can't be changed by non-@action rules")
        old = self._writebuf
        if old is not _sentinel and old is not value and old!=value:
            raise InputConflict(old, value) # XXX
        self._writebuf = value
        ctrl.change(self)
        if not observer: _cleanup(state)

    value = property(ReadOnlyCell.get_value, set_value)

def current_pulse():    return _get_state()[0]
def current_observer(): return _get_state()[1]

class _Defaulting(addons.Registry):
    def __init__(self, subject):
        self.defaults = {}
        return super(_Defaulting, self).__init__(subject)

    def created_for(self, cls):
        for k,v in self.defaults.items():
            self.setdefault(k, v)
        return super(_Defaulting, self).created_for(cls)

class CellFactories(_Defaulting):     """Registry for cell factories"""
class CellValues(addons.Registry):    """Registry for cell values"""
class CellRules(addons.Registry):     """Registry for cell rules"""
class IsDiscrete(_Defaulting): "Registry for flagging that a cell is an event"

class IsOptional(_Defaulting):
    """Registry for flagging that an attribute need not be activated"""
    def created_for(self, cls):
        _Defaulting.created_for(self, cls)
        for k in self:
            if k in cls.__dict__ \
            and not isinstance(cls.__dict__[k], CellProperty):
                # Don't create a cell for overridden non-CellProperty attribute 
                self[k] = True

def default_factory(typ, ob, name, celltype=Cell):
    """Default factory for making cells"""
    rule = CellRules(typ).get(name)
    value = CellValues(typ).get(name, _sentinel)
    if rule is not None:
        rule = rule.__get__(ob, typ)
    if value is _sentinel:
        if IsDiscrete(typ).get(name, False):
            return celltype(rule, discrete=True)
        return celltype(rule)
    return celltype(rule, value, IsDiscrete(typ).get(name, False))


class Cells(addons.AddOn):
    __slots__ = ()
    addon_key = classmethod(lambda cls: '__cells__')
    def __new__(cls, subject): return {}

def rule(func):
    """Define a rule cell attribute"""
    return _rule(func, __frame=sys._getframe(1))

def _rule(func, deco='@rule', factory=default_factory, extras=(), **kw):
    if isinstance(func, CellProperty):
        raise TypeError(deco+" decorator must wrap a function directly")
    else:
        items = [(CellRules, func), (CellFactories, factory)] + list(extras)
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

def discrete(func):
    """Define a discrete rule attribute"""
    return _discrete(func, __frame=sys._getframe(1))

def action(func):
    """Define an action cell attribute"""
    return _rule(func, '@action', action_factory, [(CellValues, NO_VALUE)],
        __frame=sys._getframe(1)
    )


class Component(decorators.classy):
    """Base class for objects with Cell attributes"""

    __slots__ = ()

    decorators.decorate(classmethod)
    def __class_call__(cls, *args, **kw):
        pulse, observer, ctrl = state = _get_state()
        if observer is not None and observer._is_action:
            return super(Component, cls).__class_call__(*args, **kw)
        state[1] = ctrl.action
        try:
            rv = super(Component, cls).__class_call__(*args, **kw)
            if isinstance(rv, cls):
                cells = Cells(rv)
                for k, v in IsOptional(cls).iteritems():
                    if not v and k not in cells:
                        ctrl.notify(
                            cells.setdefault(k,
                                CellFactories(cls)[k](cls, rv, k))
                        )
        finally:
            state[1] = observer
        if observer is None:
            _cleanup(state)
        return rv
            
    def __init__(self, **kw):
        if kw:
            cls = type(self)
            for k, v in kw.iteritems():
                if not hasattr(cls, k):
                    raise TypeError("%s() has no keyword argument %r"
                        % (cls.__name__, k)
                    )
                setattr(self, k, v)





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

def dirty():
    """Force the current rule's return value to be treated as if it changed"""
    current_observer()._current_val = _sentinel


class DummyAction(Constant):
    """Placeholder cell used by @modifier and Component() to enter mod state"""

    __slots__ = ()   
    _is_action = True

    def __init__(self):
        Constant.__init__(self, None)


AbstractCell = ReadOnlyCell     # XXX









class TaskCell(ActionCell):
    """Cell that manages a generator-based task"""
    __slots__ = '_result', '_error'

    def __init__(self, func):
        VALUE = self._result = []
        ERROR = self._error  = []               
        STACK = [func()]; CALL = STACK.append; RETURN = STACK.pop;
        def step():
            while STACK:
                try:
                    it = STACK[-1]
                    if VALUE and hasattr(it, 'send'):
                        rv = it.send(VALUE[0])
                    elif ERROR and hasattr(it, 'throw'):
                        rv = it.throw(*ERROR.pop())
                    else:
                        rv = it.next()
                except:
                    del VALUE[:]
                    ERROR.append(sys.exc_info())
                    if ERROR[-1][0] is StopIteration:
                        ERROR.pop() # not really an error
                    RETURN()
                else:
                    del VALUE[:]
                    if rv is Pause:
                        break
                    elif hasattr(rv, 'next'):
                        CALL(rv); continue
                    elif isinstance(rv, Return):
                        rv = rv.value
                    VALUE.append(rv)
                    if len(STACK)==1: break
                    RETURN()
            if STACK and not ERROR and not current_observer()._mailbox.dependencies:
                repeat()    # don't become Constant while still running
            return resume()

        ReadOnlyCell.__init__(self, step, None, False)

class CompletedTask(Constant, TaskCell):
    """Task that has exhausted its generator"""
    __slots__ = ()

TaskCell._const_type = CompletedTask

Pause = symbols.Symbol('Pause', __name__)

decorators.struct()
def Return(value):
    """Wrapper for yielding a value from a task"""
    return value,

def resume():
    """Get the result of a nested task invocation (needed for Python<2.5)"""
    c = current_observer()
    if not isinstance(c, TaskCell):
        raise RuntimeError("resume() must be called from a @trellis.task")
    elif c._result:
        return c._result[0]
    elif c._error:
        e = c._error.pop()
        try:
            raise e[0], e[1], e[2]
        finally:
            del e
    elif c._reset is not _sentinel:
        return c._reset
    else:
        return c._current_val

def task_factory(typ, ob, name):
    return default_factory(typ, ob, name, TaskCell)

def action_factory(typ, ob, name):
    return default_factory(typ, ob, name, ActionCell)

def task(func):
    """Define a rule cell attribute"""
    return _rule(func, '@task', task_factory, __frame=sys._getframe(1))

class CellProperty(object):
    """Descriptor for cell-based attributes"""

    def __init__(self, name):
        self.__name__ = name

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.__name__)

    def __get__(self, ob, typ=None):
        if ob is None:
            return self
        try: cells = ob.__cells__
        except AttributeError: cells = Cells(ob)
        try:
            cell = cells[self.__name__]
        except KeyError:
            name = self.__name__
            cell = CellFactories(typ)[name](typ, ob, name)
            cell = cells.setdefault(name, cell)
        return cell.value

    def __set__(self, ob, value):
        try: cells = ob.__cells__
        except AttributeError: cells = Cells(ob)
        if isinstance(value, AbstractCell):
            cells[self.__name__] = value
        else:
            try:
                cell = cells[self.__name__]
            except KeyError:
                name = self.__name__
                typ = type(ob)
                cell =  CellFactories(typ)[name](typ, ob, name)
                if not cell._writable:
                    return cells.setdefault(name, Constant(value))
                cell = cells.setdefault(name, cell)
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
        if not isinstance(func, CellProperty):
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
            try: cells = ob.__cells__
            except AttributeError: cells = Cells(ob)
            try:
                cell = cells[name]
            except KeyError:
                typ = type(ob)
                cell = CellFactories(typ)[name](typ, ob, name)
                cell = cells.setdefault(name, cell)
            if cell._writebuf is _sentinel:
                pulse, observer, ctrl = _get_state()
                if not observer or not observer._is_action:
                    raise RuntimeError("future can only be accessed from a @modifier")
                cell.value = CellRules(type(ob))[name].__get__(ob)()
            return cell._writebuf            
        return property(get, doc="The future value of the %r attribute" % name)

def todo_factory(typ, ob, name):
    """Factory for ``todo`` cells"""
    rule = CellRules(typ).get(name).__get__(ob, typ)
    return Cell(None, rule(), True)

def modifier(method):
    """Mark a method as performing modifications to Trellis data"""
    def wrap(__method,__get_state,__cleanup):
        """
        __pulse, __observer, __ctrl = __state = __get_state()
        if __observer is not None:
            if __observer._is_action:
                return __method($args)
            raise RuntimeError("@modifiers can't be called from non-@action rules")
        __state[1] = __ctrl.action
        try:     return __method($args)
        finally: __state[1] = __observer; __cleanup(__state)"""
    return decorators.template_function(wrap)(method,_get_state,_cleanup)
class Dict(UserDict.IterableUserDict, Component):
    """Dictionary-like object that recalculates observers when it's changed

    The ``added``, ``changed``, and ``deleted`` attributes are dictionaries
    showing the current added/changed/deleted contents.  Note that ``changed``
    may include items that were set as of this recalc, but in fact have the
    same value as they had in the previous recalc, as no value comparisons are
    done!

    You may observe these attributes directly, but any rule that reads the
    dictionary in any way (e.g. gets items, iterates, checks length, etc.)
    will be recalculated if the dictionary is changed in any way.

    Any changes that happen to the dictionary are made "in the future", but all
    read operations are done "in the present" -- so you can't see the effect of
    any changes until the next Trellis recalculation.

    Note that this means operations like pop(), popitem(), and setdefault()
    that both read and write in the same operation are NOT supported, since
    reading must always happen in the present, whereas writing is done to the
    future version of the dictionary.
    """
    added = todo(lambda self: {})
    deleted = todo(lambda self: {})
    changed = todo(lambda self: {})

    to_add = added.future
    to_change = changed.future
    to_delete = deleted.future

    def __init__(self, other=(), **kw):
        Component.__init__(self)
        if other: self.data.update(other)
        if kw:    self.data.update(kw)

    def copy(self):
        return self.__class__(self.data)

    def get(self, key, failobj=None):
        return self.data.get(key, failobj)

    decorators.decorate(rule)    
    def data(self):
        data = self.data
        if data is None:
            data = {}
        if self.deleted:
            dirty()
            for key in self.deleted:
                del data[key]
        if self.added:
            dirty(); data.update(self.added)
        if self.changed:
            dirty(); data.update(self.changed)
        return data    

    decorators.decorate(modifier)    
    def __setitem__(self, key, item):
        if key in self.to_delete:
            del self.to_delete[key]
        if key in self.data:
            self.to_change[key] = item
        else:
            self.to_add[key] = item

    decorators.decorate(modifier)    
    def __delitem__(self, key):
        if key in self.to_add:
            del self.to_add[key]
        elif key in self.data and key not in self.to_delete:
            self.to_delete[key] = self.data[key]
            if key in self.to_change:
                del self.to_change[key]
        else:
            raise KeyError, key
                
    decorators.decorate(modifier)
    def clear(self):
        self.to_add.clear()
        self.to_change.clear()
        self.to_delete.update(self.data)

    decorators.decorate(modifier)    
    def update(self, d=(), **kw):
        if d:
            if kw:
                d = dict(d);  d.update(kw)
            elif not hasattr(d, 'iteritems'):
                d = dict(d)
        else:
            d = kw
        to_change = self.to_change
        to_add = self.to_add
        to_delete = self.to_delete
        data = self.data
        for k, v in d.iteritems():
            if k in to_delete:
                del to_delete[k]
            if k in data:
                to_change[k] = d[k]
            else:
                to_add[k] = d[k]

    def setdefault(self, key, failobj=None):
        """setdefault() is disallowed because it 'reads the future'"""
        raise InputConflict(
            "Can't read and write in the same operation"
        )
    def pop(self, key, *args):
        """The pop() method is disallowed because it 'reads the future'"""
        raise InputConflict(
            "Can't read and write in the same operation"
        )
    def popitem(self):
        """The popitem() method is disallowed because it 'reads the future'"""
        raise InputConflict(
            "Can't read and write in the same operation"
        )
    def __hash__(self):
        raise TypeError



class List(UserList.UserList, Component):
    """List-like object that recalculates observers when it's changed

    The ``changed`` attribute is True whenever the list has changed as of the
    current recalculation, and any rule that reads the list in any way (e.g.
    gets items, iterates, checks length, etc.) will be recalculated if the
    list is changed in any way.

    Any changes that happen to the list are made "in the future", but all read
    operations are done "in the present" -- so you can't see the effect of
    any changes until the next Trellis recalculation.

    Note that this type is not efficient for large lists, as a copy-on-write
    strategy is used in each recalcultion that changes the list.  If what you
    really want is e.g. a sorted read-only view on a set, don't use this.
    """

    updated = todo(lambda self: self.data[:])
    future  = updated.future
    changed = receiver(False)

    def __init__(self, other=(), **kw):
        Component.__init__(self, **kw)
        self.data[:] = other
    
    decorators.decorate(rule)    
    def data(self):
        if self.changed:
            return self.updated
        return self.data or []

    decorators.decorate(modifier)
    def __setitem__(self, i, item):
        self.changed = True
        self.future[i] = item

    decorators.decorate(modifier)
    def __delitem__(self, i):
        self.changed = True
        del self.future[i]

    decorators.decorate(modifier)
    def __setslice__(self, i, j, other):
        self.changed = True
        self.future[i:j] = other

    decorators.decorate(modifier)
    def __delslice__(self, i, j):
        self.changed = True
        del self.future[i:j]

    decorators.decorate(modifier)
    def __iadd__(self, other):
        self.changed = True
        self.future.extend(other)
        return self

    decorators.decorate(modifier)
    def append(self, item):
        self.changed = True
        self.future.append(item)

    decorators.decorate(modifier)
    def insert(self, i, item):
        self.changed = True
        self.future.insert(i, item)

    decorators.decorate(modifier)
    def extend(self, other):
        self.changed = True
        self.future.extend(other)

    decorators.decorate(modifier)
    def __imul__(self, n):
        self.changed = True
        self.future[:] = self.future * n
        return self





    decorators.decorate(modifier)
    def remove(self, item):
        self.changed = True
        self.future.remove(item)

    decorators.decorate(modifier)
    def reverse(self):
        self.changed = True
        self.future.reverse()

    decorators.decorate(modifier)
    def sort(self, *args, **kw):
        self.changed = True
        self.future.sort(*args, **kw)

    def pop(self, i=-1):
        """The pop() method isn't supported, because it 'reads the future'"""
        raise InputConflict(
            "Can't read and write in the same operation"
        )

    def __hash__(self):
        raise TypeError


















class Set(sets.Set, Component):
    """Mutable set that recalculates observers when it's changed

    The ``added`` and ``removed`` attributes can be watched for changes, but
    any rule that simply uses the set (e.g. iterates over it, checks for
    membership or size, etc.) will be recalculated if the set is changed.

    Any changes that happen to the set are made "in the future", but anything
    you read from the set is "in the present" -- so you can't see the effect of
    any changes until the next Trellis recalculation.
    """
    _added = todo(lambda self: set())
    _removed = todo(lambda self: set())
    added, removed = _added, _removed
    to_add = _added.future
    to_remove = _removed.future
    
    def __init__(self, iterable=None, **kw):
        """Construct a set from an optional iterable."""
        Component.__init__(self, **kw)
        if iterable is not None:
            # we can update self._data in place, since no-one has seen it yet
            sets.Set._update(self, iterable)

    decorators.decorate(rule)
    def _data(self):
        """The dictionary containing the set data."""
        data = self._data
        if data is None:
            data = {}
        if self.removed:
            dirty()
            for item in self.removed:
                if item in data: del data[item]
        if self.added:
            dirty(); data.update(dict.fromkeys(self.added, True))
        return data

    def __setstate__(self, data):
        self.__init__(data[0])

    def _binary_sanity_check(self, other):
        # Check that the other argument to a binary operation is also
        # a set, raising a TypeError otherwise.
        if not isinstance(other, set_like):
            raise TypeError, "Binary operation only permitted between sets"

    def pop(self):
        """The pop() method isn't supported, because it 'reads the future'"""
        raise InputConflict(
            "Can't read and write in the same operation"
        )

    decorators.decorate(modifier)
    def _update(self, iterable):
        to_remove = self.to_remove
        add = self.to_add.add
        for item in iterable:
            if item in to_remove:
                to_remove.remove(item)
            else:
                add(item)

    decorators.decorate(modifier)
    def add(self, item):
        """Add an element to a set (no-op if already present)"""
        if item in self.to_remove:
            self.to_remove.remove(item)
        elif item not in self._data:
            self.to_add.add(item)

    decorators.decorate(modifier)
    def remove(self, item):
        """Remove an element from a set (KeyError if not present)"""
        if item in self.to_add:
            self.to_add.remove(item)
        elif item in self._data and item not in self.to_remove:
            self.to_remove.add(item)
        else:
            raise KeyError(item)


    decorators.decorate(modifier)
    def clear(self):
        """Remove all elements from this set."""
        self.to_remove.update(self)
        self.to_add.clear()              

    def __ior__(self, other):
        """Update a set with the union of itself and another."""
        self._binary_sanity_check(other)
        self._update(other)
        return self

    def __iand__(self, other):
        """Update a set with the intersection of itself and another."""
        self._binary_sanity_check(other)
        self.intersection_update(other)
        return self

    decorators.decorate(modifier)
    def difference_update(self, other):
        """Remove all elements of another set from this set."""
        data = self._data
        to_add, to_remove = self.to_add, self.to_remove
        for item in other:
            if item in to_add: to_add.remove(item)
            elif item in data: to_remove.add(item)

    decorators.decorate(modifier)
    def intersection_update(self, other):
        """Update a set with the intersection of itself and another."""
        to_remove = self.to_remove
        to_add = self.to_add
        self.to_add.intersection_update(other)
        other = to_dict_or_set(other)
        for item in self._data:
            if item not in other:
                to_remove.add(item)
        return self


        
    decorators.decorate(modifier)
    def symmetric_difference_update(self, other):
        """Update a set with the symmetric difference of itself and another."""
        data = self._data
        to_add = self.to_add
        to_remove = self.to_remove
        for elt in to_dict_or_set(other):            
            if elt in to_add:
                to_add.remove(elt)      # Got it; get rid of it
            elif elt in to_remove:
                to_remove.remove(elt)   # Don't got it; add it
            elif elt in data:
                to_remove.add(elt)      # Got it; get rid of it
            else:
                to_add.add(elt)         # Don't got it; add it

try:
    set = set
except NameError:
    set = sets.Set
    frozenset = sets.ImmutableSet
    set_like = sets.BaseSet
    dictlike = dict, sets.BaseSet
else:
    set_like = set, frozenset, sets.BaseSet
    dictlike = (dict,) + set_like

def to_dict_or_set(ob):
    """Return the most basic set or dict-like object for ob
    If ob is a sets.BaseSet, return its ._data; if it's something we can tell
    is dictlike, return it as-is.  Otherwise, make a dict using .fromkeys()
    """
    if isinstance(ob, sets.BaseSet):
        return ob._data
    elif not isinstance(ob, dictlike):
        return dict.fromkeys(ob)
    return ob

  


