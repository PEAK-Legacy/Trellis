"""Software Transactional Memory and Observers"""

import weakref, sys, heapq

try:
    import threading
except ImportError:
    import dummy_threading as threading

__all__ = [
    'STMHistory', 'AbstractSubject',  'Link', 'AbstractListener', 'Controller',
]

class AbstractSubject(object):
    """Abstract base for objects that can be linked via ``Link`` objects"""

    __slots__ = ()

    manager = None

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

    def __init__(self):
        self.layer = 0
        self.next_subject = None

    def iter_subjects(self):
        """Yield the listeners of this subject"""
        link = self.next_subject
        while link is not None:
            nxt = link.next_subject   # avoid unlinks breaking iteration
            yield link.subject
            link = nxt

























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
        nxt = self.next_listener
        prev = self.prev_listener
        if nxt is not None:
            nxt.prev_listener = prev
        if prev is not None:
            prev.next_listener = nxt
        prev = self.prev_subject
        nxt = self.next_subject
        if nxt is not None:
            nxt.prev_subject = prev
        if prev is None:
            prev = self()   # get head of list
        if prev is not None and prev.next_subject is self:
            prev.next_subject = nxt

_unlink_fn = Link.unlink




class STMHistory(object):
    """Simple STM implementation using undo logging and context managers"""

    active = in_cleanup = False

    def __init__(self):
        self.undo = []      # [(func,args), ...]
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
            del self.undo[:]
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
                self.rollback_to(0)
                raise typ, val, tb
        finally:
            self.in_cleanup = False
            typ = val = tb = None

    def setattr(self, ob, attr, val):
        """Set `ob.attr` to `val`, w/undo log to restore the previous value"""
        self.on_undo(setattr, ob, attr, getattr(ob, attr))
        setattr(ob, attr, val)





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

    def cleanup(self, *args):
        try:
            return super(Controller, self).cleanup(*args)
        finally:
            #self.has_run.clear()
            del self.layers[:]
            self.queues.clear()
            self.current_listener = None
            self.last_notified = None
            #self.last_listener = None
            #self.last_save = None
















    def schedule(self, listener, source_layer=None, reschedule=False):
        """Schedule `listener` to run during an atomic operation

        If an operation is already in progress, it's immediately scheduled, and
        its scheduling is logged in the undo queue (unless it was already
        scheduled)

        If `source_layer` is specified, ensure that the listener belongs to
        a higher layer than the source, moving the listener from an existing
        queue layer if necessary.  (This layer elevation is intentionally
        NOT undo-logged, however.)
        """
        new = old = listener.layer
        get = self.queues.get

        if source_layer is not None and source_layer >= listener.layer:
            new = source_layer + 1

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
        while writes:
            subject, ignore = writes.popitem()
            for dependent in subject.iter_listeners():
                if dependent is not listener:
                    # XXX if dependent.dirty(listener):
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


    def cancel(self, listener):
        """Prevent the listener from being recalculated, if applicable"""
        q = self.queues.get(listener.layer)
        if q and listener in q:
            del q[listener]
            if not q:
                del self.queues[listener.layer]
                self.layers.remove(listener.layer)
                self.layers.sort()  # preserve heap order

    def lock(self, subject):
        assert self.active, "Subjects must be accessed atomically"
        manager = subject.manager
        if manager is not None and manager not in self.managers:
            self.manage(manager)

    def used(self, subject):
        self.lock(subject)
        if self.current_listener is not None:
            self.reads[subject] = 1

    def changed(self, subject):
        self.lock(subject)
        if self.current_listener is not None:
            self.writes[subject] = 1
        if self.readonly:
            raise RuntimeError("Can't change objects during commit phase")














