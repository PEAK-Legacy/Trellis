"""Software Transactional Memory and Observers"""

import weakref, sys, heapq

try:
    import threading
except ImportError:
    import dummy_threading as threading

__all__ = [
    'STMHistory', #'Link', 'AbstractListener', 'AbstractSubject',  'History'
]





























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










