from thread import get_ident
from weakref import ref
from peak.util import symbols, addons, decorators
import sys, UserDict, UserList, sets, stm
from peak.util.extremes import Max

__all__ = [
    'Cell', 'Constant', 'rule', 'rules', 'value', 'values', 'optional',
    'todo', 'todos', 'modifier', 'receiver', 'receivers', 'Component',
    'discrete', 'repeat', 'poll', 'InputConflict', 'observer', 'ObserverCell',
    'Dict', 'List', 'Set', 'task', 'resume', 'Pause', 'Return', 'TaskCell',
    'dirty', 'ctrl',
]

NO_VALUE = symbols.Symbol('NO_VALUE', __name__)
_sentinel = NO_VALUE

class InputConflict(Exception):
    """Attempt to set a cell to two different values during the same pulse"""






















class AbstractCell(object):
    """Base class for cells"""
    __slots__ = ()

    rule = value = _value = _needs_init = None

    def get_value(self):
        """Get the value of this cell"""
        return self.value

    def __repr__(self):
        rule = reset = ni = ''
        if getattr(self, 'rule', None) is not None:
            rule = repr(self.rule)+', '
        if self._needs_init:
            ni = ' [uninitialized]'
        if getattr(self, '_reset', _sentinel) is not _sentinel:
            reset =', discrete['+repr(self._reset)+']'
        return '%s(%s%r%s%s)'% (
            self.__class__.__name__, rule, self._value, ni, reset
        )




















class _ReadValue(stm.AbstractSubject, AbstractCell):
    """Base class for readable cells"""

    __slots__ = '_value', 'next_listener', '_set_by', '_reset', # XXX 'manager'

    def __init__(self, value=None, discrete=False):
        self._value = value
        self._set_by = _sentinel
        stm.AbstractSubject.__init__(self)
        self._reset = (_sentinel, value)[bool(discrete)]

    def get_value(self):
        if ctrl.active:
            # if atomic, make sure we're locked and consistent
            used(self)
        return self._value

    value = property(get_value)

    def _finish(self):
        if self._set_by is not _sentinel:
            change_attr(self, '_set_by', _sentinel)
        if self._reset is not _sentinel and self._value != self._reset:
            change_attr(self, '_value', self._reset)
            changed(self)
















class Value(_ReadValue):
    """A read-write value with optional discrete mode"""

    __slots__ = ('__weakref__')

    def set_value(self, value):
        if not ctrl.active:
            return atomically(self.set_value, value)

        lock(self)
        if self._set_by is _sentinel:
            change_attr(self, '_set_by', ctrl.current_listener)
            on_commit(self._finish)

        if value is self._value:
            return  # no change, no foul...

        if value!=self._value:
            if self._set_by is not ctrl.current_listener:
                # already set by someone else
                raise InputConflict(self._value, value) #self._set_by) #, value, ctrl.current_listener) # XXX
            changed(self)

        change_attr(self, '_value', value)

    value = property(_ReadValue.get_value.im_func, set_value)


def install_controller(controller):
    global ctrl
    stm.ctrl = ctrl = controller
    for name in [
        'on_commit', 'on_undo', 'atomically', 'manage', 'savepoint',
        'rollback_to', 'schedule', 'cancel', 'lock', 'used', 'changed',
        'run_rule', 'change_attr',
    ]:
        globals()[name] = getattr(ctrl, name)
        if name not in __all__: __all__.append(name)

install_controller(stm.LocalController())

class ReadOnlyCell(_ReadValue, stm.AbstractListener):
    """A cell with a rule"""
    __slots__ = 'rule', '_needs_init', 'next_subject', '__weakref__', 'layer'

    def __init__(self, rule, value=None, discrete=False):
        super(ReadOnlyCell, self).__init__(value, discrete)
        stm.AbstractListener.__init__(self)
        self._needs_init = True
        self.rule = rule
        self.layer = 0

    def get_value(self):
        if self._needs_init:
            if not ctrl.active:
                # initialization must be atomic
                atomically(schedule, self)
                return self._value
            else:
                cancel(self); run_rule(self, False)
        if ctrl.current_listener is not None:
            used(self)
        return self._value

    value = property(get_value)

    def run(self):
        if self._needs_init:
            change_attr(self, '_needs_init', False)
            change_attr(self, '_set_by', self)
            change_attr(self, '_value', self.rule())
            on_commit(self._finish)
        else:
            value = self.rule()
            if value!=self._value:
                if self._set_by is _sentinel:
                    change_attr(self, '_set_by', self)
                    on_commit(self._finish)
                change_attr(self, '_value', value)
                changed(self)
        if not ctrl.reads: on_commit(self._check_const)

    def _check_const(self):
        if self.next_subject is None and (
            self._reset is _sentinel or self._value==self._reset
        ):
            change_attr(self, '_set_by', _sentinel)
            change_attr(self, 'rule', None)
            change_attr(self, 'next_listener', None)
            change_attr(self, '__class__', ConstantRule)


class _ConstantMixin(AbstractCell):
    """A read-only abstract cell"""

    __slots__ = ()

    def __setattr__(self, name, value):
        """Constants can't be changed"""
        raise AttributeError("Constants can't be changed")

    def __repr__(self):
        return "Constant(%r)" % (self.value,)


class Constant(_ConstantMixin):
    """A pure read-only value"""

    __slots__ = 'value'

    def __init__(self, value):
        Constant.value.__set__(self, value)











class ConstantRule(_ConstantMixin, ReadOnlyCell):
    """A read-only cell that no longer depends on anything else"""

    __slots__ = ()

    value = ReadOnlyCell._value

    def dirty(self):
        """Constants don't need recalculation"""
        return False

    def run(self):
        """Constants don't run"""

    def __setattr__(self, name, value):
        """Constants can't be changed"""
        if name == '__class__':
            object.__setattr__(self, name, value)
        else:
            super(ConstantRule, self).__setattr__(name, value)


class ObserverCell(stm.AbstractListener, AbstractCell):
    """Rule that performs non-undoable actions"""

    __slots__ = 'run', 'next_subject', '__weakref__'

    layer = Max

    def __init__(self, rule):
        self.run = rule
        super(ObserverCell, self).__init__()
        atomically(schedule, self)

ObserverCell.rule = ObserverCell.run    # alias the attribute for inspection






class Cell(ReadOnlyCell, Value):
    """Spreadsheet-like cell with automatic updating"""

    __slots__ = ()

    def __new__(cls, rule=None, value=_sentinel, discrete=False):
        if value is _sentinel and rule is not None:
            return ReadOnlyCell(rule, None, discrete)
        elif rule is None:
            return Value([value,None][value is _sentinel], discrete)
        return ReadOnlyCell.__new__(cls, rule, value, discrete)

    def _check_const(self): pass    # we can never become Constant

    def get_value(self):
        if self._needs_init:
            if not ctrl.active:
                atomically(schedule, self)  # initialization must be atomic
                return self._value
            if self._set_by is _sentinel:
                # No value set yet, so we have to run() first
                cancel(self); run_rule(self, False)
        if ctrl.current_listener is not None:
            used(self)
        return self._value

    def set_value(self, value):
        if not ctrl.active:
            return atomically(self.set_value, value)
        super(Cell, self).set_value(value)
        if self._needs_init:
            schedule(self)

    value = property(get_value, set_value)

    def dirty(self):
        # If we've been manually set, don't reschedule
        who = self._set_by
        return who is _sentinel or who is self


    def run(self):
        if self.dirty():
            # Nominal case: the value hasn't been set in this txn, or was only
            # set by the rule itself.
            super(Cell, self).run()
        elif self._needs_init:
            # Initialization case: value was set before reading, so we ignore
            # the return value of the rule and leave our current value as-is,
            # but of course now we will notice any future changes
            change_attr(self, '_needs_init', False)
            self.rule()
        else:
            # It should be impossible to get here unless you run the cell
            # manually.  Don't do that.  :)
            raise AssertionError("This should never happen!")


def modifier(func):
    """Mark a function as performing modifications to Trellis data

    The wrapped function will always run atomically, and if called from inside
    a rule, reads performed in the function will not become dependencies of the
    caller.
    """
    def wrap(__func, __module):
        """
        if not __module.ctrl.active:
            return __module.atomically(__func, $args)
        elif __module.ctrl.current_listener is None:
            return __func($args)
        else:
            # Prevent any reads from counting against the current rule
            old_reads, __module.ctrl.reads = __module.ctrl.reads, {}
            try:
                return __func($args)
            finally:
                __module.ctrl.reads = old_reads
        """
    return decorators.template_function(wrap)(func, sys.modules[__name__])


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

def observer(func):
    """Define an observer cell attribute"""
    return _rule(func, '@observer', observer_factory, [(CellValues, NO_VALUE)],
        __frame=sys._getframe(1)
    )


class Component(decorators.classy):
    """Base class for objects with Cell attributes"""

    __slots__ = ()

    decorators.decorate(classmethod, modifier)
    def __class_call__(cls, *args, **kw):
        rv = super(Component, cls).__class_call__(*args, **kw)
        if isinstance(rv, cls):
            cells = Cells(rv)
            for k, v in IsOptional(cls).iteritems():
                if not v and k not in cells:
                    c = cells.setdefault(k, CellFactories(cls)[k](cls, rv, k))
                    c.value     # XXX
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
    if ctrl.current_listener is not None:
        on_commit(schedule, ctrl.current_listener)
    else:
        raise RuntimeError("repeat() must be called from a rule")

def poll():
    """Recalculate this rule the next time *any* other cell is set"""
    listener = ctrl.current_listener
    if listener is None or not hasattr(listener, '_needs_init'):
        raise RuntimeError("poll() must be called from a rule")
    else:
        return ctrl.pulse.value

def dirty():
    """Force the current rule's return value to be treated as if it changed"""
    assert ctrl.current_listener is not None, "dirty() must be called from a rule"
    changed(ctrl.current_listener)






















class TaskCell(AbstractCell, stm.AbstractListener):
    """Cell that manages a generator-based task"""
    
    __slots__ = (
        '_result', '_error', '_step', 'next_subject', 'layer', '_loop',
        '_scheduled', '__weakref__',
    )

    def __init__(self, func):
        self._step = self._stepper(func)
        self.layer = 0
        self.next_subject = None
        from activity import EventLoop
        self._loop = EventLoop.get()
        self._scheduled = False
        atomically(self.dirty)

    def dirty(self):
        if not self._scheduled:
            change_attr(self, '_scheduled', True)
            on_commit(self._loop.call, atomically, self.do_run)
            on_commit(change_attr, self, '_scheduled', False)
        return False


















    def _stepper(self, func):
        VALUE = self._result = []
        ERROR = self._error  = []               
        STACK = [func()]
        CALL = STACK.append
        RETURN = STACK.pop

        def _step():
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
            if STACK and not ERROR and not ctrl.reads:
                ctrl.current_listener.dirty()    # re-run if still running
            return resume()

        return _step


    def do_run(self):
        ctrl.current_listener = self
        try:
            try:
                self._step()
                # process writes as if from a non-rule perspective
                writes = ctrl.writes
                has_run = ctrl.has_run.get
                while writes:
                    subject, writer = writes.popitem()
                    for dependent in subject.iter_listeners():
                        if has_run(dependent) is not self:
                            if dependent.dirty():
                                schedule(dependent)

                # process reads in normal fashion
                ctrl._process_reads(self)

            except:
                ctrl.reads.clear()
                ctrl.writes.clear()
                raise           
        finally:
            ctrl.current_listener = None

Pause = symbols.Symbol('Pause', __name__)

decorators.struct()
def Return(value):
    """Wrapper for yielding a value from a task"""
    return value,










def resume():
    """Get the result of a nested task invocation (needed for Python<2.5)"""
    c = ctrl.current_listener
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

def task_factory(typ, ob, name):
    return default_factory(typ, ob, name, TaskCell)

def observer_factory(typ, ob, name):
    return default_factory(typ, ob, name, ObserverCell)

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
                if not hasattr(cell, 'set_value'):
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
            if not ctrl.active:
                raise RuntimeError("future can only be accessed from a @modifier")
            try: cells = ob.__cells__
            except AttributeError: cells = Cells(ob)
            try:
                cell = cells[name]
            except KeyError:
                typ = type(ob)
                cell = CellFactories(typ)[name](typ, ob, name)
                cell = cells.setdefault(name, cell)
            if cell._set_by is _sentinel:
                cell.value = CellRules(type(ob))[name].__get__(ob)()
                changed(cell)
            return cell._value
        return property(get, doc="The future value of the %r attribute" % name)


def todo_factory(typ, ob, name):
    """Factory for ``todo`` cells"""
    rule = CellRules(typ).get(name).__get__(ob, typ)
    return Cell(None, rule(), True)












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
                if key in data: del data[key]   # XXX
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
            dirty(); return self.updated
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

  


  




