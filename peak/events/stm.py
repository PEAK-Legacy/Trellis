"""Software Transactional Memory and Observers"""

import weakref, sys, heapq

try:
    import threading
except ImportError:
    import dummy_threading as threading

__all__ = [
    'STMHistory', 'AbstractSubject',  'Link', 'AbstractListener', #'History'
]

class AbstractSubject(object):
    """Abstract base for objects that can be linked via ``Link`` objects"""

    __slots__ = ()

    def __init__(self):
        # self.manager = XXX
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

    listener = property(lambda self: self())

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
                if self.managers:
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










