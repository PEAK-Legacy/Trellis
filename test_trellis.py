from test_sets import *
from peak import context
from peak.events.activity import EventLoop, TwistedEventLoop, Time, NOT_YET
from peak.events import trellis, stm
from peak.util.decorators import rewrap, decorate as d
import unittest, heapq

try:
    import testreactor
except ImportError:
    testreactor = None  # either twisted or testreactor are missing
try:
    import wx
except ImportError:
    wx = None

class EventLoopTestCase(unittest.TestCase):
    def setUp(self):
        self.state = context.new()
        self.state.__enter__()
        super(EventLoopTestCase, self).setUp()
        self.configure_context()

    def tearDown(self):
        super(EventLoopTestCase, self).tearDown()
        self.state.__exit__(None, None, None)

    def configure_context(self):
        pass












if wx:
    class TestWxEventLoop(EventLoopTestCase):
        def configure_context(self):
            from peak.events.activity import EventLoop, WXEventLoop
            EventLoop <<= WXEventLoop
            self.app = wx.PySimpleApp(redirect=False)
            self.app.ExitOnFrameDelete = False

        def testSequentialCalls(self):
            log = []
            EventLoop.call(log.append, 1)
            EventLoop.call(log.append, 2)
            EventLoop.call(log.append, 3)
            EventLoop.call(log.append, 4)
            EventLoop.call(EventLoop.stop)
            EventLoop.run()
            self.assertEqual(log, [1,2,3,4])

            # XXX this should test timing stuff, but the only way to do that
            #     is with a wx mock, which I haven't time for as yet.





















if testreactor:

    class TestReactorEventLoop(EventLoopTestCase, testreactor.ReactorTestCase):

        def configure_context(self):
            from peak.events.activity import Time, EventLoop
            from twisted.internet import reactor
            Time <<= lambda: Time()
            Time.time = reactor.getTime
            EventLoop <<= TwistedEventLoop

        def testSequentialCalls(self):
            log = []
            EventLoop.call(log.append, 1)
            EventLoop.call(log.append, 2)
            EventLoop.call(log.append, 3)
            EventLoop.call(log.append, 4)

            class IdleTimer(trellis.Component):
                trellis.values(
                    idle_for = NOT_YET,
                    idle_timeout = 20,
                    busy = False,
                )
                trellis.rules(
                    idle_for = lambda self:
                        self.idle_for.begins_with(not self.busy)
                )
                def alarm(self):
                    if self.idle_for[self.idle_timeout] and EventLoop.running:
                        log.append(5)
                        EventLoop.stop()
                alarm = trellis.action(alarm)

            it = IdleTimer()
            EventLoop.run()
            self.assertEqual(log, [1,2,3,4,5])




class TestListener(stm.AbstractListener): pass
class TestSubject(stm.AbstractSubject): pass

class TestLinks(unittest.TestCase):

    def setUp(self):
        self.l1 = TestListener()
        self.l2 = TestListener()
        self.s1 = TestSubject()
        self.s2 = TestSubject()
        self.lk11 = stm.Link(self.s1, self.l1)
        self.lk12 = stm.Link(self.s1, self.l2)
        self.lk21 = stm.Link(self.s2, self.l1)
        self.lk22 = stm.Link(self.s2, self.l2)

    def verify_subjects(self, items):
        for link, nxt, prev in items:
            self.failUnless(link.next_subject is nxt)
            if isinstance(link,stm.Link):
                self.failUnless(link.prev_subject is prev)
            
    def verify_listeners(self, items):
        for link, nxt, prev in items:
            self.failUnless(link.next_listener is nxt)
            if isinstance(link,stm.Link):
                self.failUnless(link.prev_listener is prev)
            
    def testBreakIterSubjects(self):
        it = self.l1.iter_subjects()
        self.failUnless(it.next() is self.s2)
        self.lk11.unlink()
        self.failUnless(it.next() is self.s1)

    def testBreakIterListeners(self):
        it = self.s1.iter_listeners()
        self.failUnless(it.next() is self.l2)
        self.lk11.unlink()
        self.failUnless(it.next() is self.l1)



    def testLinkSetup(self):
        self.verify_subjects([
            (self.l1, self.lk21, None),   (self.l2, self.lk22, None),
            (self.lk21, self.lk11, None), (self.lk11, None, self.lk21),
            (self.lk22, self.lk12, None), (self.lk12, None, self.lk22),
        ])
        self.verify_listeners([
            (self.s1, self.lk12, None),      (self.s2, self.lk22, None),
            (self.lk22, self.lk21, self.s2), (self.lk21, None, self.lk22),
            (self.lk12, self.lk11, self.s1), (self.lk11, None, self.lk12),
        ])           

    def testUnlinkListenerHeadSubjectTail(self):
        self.lk21.unlink()
        self.verify_subjects([
            (self.l1, self.lk11, None), (self.lk11, None, None)
        ])
        self.verify_listeners([
            (self.s2, self.lk22, None), (self.lk22, None, self.s2)
        ])

    def testUnlinkListenerTailSubjectHead(self):
        self.lk12.unlink()
        self.verify_subjects([
            (self.l2, self.lk22, None), (self.lk22, None, None),
        ])
        self.verify_listeners([
            (self.s1, self.lk11, None), (self.lk11, None, self.s1),
        ])           



def a(f):
    def g(self):
        return self.ctrl.atomically(f, self)
    return rewrap(f, g)





class TestController(unittest.TestCase):

    def setUp(self):
        self.ctrl = stm.Controller()
        self.t0 = TestListener()
        self.t1 = TestListener(); self.t1.layer = 1
        self.t2 = TestListener(); self.t2.layer = 2
        self.s1 = TestSubject(); self.s2 = TestSubject()

    def tearDown(self):
        # Verify correct cleanup in all scenarios
        self.assertEqual(self.ctrl.undo, [])
        self.assertEqual(self.ctrl.managers, {})
        self.assertEqual(self.ctrl.queues, {})
        self.assertEqual(self.ctrl.layers, [])
        self.assertEqual(self.ctrl.reads, {})
        self.assertEqual(self.ctrl.writes, {})
        self.assertEqual(self.ctrl.has_run, {})
        self.assertEqual(self.ctrl.last_listener, None)
        self.assertEqual(self.ctrl.last_notified, None)
        self.assertEqual(self.ctrl.last_save, None)
        self.assertEqual(self.ctrl.current_listener, None)
        self.assertEqual(self.ctrl.readonly, False)
        self.assertEqual(self.ctrl.in_cleanup, False)
        self.assertEqual(self.ctrl.active, False)

    def testScheduleSimple(self):
        t1 = TestListener()
        t2 = TestListener()
        self.assertEqual(self.ctrl.layers, [])
        self.assertEqual(self.ctrl.queues, {})
        self.ctrl.schedule(t1)
        self.ctrl.schedule(t2)
        self.assertEqual(self.ctrl.layers, [0])
        self.assertEqual(self.ctrl.queues, {0: {t1:1, t2:1}})
        self.ctrl.cancel(t1)
        self.assertEqual(self.ctrl.layers, [0])
        self.assertEqual(self.ctrl.queues, {0: {t2:1}})
        self.ctrl.cancel(t2)
        # tearDown will assert that everything has been cleared

    def testHeapingCancel(self):
        # verify that cancelling the last listener of a layer keeps
        # the 'layers' list in heap order
        self.ctrl.schedule(self.t0)
        self.ctrl.schedule(self.t2)
        self.ctrl.schedule(self.t1)
        layers = self.ctrl.layers
        self.assertEqual(layers, [0, 2, 1])
        self.ctrl.cancel(self.t0)
        self.assertEqual(heapq.heappop(layers), 1)
        self.assertEqual(heapq.heappop(layers), 2)
        self.assertEqual(self.ctrl.queues, {1: {self.t1:1}, 2: {self.t2:1}})
        self.ctrl.queues.clear()

    def testDoubleAndMissingCancelOrSchedule(self):
        self.ctrl.schedule(self.t2)
        self.ctrl.cancel(self.t0)
        self.ctrl.cancel(self.t2)
        self.ctrl.cancel(self.t2)
        self.ctrl.schedule(self.t1)
        self.assertEqual(self.ctrl.queues, {1: {self.t1:1}})
        self.ctrl.schedule(self.t1)
        self.assertEqual(self.ctrl.queues, {1: {self.t1:1}})
        self.ctrl.cancel(self.t1)

    def testScheduleLayerBump(self):
        # listener layer must be at least source layer + 1
        self.ctrl.schedule(self.t1)
        self.ctrl.schedule(self.t1, 0)
        self.assertEqual(self.ctrl.queues, {1: {self.t1:1}})
        self.ctrl.schedule(self.t1, 1)
        self.assertEqual(self.ctrl.queues, {2: {self.t1:1}})
        self.assertEqual(self.t1.layer, 2)
        self.ctrl.cancel(self.t1)

    d(a)
    def testScheduleRollback(self):
        # when running atomically, scheduling is an undo-logged operation
        self.ctrl.schedule(self.t1)
        self.ctrl.rollback_to(0)

    def testCleanup(self):
        self.ctrl.schedule(self.t0)
        class MyError(Exception): pass
        def raiser():
            # XXX need to actually run one rule, plus start another w/error
            raise MyError
        try:
            self.ctrl.atomically(raiser)
        except MyError:
            pass

    def testSubjectsMustBeAtomic(self):
        self.assertRaises(AssertionError, self.ctrl.lock, self.s1)
        self.assertRaises(AssertionError, self.ctrl.used, self.s1)
        self.assertRaises(AssertionError, self.ctrl.changed, self.s1)

    d(a)
    def testLockAcquiresManager(self):
        class Dummy:
            def __enter__(*args): pass
            def __exit__(*args): pass
        mgr = self.s1.manager = Dummy()
        self.ctrl.lock(self.s1)
        self.assertEqual(self.ctrl.managers, {mgr:0})
        self.ctrl.lock(self.s2)
        self.assertEqual(self.ctrl.managers, {mgr:0})

    d(a)
    def testReadWrite(self):
        self.ctrl.used(self.s1)
        self.ctrl.changed(self.s2)
        self.assertEqual(self.ctrl.reads, {})
        self.assertEqual(self.ctrl.writes, {})
        self.ctrl.current_listener = self.t0
        self.ctrl.used(self.s1)
        self.ctrl.changed(self.s2)
        self.assertEqual(self.ctrl.reads, {self.s1:1})
        self.assertEqual(self.ctrl.writes, {self.s2:1})
        self.ctrl.reads.clear()     # these would normally be handled by
        self.ctrl.writes.clear()    # the run() method's try/finally

    d(a)
    def testNoReadDuringCommit(self):
        self.ctrl.readonly = True
        self.assertRaises(RuntimeError, self.ctrl.changed, self.s1)
        self.ctrl.readonly = False  # normally reset by ctrl.run()

    d(a)
    def testRecalcOnWrite(self):
        stm.Link(self.s1, self.t0)
        stm.Link(self.s2, self.t1)
        stm.Link(self.s2, self.t0)
        self.ctrl.current_listener = self.t1
        self.ctrl.changed(self.s1)
        self.ctrl.changed(self.s2)
        self.assertEqual(self.ctrl.writes, {self.s1:1, self.s2:1})
        sp = self.ctrl.savepoint()
        self.ctrl._process_writes(self.t1)
        # Only t0 is notified, not t1, since t1 is the listener
        self.assertEqual(self.ctrl.last_notified, {self.t0: 1})
        self.assertEqual(self.ctrl.queues, {2: {self.t0:1}})
        self.ctrl.reads.clear()     # normally reset by _process_reads
        self.ctrl.rollback_to(sp)
        self.assertEqual(self.ctrl.last_notified, None)

    d(a)
    def testDependencyUpdatingAndUndo(self):
        stm.Link(self.s1, self.t0)
        s3 = TestSubject()
        stm.Link(s3, self.t0)
        self.assertEqual(list(self.t0.iter_subjects()), [s3, self.s1])
        self.ctrl.current_listener = self.t0
        self.ctrl.used(self.s1)
        self.ctrl.used(self.s2)
        sp = self.ctrl.savepoint()
        self.ctrl._process_reads(self.t0)
        self.assertEqual(list(self.t0.iter_subjects()), [self.s2, self.s1])
        self.ctrl.rollback_to(sp)
        self.assertEqual(list(self.t0.iter_subjects()), [s3, self.s1])
        


def additional_tests():
    import doctest, sys
    files = [
        'README.txt', 'STM-Observer.txt', 'Collections.txt', 'Internals.txt',
        'Specification.txt',
    ][(sys.version<'2.4')*3:]   # README.txt uses decorator syntax
    return doctest.DocFileSuite(
        optionflags=doctest.ELLIPSIS|doctest.NORMALIZE_WHITESPACE, *files
    )
































