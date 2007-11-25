"""Software Transactional Memory and Observers"""

import weakref, sys, heapq
from peak.util.extremes import Max

try:
    import threading
except ImportError:
    import dummy_threading as threading

__all__ = [
    'STMHistory', 'AbstractSubject',  'Link', 'AbstractListener', 'Controller',
    'CircularityError', 'LocalController',
]


class CircularityError(Exception):
    """Rules arranged in an infinite loop"""


class AbstractSubject(object):
    """Abstract base for objects that can be linked via ``Link`` objects"""

    __slots__ = ()

    manager = None
    layer = 0

    def __init__(self):
        self.next_listener = None

    def iter_listeners(self):
        """Yield the listeners of this subject"""
        link = self.next_listener
        while link is not None:
            nxt = link.next_listener   # avoid unlinks breaking iteration
            ob = link()
            if ob is not None:
                yield ob
            link = nxt

class AbstractListener(object):
    """Abstract base for objects that can be linked via ``Link`` objects"""

    __slots__ = ()
    layer = 0

    def __init__(self):
        self.next_subject = None

    def iter_subjects(self):
        """Yield the listeners of this subject"""
        link = self.next_subject
        while link is not None:
            nxt = link.next_subject   # avoid unlinks breaking iteration
            if link.subject is not None:
                yield link.subject
            link = nxt

    def dirty(self):
        """Mark the listener dirty and query whether it should be scheduled

        If a true value is returned, the listener should be scheduled.  Note
        that this method is allowed to have side-effects, but must be
        idempotent.
        """
        return True















class Link(weakref.ref):
    """Dependency link"""
    __slots__ = [
        'subject','next_subject','prev_subject','next_listener','prev_listener'
    ]

    def __new__(cls, subject, listener):
        self = weakref.ref.__new__(Link, listener, _unlink_fn)
        self.subject = self.prev_listener = subject
        self.prev_subject = None    # listener link is via weak ref
        nxt = self.next_subject = listener.next_subject
        if nxt is not None:
            nxt.prev_subject = self
        nxt = self.next_listener = subject.next_listener
        if nxt is not None:
            nxt.prev_listener = self
        listener.next_subject = self
        subject.next_listener = self
        return self

    def unlink(self):
        """Deactivate the link and remove it from its lists"""
        nxt = self.next_listener
        prev = self.prev_listener
        if nxt is not None:
            nxt.prev_listener = prev
        if prev is not None and prev.next_listener is self:
            prev.next_listener = nxt
        prev = self.prev_subject
        nxt = self.next_subject
        if nxt is not None:
            nxt.prev_subject = prev
        if prev is None:
            prev = self()   # get head of list
        if prev is not None and prev.next_subject is self:
            prev.next_subject = nxt
        self.subject = self.next_subject = self.prev_subject = None
        self.next_listener = self.prev_listener = None

_unlink_fn = Link.unlink

class STMHistory(object):
    """Simple STM implementation using undo logging and context managers"""

    active = in_cleanup = False

    def __init__(self):
        self.undo = []      # [(func,args), ...]
        self.at_commit =[]       # [(func,args), ...]
        self.managers = {}  # [mgr]->seq #  (context managers to __exit__ with)

    def atomically(self, func=lambda:None, *args, **kw):
        """Invoke ``func(*args,**kw)`` atomically"""
        if self.active:
            return func(*args, **kw)
        self.active = True
        try:
            try:
                retval = func(*args, **kw)
                self.cleanup()
                return retval
            except:
                self.cleanup(*sys.exc_info())
        finally:
            self.active = False

    def manage(self, mgr):
        assert self.active, "Can't manage without active history"
        if mgr not in self.managers:
            mgr.__enter__()
            self.managers[mgr] = len(self.managers)

    def on_undo(self, func, *args):
        """Call `func(*args)` if atomic operation is undone"""
        assert self.active, "Can't record undo without active history"
        self.undo.append((func, args))

    def savepoint(self):
        """Get a savepoint suitable for calling ``rollback_to()``"""
        return len(self.undo)


    def rollback_to(self, sp=0):
        """Rollback to the specified savepoint"""
        assert self.active, "Can't rollback without active history"
        undo = self.undo
        while len(undo) > sp:
            f, a = undo.pop()
            f(*a)

    def cleanup(self, typ=None, val=None, tb=None):
        # Exit the processing loop, unwinding managers
        assert self.active, "Can't exit when inactive"
        assert not self.in_cleanup, "Can't invoke cleanup while in cleanup"
        self.in_cleanup = True

        if typ is None:
            try:
                for (f,a) in self.at_commit: f(*a)
            except:
                typ, val, tb = sys.exc_info()
        if typ is not None:
            try:
                self.rollback_to(0)
            except:
                typ, val, tb = sys.exc_info()

        managers = [(posn,mgr) for (mgr, posn) in self.managers.items()]
        managers.sort()
        self.managers.clear()
        try:
            while managers:
                try:
                    managers.pop()[1].__exit__(typ, val, tb)
                except:
                    typ, val, tb = sys.exc_info()
            if typ is not None:
                raise typ, val, tb
        finally:
            del self.at_commit[:], self.undo[:]
            self.in_cleanup = False
            typ = val = tb = None

    def setattr(self, ob, attr, val):
        """Set `ob.attr` to `val`, w/undo log to restore the previous value"""
        self.on_undo(setattr, ob, attr, getattr(ob, attr))
        setattr(ob, attr, val)

    def on_commit(self, func, *args):
        """Call `func(*args)` if atomic operation is committed"""
        assert self.active, "Not in an atomic operation"
        self.at_commit.append((func, args))
        self.undo.append((self.at_commit.pop,()))































class Controller(STMHistory):
    """STM History with support for subjects, listeners, and queueing"""

    last_listener = current_listener = last_notified = last_save = None
    readonly = False

    def __init__(self):
        super(Controller, self).__init__()
        self.reads = {}
        self.writes = {}
        self.has_run = {}   # listeners that have run
        self.layers = []    # heap of layer numbers
        self.queues = {}    # [layer]    -> dict of listeners to be run
        self.to_retry = {}

    def cleanup(self, *args):
        try:
            self.has_run.clear()
            return super(Controller, self).cleanup(*args)
        finally:
            self.current_listener = self.last_listener = None
            self.last_notified = self.last_save = None

    def _retry(self):
        try:    # undo back through listener, watching to detect cycles
            todo = self.to_retry.copy(); destinations = set(todo)
            routes = {} # tree of rules that (re)triggered the original listener
            while todo:
                this = self.last_listener
                if self.last_notified:
                    via = destinations.intersection(self.last_notified)
                    if via:
                        routes[this] = via; destinations.add(this)
                self.rollback_to(self.last_save)
                if this in todo: del todo[this]
            for item in self.to_retry:
                if item in routes:
                    raise CircularityError(routes)
        finally:
            self.to_retry.clear()

    def run(self, listener):
        """Run the specified listener"""
        old = self.current_listener
        self.current_listener = listener
        if listener.layer is Max:
            self.readonly = True
        try:
            assert listener not in self.has_run, "Re-run of rule without retry"

            if old is not None:
                self.has_run[listener] = self.has_run[old]
                self.on_undo(self.has_run.pop, listener, None)

                old_reads, self.reads = self.reads, {}
                try:
                    listener.run()
                    self._process_reads(listener)
                finally:
                    self.reads = old_reads

            else:
                self.setattr(self, 'last_save', self.savepoint())
                self.setattr(self, 'last_listener', listener)
                self.has_run[listener] = listener
                self.on_undo(self.has_run.pop, listener, None)
                try:
                    listener.run()
                    self._process_writes(listener)
                    self._process_reads(listener)
                except:
                    self.reads.clear()
                    self.writes.clear()
                    raise
        finally:
            self.current_listener = old
            self.readonly = False





    def _process_writes(self, listener):
        #
        # Remove changed items from self.writes and notify their listeners,
        # keeping a record in self.last_notified so that we can figure out
        # later what caused a cyclic dependency (if one happens).
        #
        notified = {}
        self.setattr(self, 'last_notified', notified)
        writes = self.writes
        layer = listener.layer
        has_run = self.has_run
        while writes:
            subject, ignore = writes.popitem()
            for dependent in subject.iter_listeners():
                if has_run.get(dependent) is not listener:
                    if dependent.dirty():
                        self.schedule(dependent, layer)
                        notified[dependent] = 1

    def _process_reads(self, listener):
        #
        # Remove subjects from self.reads and link them to `listener`
        # (Old subjects of the listener are deleted, and self.reads is cleared
        #
        subjects = self.reads

        link = listener.next_subject
        while link is not None:
            nxt = link.next_subject   # avoid unlinks breaking iteration
            if link.subject in subjects:
                del subjects[link.subject]
            else:
                self.undo.append((Link, (link.subject, listener)))
                link.unlink()
            link = nxt

        while subjects:
            self.undo.append(
                (Link(subjects.popitem()[0], listener).unlink, ())
            )

    def schedule(self, listener, source_layer=None, reschedule=False):
        """Schedule `listener` to run during an atomic operation

        If an operation is already in progress, it's immediately scheduled, and
        its scheduling is logged in the undo queue (unless it was already
        scheduled).

        If `source_layer` is specified, ensure that the listener belongs to
        a higher layer than the source, moving the listener from an existing
        queue layer if necessary.  (This layer elevation is intentionally
        NOT undo-logged, however.)
        """
        new = old = listener.layer
        get = self.queues.get
        assert not self.readonly or old is Max, \
            "Shouldn't be scheduling a non-Observer during commit"

        if source_layer is not None and source_layer >= listener.layer:
            new = source_layer + 1

        if listener in self.has_run:
            self.to_retry[self.has_run[listener]]=1

        q = get(old)
        if q and listener in q:
            if new is not old:
                self.cancel(listener)
        elif self.active and not reschedule:
            self.on_undo(self.cancel, listener)

        if new is not old:
            listener.layer = new
            q = get(new)

        if q is None:
             q = self.queues[new] = {listener:1}
             heapq.heappush(self.layers, new)
        else:
            q[listener] = 1


    def cancel(self, listener):
        """Prevent the listener from being recalculated, if applicable"""
        q = self.queues.get(listener.layer)
        if q and listener in q:
            del q[listener]
            if not q:
                del self.queues[listener.layer]
                self.layers.remove(listener.layer)
                self.layers.sort()  # preserve heap order

    def atomically(self, func=lambda:None, *args, **kw):
        """Invoke ``func(*args,**kw)`` atomically"""
        if self.active:
            return func(*args, **kw)
        return super(Controller,self).atomically(self._process, func, args, kw)

    def _process(self, func, args, kw):
        try:
            retval = func(*args, **kw)
            layers = self.layers
            queues = self.queues
            while layers or self.at_commit:
                while layers:
                    if self.to_retry:
                        self._retry()
                    q = queues[layers[0]]
                    if q:
                        listener = q.popitem()[0]
                        self.on_undo(self.schedule, listener, None, True)
                        self.run(listener)
                    else:
                        del queues[layers[0]]
                        heapq.heappop(layers)
                self.cleanup()
            return retval
        except:
            del self.layers[:]
            self.queues.clear()
            raise


    def lock(self, subject):
        assert self.active, "Subjects must be accessed atomically"
        manager = subject.manager
        if manager is not None and manager not in self.managers:
            self.manage(manager)

    def used(self, subject):
        self.lock(subject)
        cl = self.current_listener
        if cl is not None and subject not in self.reads:
            self.reads[subject] = 1
            if subject.layer >= cl.layer:
                cl.layer = subject.layer + 1

    def changed(self, subject):
        self.lock(subject)
        if self.current_listener is not None:
            self.writes[subject] = 1
        else:
            for listener in subject.iter_listeners():
                if listener.dirty():
                    self.schedule(listener)
        if self.readonly:
            raise RuntimeError("Can't change objects during commit phase")


class LocalController(Controller, threading.local):
    """Thread-local Controller"""

ctrl = LocalController()

from trellis import _sentinel, InputConflict    # XXX









class AbstractCell(object):
    """Base class for cells"""
    __slots__ = ()

    value = None

    def get_value(self):
        """Get the value of this cell"""
        return self.value

    def __repr__(self):
        rule = reset = ''
        if getattr(self, 'rule', None) is not None:
            rule = repr(self.rule)+', '
        if getattr(self, '_reset', _sentinel) is not _sentinel:
            reset =' ['+repr(self._reset)+']'
        return '%s(%s%r%s)'% (self.__class__.__name__, rule, self.value, reset)
























class _ReadValue(AbstractSubject, AbstractCell):
    """Base class for readable cells"""

    __slots__ = '_value', 'next_listener', '_set_by', '_reset', # XXX 'manager'

    def __init__(self, value=None, discrete=False):
        self._value = value
        self._set_by = _sentinel
        AbstractSubject.__init__(self)
        self._reset = (_sentinel, value)[bool(discrete)]

    def get_value(self):
        if ctrl.active:
            # if atomic, make sure we're locked and consistent
            ctrl.used(self)
        return self._value

    value = property(get_value)

    def _finish(self):
        if self._set_by is not _sentinel:
            ctrl.setattr(self, '_set_by', _sentinel)
        if self._reset is not _sentinel and self._value != self._reset:
            ctrl.setattr(self, '_value', self._reset)
            ctrl.changed(self)
















class Value(_ReadValue):
    """A read-write value with optional discrete mode"""

    __slots__ = ()

    def set_value(self, value):
        if not ctrl.active:
            return ctrl.atomically(self.set_value, value)

        ctrl.lock(self)
        if self._set_by is _sentinel:
            ctrl.setattr(self, '_set_by', ctrl.current_listener)
            ctrl.on_commit(self._finish)

        if value==self._value:
            return  # no change, no foul...

        if self._set_by is not ctrl.current_listener:
            # already set by someone else
            raise InputConflict(self._value, value) # XXX

        ctrl.setattr(self, '_value', value)
        ctrl.changed(self)

    value = property(_ReadValue.get_value.im_func, set_value)
















class ReadOnlyCell(_ReadValue, AbstractListener):
    """A cell with a rule"""

    __slots__ = 'rule', '_needs_init', 'next_subject', '__weakref__', 'layer'

    def __init__(self, rule, value=None, discrete=False):
        super(ReadOnlyCell, self).__init__(value, discrete)
        AbstractListener.__init__(self)
        self._needs_init = True
        self.rule = rule
        self.layer = 0

    def get_value(self):
        if self._needs_init:
            if not ctrl.active:
                # initialization must be atomic
                return ctrl.atomically(self.get_value)
            ctrl.run(self)
        if ctrl.current_listener is not None:
            ctrl.used(self)
        return self._value

    value = property(get_value)

    def run(self):
        if self._needs_init:
            ctrl.setattr(self, '_needs_init', False)
        value = self.rule()
        if value!=self._value:
            if self._set_by is _sentinel:
                ctrl.setattr(self, '_set_by', self)
                ctrl.on_commit(self._finish)
            ctrl.setattr(self, '_value', value)
            ctrl.changed(self)







    def _finish(self):
        super(ReadOnlyCell, self)._finish()

        if self.next_subject is None and (
            self._reset is _sentinel or self._value==self._reset
        ):
            ctrl.setattr(self, '_set_by', _sentinel)
            ctrl.setattr(self, 'rule', None)
            ctrl.setattr(self, 'next_listener', None)
            ctrl.setattr(self, '__class__', ConstantRule)


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


class Observer(AbstractListener, AbstractCell):
    """Rule that performs non-undoable actions"""

    __slots__ = 'run', 'next_subject', '__weakref__'

    layer = Max

    def __init__(self, rule):
        self.run = rule
        super(Observer, self).__init__()
        if not ctrl.active:
            return ctrl.atomically(ctrl.schedule, self)
        else:
            ctrl.schedule(self)

Observer.rule = Observer.run    # alias the attribute for inspection



class Cell(ReadOnlyCell, Value):
    """Spreadsheet-like cell with automatic updating"""

    __slots__ = ()

    def __new__(cls, rule=None, value=_sentinel, discrete=False):
        if rule is None:
            return Value(value, discrete)
        elif value is _sentinel:
            return ReadOnlyCell(rule, None, discrete)
        return ReadOnlyCell.__new__(cls, rule, value, discrete)

    _finish = Value._finish.im_func     # we can never become Constant

    def get_value(self):
        if self._needs_init:
            if not ctrl.active:
                # initialization must be atomic
                return ctrl.atomically(self.get_value)
            if self._set_by is _sentinel:
                # No value set yet, so we have to run() first
                ctrl.run(self)
        if ctrl.current_listener is not None:
            ctrl.used(self)
        return self._value

    def set_value(self, value):
        if not ctrl.active:
            return ctrl.atomically(self.set_value, value)
        super(Cell, self).set_value(value)
        if self._needs_init:
            ctrl.schedule(self)

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
            ctrl.setattr(self, '_needs_init', False)
            self.rule()
        else:
            # It should be impossible to get here unless you run() the cell
            # manually.
            raise AssertionError("This should never happen!")


























