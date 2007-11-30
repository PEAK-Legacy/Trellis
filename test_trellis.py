from test_sets import *
from peak import context
from peak.events.activity import EventLoop, TwistedEventLoop, Time, NOT_YET
from peak.events import trellis, stm
from peak.util.decorators import rewrap, decorate as d
from peak.util.extremes import Max
import unittest, heapq, mocker, types

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

class TestListener(stm.AbstractListener):
    def __repr__(self): return self.name
class TestSubject(stm.AbstractSubject):
    def __repr__(self): return self.name
class DummyError(Exception): pass
class UndirtyListener(TestListener):
    def dirty(self):
        return False


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
                alarm = trellis.rule(alarm)

            it = IdleTimer()
            EventLoop.run()
            self.assertEqual(log, [1,2,3,4,5])




class TestLinks(unittest.TestCase):

    def setUp(self):
        self.l1 = TestListener(); self.l1.name = 'l1'
        self.l2 = TestListener(); self.l1.name = 'l2'
        self.s1 = TestSubject(); self.s1.name = 's1'
        self.s2 = TestSubject(); self.s2.name = 's2'
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
        self.lk21.unlink()
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
        self.t0 = TestListener(); self.t0.name='t0';
        self.t1 = TestListener(); self.t1.name='t1'; self.t1.layer = 1
        self.t2 = TestListener(); self.t2.name='t2'; self.t2.layer = 2
        self.t3 = UndirtyListener(); self.t3.name='t3'
        self.s1 = TestSubject(); self.s2 = TestSubject()
        self.s1.name = 's1'; self.s2.name = 's2'

    def tearDown(self):
        # Verify correct cleanup in all scenarios
        for k,v in dict(
            undo=[], managers={}, queues={}, layers=[], reads={}, writes={},
            has_run={}, last_listener=None, last_notified=None, last_save=None,
            current_listener=None, readonly=False, in_cleanup=False,
            active=False, at_commit=[], to_retry={}
        ).items():
            val = getattr(self.ctrl, k)
            self.assertEqual(val, v, '%s: %r' % (k,val))

    def testScheduleSimple(self):
        t1 = TestListener(); t1.name='t1'
        t2 = TestListener(); t2.name='t2'
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

    def testThreadLocalController(self):
        self.failUnless(isinstance(trellis.ctrl, stm.Controller))
        self.failUnless(isinstance(trellis.ctrl, stm.threading.local))

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
        def raiser():
            # XXX need to actually run one rule, plus start another w/error
            raise DummyError
        try:
            self.ctrl.atomically(self.runAs, self.t0, raiser)
        except DummyError:
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
        self.assertEqual(self.ctrl.writes, {self.s2:self.t0})
        self.ctrl.reads.clear()     # these would normally be handled by
        self.ctrl.writes.clear()    # the run() method's try/finally


    d(a)
    def testNoReadDuringCommit(self):
        self.ctrl.readonly = True
        self.assertRaises(RuntimeError, self.ctrl.changed, self.s1)
        self.ctrl.readonly = False  # normally reset by ctrl.run_rule()

    d(a)
    def testRecalcOnWrite(self):
        stm.Link(self.s1, self.t0)
        stm.Link(self.s2, self.t1)
        stm.Link(self.s2, self.t0)
        self.ctrl.current_listener = self.t1
        self.ctrl.changed(self.s1)
        self.ctrl.changed(self.s2)
        self.assertEqual(self.ctrl.writes, {self.s1:self.t1, self.s2:self.t1})
        sp = self.ctrl.savepoint(); self.ctrl.has_run[self.t1] = self.t1
        self.ctrl._process_writes(self.t1)
        # Only t0 is notified, not t1, since t1 is the listener
        self.assertEqual(self.ctrl.last_notified, {self.t0: 1})
        self.assertEqual(self.ctrl.queues, {2: {self.t0:1}})
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




    def runAs(self, listener, rule, initialized=True):
        listener.run = rule
        self.ctrl.run_rule(listener, initialized)

    d(a)
    def testIsRunningAndHasRan(self):
        def rule():
            self.assertEqual(self.ctrl.current_listener, self.t1)
            self.assertEqual(self.ctrl.last_listener, self.t1)
            self.assertEqual(self.ctrl.has_run, {self.t1: self.t1})
        sp = self.ctrl.savepoint()
        self.runAs(self.t1, rule)
        self.assertEqual(self.ctrl.last_save, sp)
        self.assertEqual(self.ctrl.current_listener, None)
        self.assertEqual(self.ctrl.last_listener, self.t1)
        self.assertEqual(self.ctrl.has_run, {self.t1: self.t1})
        self.ctrl.rollback_to(sp)   # should clear last_listener, last_save

    d(a)
    def testIsRunningButHasNotRan(self):
        def rule():
            self.assertEqual(self.ctrl.current_listener, self.t1)
            self.assertEqual(self.ctrl.last_listener, None)
            self.assertEqual(self.ctrl.has_run, {})
        sp = self.ctrl.savepoint()
        self.runAs(self.t1, rule, False)    # uninit'd rule
        self.assertEqual(self.ctrl.last_save, None)
        self.assertEqual(self.ctrl.current_listener, None)
        self.assertEqual(self.ctrl.last_listener, None)
        self.assertEqual(self.ctrl.has_run, {})
        self.ctrl.rollback_to(sp)   # should clear last_listener, last_save

    d(a)
    def testClearLastListener(self):
        self.runAs(self.t1, lambda:1)
        self.assertEqual(self.ctrl.last_listener, self.t1)
        # last_listener should be cleared by cleanup()

    d(a)
    def testScheduleUndo(self):
        sp = self.ctrl.savepoint()
        self.ctrl.schedule(self.t2)
        self.assertEqual(self.ctrl.queues, {2: {self.t2:1}})
        self.ctrl.rollback_to(sp)
        self.assertEqual(self.ctrl.queues, {})










    d(a)
    def testWriteProcessingInRun(self):
        stm.Link(self.s1, self.t0)
        stm.Link(self.s2, self.t1)
        stm.Link(self.s2, self.t3)
        stm.Link(self.s2, self.t0)
        def rule():
            self.ctrl.changed(self.s1)
            self.ctrl.changed(self.s2)
            self.assertEqual(self.ctrl.writes, {self.s1:self.t1, self.s2:self.t1})
        self.runAs(self.t1, rule)
        # Only t0 is notified, not t1, since t1 is the listener & t3 is !dirty
        self.assertEqual(self.ctrl.writes, {})
        self.assertEqual(self.ctrl.last_notified, {self.t0: 1})
        self.assertEqual(self.ctrl.queues, {2: {self.t0:1}})
        self.ctrl.cancel(self.t0)

    d(a)
    def testReadProcessingInRun(self):
        stm.Link(self.s1, self.t0)
        s3 = TestSubject()
        stm.Link(s3, self.t0)
        self.assertEqual(list(self.t0.iter_subjects()), [s3, self.s1])
        def rule():
            self.ctrl.used(self.s1)
            self.ctrl.used(self.s2)
            self.assertEqual(self.ctrl.reads, {self.s1:1, self.s2:1})
        self.runAs(self.t0, rule)
        self.assertEqual(self.ctrl.reads, {})
        self.assertEqual(list(self.t0.iter_subjects()), [self.s2, self.s1])

    d(a)
    def testReadOnlyDuringMax(self):
        def rule():
            self.assertEqual(self.ctrl.readonly, True)
        self.t0.layer = Max
        self.assertEqual(self.ctrl.readonly, False)
        self.runAs(self.t0, rule)
        self.assertEqual(self.ctrl.readonly, False)


    d(a)
    def testRunClearsReadWriteOnError(self):
        def rule():
            self.ctrl.used(self.s1)
            self.ctrl.changed(self.s2)
            self.assertEqual(self.ctrl.reads, {self.s1:1})
            self.assertEqual(self.ctrl.writes, {self.s2:1})
            try:
                self.runAs(self.t0, rule)
            except DummyError:
                pass
            else:
                raise AssertionError("Error should've propagated")
        self.assertEqual(self.ctrl.reads, {})
        self.assertEqual(self.ctrl.writes, {})

    d(a)
    def testSimpleCycle(self):
        stm.Link(self.s1, self.t1)
        stm.Link(self.s2, self.t2)
        def rule0():
            self.ctrl.used(self.s1)
            self.ctrl.changed(self.s1)
        def rule1():
            self.ctrl.used(self.s1)
            self.ctrl.changed(self.s2)
        def rule2():
            self.ctrl.used(self.s2)
            self.ctrl.changed(self.s1)
        self.runAs(self.t0, rule0)
        self.runAs(self.t1, rule1)
        self.runAs(self.t2, rule2)
        try:
            self.ctrl._retry()
        except stm.CircularityError, e:
            self.assertEqual(e.args[0],
                {self.t0: set([self.t1]), self.t1: set([self.t2]),
                 self.t2: set([self.t0, self.t1])})
        else:
            raise AssertionError("Should've caught a cycle")

    d(a)
    def testSimpleRetry(self):
        def rule():
            pass
        sp = self.ctrl.savepoint()
        self.runAs(self.t0, rule)
        self.runAs(self.t1, rule)
        self.runAs(self.t2, rule)
        self.ctrl.to_retry[self.t1]=1
        self.ctrl._retry(); self.ctrl.to_retry.clear()
        self.assertEqual(self.ctrl.last_listener, self.t0)
        self.assertEqual(self.ctrl.last_save, sp)
        self.ctrl.to_retry[self.t0]=1
        self.ctrl._retry(); self.ctrl.to_retry.clear()
        self.assertEqual(self.ctrl.last_save, None)

    d(a)
    def testNestedNoRetry(self):
        def rule0():
            self.runAs(self.t1, rule1, False)
        def rule1():
            pass
        self.runAs(self.t2, rule1)
        self.runAs(self.t0, rule0)
        self.ctrl.schedule(self.t1)
        self.assertEqual(self.ctrl.to_retry, {})
        self.assertEqual(self.ctrl.last_listener, self.t0)
        self.assertEqual(self.ctrl.to_retry, {})
        self.assertEqual(self.ctrl.queues, {1: {self.t1:1}})












    def testRunScheduled(self):
        log = []
        self.t1.run = lambda: log.append(True)
        def go():
            self.ctrl.schedule(self.t1)
        self.ctrl.atomically(go)
        self.assertEqual(log, [True])


    def testRollbackReschedules(self):
        sp = []
        def rule0():
            self.ctrl.rollback_to(sp[0])
            self.assertEqual(self.ctrl.queues, {0: {self.t0:1}})
            self.ctrl.cancel(self.t0)
        self.t0.run = rule0
        def go():
            self.ctrl.schedule(self.t0)
            sp.append(self.ctrl.savepoint())
        self.ctrl.atomically(go)

    def testManagerCanCreateLoop(self):
        class Mgr:
            def __enter__(self): pass
            def __exit__(*args):
                self.ctrl.schedule(self.t1)
        log = []
        def rule1():
            log.append(True)
        self.t1.run = rule1
        self.t0.run = lambda:self.ctrl.manage(Mgr())
        self.ctrl.atomically(self.ctrl.schedule, self.t0)
        self.assertEqual(log, [True])








    d(a)
    def testNotifyOnChange(self):
        stm.Link(self.s2, self.t2)
        stm.Link(self.s2, self.t3)
        self.ctrl.changed(self.s2)
        self.ctrl.current_listener = self.t0
        self.ctrl.changed(self.s2)
        self.assertEqual(self.ctrl.queues, {2: {self.t2:1}})
        self.ctrl.cancel(self.t2)
        self.ctrl.writes.clear()

    def testCommitCanLoop(self):
        log=[]
        def go():
            log.append(True)
        self.t0.run = go
        self.ctrl.atomically(self.ctrl.on_commit, self.ctrl.schedule, self.t0)
        self.assertEqual(log,[True])

    d(a)
    def testNoUndoDuringUndo(self):
        def undo():
            self.ctrl.on_undo(redo)
        def redo():
            raise AssertionError("Should not be run")
        self.ctrl.on_undo(undo)
        self.ctrl.rollback_to(0)














    d(a)
    def testNestedRule(self):
        def rule1():
            self.assertEqual(self.ctrl.last_listener, self.t1)
            self.assertEqual(self.ctrl.current_listener, self.t1)
            self.ctrl.used(self.s1)
            self.ctrl.changed(self.s2)
            self.assertEqual(self.ctrl.reads, {self.s1:1})
            self.assertEqual(self.ctrl.writes, {self.s2:self.t1})
            self.runAs(self.t2, rule2, False)
            self.assertEqual(self.ctrl.last_listener, self.t1)
            self.assertEqual(self.ctrl.current_listener, self.t1)
            self.assertEqual(self.ctrl.reads, {self.s1:1})
            self.assertEqual(self.ctrl.writes, {self.s2:self.t1, s3:self.t2})

        def rule2():
            self.assertEqual(self.ctrl.last_listener, self.t1)
            self.assertEqual(self.ctrl.current_listener, self.t2)
            self.assertEqual(self.ctrl.reads, {})
            self.assertEqual(self.ctrl.writes, {self.s2:self.t1})
            self.ctrl.used(self.s2)
            self.ctrl.changed(s3)

        def rule0():
            pass

        s3 = TestSubject(); s3.name = 's3'
        self.runAs(self.t0, rule0)
        self.runAs(self.t1, rule1)
        self.assertEqual(self.ctrl.has_run,
            {self.t1:self.t1, self.t0: self.t0}  # t2 was new, so doesn't show
        )
        self.assertEqual(list(self.t1.iter_subjects()), [self.s1])
        self.assertEqual(list(self.t2.iter_subjects()), [self.s2])
        self.ctrl.rollback_to(self.ctrl.last_save)  # should undo both t1/t2
        self.assertEqual(self.ctrl.last_listener, self.t0)





class TestCells(mocker.MockerTestCase):

    ctrl = stm.ctrl
    def tearDown(self):
        # make sure the old controller is back
        trellis.install_controller(self.ctrl)

    def testValueBasics(self):
        self.failUnless(issubclass(trellis.Value, trellis.AbstractCell))
        self.failUnless(issubclass(trellis.Value, stm.AbstractSubject))
        v = trellis.Value()
        self.assertEqual(v.value, None)
        self.assertEqual(v._set_by, trellis._sentinel)
        self.assertEqual(v._reset, trellis._sentinel)
        v.value = 21
        self.assertEqual(v._set_by, trellis._sentinel)

    d(a)
    def testValueUndo(self):
        v = trellis.Value(42)
        self.assertEqual(v.value, 42)
        sp = self.ctrl.savepoint()
        v.value = 43
        self.assertEqual(v.value, 43)
        self.ctrl.rollback_to(sp)
        self.assertEqual(v.value, 42)

    d(a)
    def testValueUsed(self):
        v = trellis.Value(42)
        ctrl = self.mocker.replace(self.ctrl) #'peak.events.stm.ctrl')
        ctrl.used(v)
        self.mocker.replay()
        trellis.install_controller(ctrl)
        self.assertEqual(v.value, 42)

    def testDiscrete(self):
        v = trellis.Value(None, True)
        v.value = 42
        self.assertEqual(v.value, None)

    def testValueChanged(self):
        v = trellis.Value(42)
        old_ctrl, ctrl = self.ctrl, self.mocker.replace(self.ctrl)
        ctrl.lock(v)
        ctrl.changed(v)
        self.mocker.replay()
        trellis.install_controller(ctrl)
        v.value = 43
        self.assertEqual(v.value, 43)

    def testValueUnchanged(self):
        v = trellis.Value(42)
        ctrl = self.mocker.replace(self.ctrl)
        ctrl.lock(v)
        mocker.expect(ctrl.changed(v)).count(0)
        self.mocker.replay()
        trellis.install_controller(ctrl)
        v.value = 42
        self.assertEqual(v.value, 42)

    d(a)
    def testValueSetLock(self):
        v = trellis.Value(42)
        v.value = 43
        self.assertEqual(v.value, 43)
        self.assertEqual(v._set_by, None)
        def go():
            v.value = 99
        t = TestListener(); t.name = 't'
        t.run = go
        self.assertRaises(trellis.InputConflict, self.ctrl.run_rule, t)
        self.assertEqual(v.value, 43)
        def go():
            v.value = 43
        t = TestListener(); t.name = 't'
        t.run = go
        self.ctrl.run_rule(t)
        self.assertEqual(v.value, 43)



    def testReadOnlyCellBasics(self):
        log = []
        c = trellis.Cell(lambda:log.append(1))
        self.failUnless(type(c) is trellis.ReadOnlyCell)
        c.value
        self.assertEqual(log,[1])
        c.value
        self.assertEqual(log,[1])

    def testDiscreteValue(self):
        log = []
        v = trellis.Value(False, True)
        c = trellis.Cell(lambda: log.append(v.value))
        self.assertEqual(log,[])
        c.value
        self.assertEqual(log,[False])
        del log[:]
        v.value = True
        self.assertEqual(log, [True, False])
        self.assertEqual(v.value, False)
        del log[:]
        v.value = False
        self.assertEqual(log, [])

    def testCellConstructor(self):
        self.failUnless(type(trellis.Cell(value=42)) is trellis.Value)
        self.failUnless(type(trellis.Cell(lambda:42)) is trellis.ReadOnlyCell)
        self.failUnless(type(trellis.Cell(lambda:42, value=42)) is trellis.Cell)

    def testRuleChain(self):
        v = trellis.Value(0)
        log = []
        c1 = trellis.Cell(lambda:int(v.value/2))
        c2 = trellis.Cell(lambda:log.append(c1.value))
        c2.value
        self.assertEqual(log, [0])
        v.value = 1
        self.assertEqual(log, [0])
        v.value = 2
        self.assertEqual(log, [0, 1])

    def testConstant(self):
        for v in (42, [57], "blah"):
            c = trellis.Constant(v)
            self.assertEqual(c.value, v)
            self.assertEqual(c.get_value(), v)
            self.failIf(hasattr(c,'set_value'))
            self.assertRaises(AttributeError, setattr, c, 'value', v)
            self.assertEqual(repr(c), "Constant(%r)" % (v,))

    def testRuleToConstant(self):
        log = []
        def go():
            log.append(1)
            return 42
        c = trellis.Cell(go)
        self.assertEqual(c.value, 42)
        self.assertEqual(log, [1])
        self.failUnless(isinstance(c, trellis.ConstantRule))
        self.assertEqual(repr(c), "Constant(42)")
        self.assertEqual(c.value, 42)
        self.assertEqual(c.get_value(), 42)
        self.assertEqual(c.rule, None)
        self.assertEqual(log, [1])
        self.failIf(c.dirty())
        c.__class__ = trellis.ReadOnlyCell  # transition must be reversible to undo
        self.failIf(isinstance(c, trellis.ConstantRule))

    def testModifierIsAtomic(self):
        log = []
        d(trellis.modifier)
        def do_it():
            self.failUnless(self.ctrl.active)
            self.assertEqual(self.ctrl.current_listener, None)
            log.append(True)
            return log
        rv = do_it()
        self.failUnless(rv is log)
        self.assertEqual(log, [True])



    d(a)
    def testModifierAlreadyAtomic(self):
        log = []
        d(trellis.modifier)
        def do_it():
            self.failUnless(self.ctrl.active)
            self.assertEqual(self.ctrl.current_listener, None)
            log.append(True)
            return log
        rv = do_it()
        self.failUnless(rv is log)
        self.assertEqual(log, [True])

    d(a)
    def testModifierFromCell(self):
        v1, v2 = trellis.Value(42), trellis.Value(99)
        d(trellis.modifier)
        def do_it():
            v1.value = v1.value * 2
            self.assertEqual(self.ctrl.reads, {v1:1})
        def rule():
            v2.value
            do_it()
            self.assertEqual(self.ctrl.reads, {v2:1})
        trellis.Cell(rule).value
        self.assertEqual(v1.value, 84)

    def testDiscreteToConstant(self):
        log = []
        c1 = trellis.ReadOnlyCell(lambda:True, False, True)
        c2 = trellis.Cell(lambda:log.append(c1.value))
        c2.value
        self.assertEqual(log, [True, False])
        self.failUnless(isinstance(c1, trellis.ConstantRule))







    def testReadWriteCells(self):
        C = trellis.Cell(lambda: (F.value-32) * 5.0/9, -40)
        F = trellis.Cell(lambda: (C.value * 9.0)/5 + 32, -40)
        self.assertEqual(C.value, -40)
        self.assertEqual(F.value, -40)
        C.value = 0
        self.assertEqual(C.value, 0)
        self.assertEqual(F.value, 32)

    def testSelfDependencyDoesNotIncreaseLayer(self):
        c1 = trellis.Value(23)
        c2 = trellis.Cell(lambda: c1.value + c2.value, 0)
        self.assertEqual(c2.value, 23)
        self.assertEqual(c2.layer, 1)
        c1.value = 19
        self.assertEqual(c2.value, 42)
        self.assertEqual(c2.layer, 1)

    def testSettingOccursForEqualObjects(self):
        d1 = {}; d2 = {}
        c1 = trellis.Value()
        c1.value = d1
        self.failUnless(c1.value is d1)
        c1.value = d2
        self.failUnless(c1.value is d2)

    def testRepeat(self):
        def counter():
            if counter.value == 10:
                return counter.value
            trellis.repeat()
            return counter.value + 1
        counter = trellis.ReadOnlyCell(counter, 1)
        self.assertEqual(counter.value, 10)







class TestDefaultEventLoop(unittest.TestCase):

    def setUp(self):
        self.loop = EventLoop()
        self.ctrl = trellis.ctrl
    
    def testCallAndPoll(self):
        log = []
        self.loop.call(log.append, 1)
        self.loop.call(log.append, 2)
        self.assertEqual(log, [])
        self.loop.poll()
        self.assertEqual(log, [1])
        self.loop.poll()
        self.assertEqual(log, [1, 2])
        self.loop.poll()
        self.assertEqual(log, [1, 2])

    d(a)
    def testLoopIsNonAtomic(self):
        self.assertRaises(AssertionError, self.loop.poll)
        self.assertRaises(AssertionError, self.loop.flush)
        self.assertRaises(AssertionError, self.loop.run)

    def testCallAndFlush(self):
        log = []
        self.loop.call(log.append, 1)
        self.loop.call(log.append, 2)
        self.loop.call(self.loop.call, log.append, 3)
        self.assertEqual(log, [])
        self.loop.flush()
        self.assertEqual(log, [1, 2])
        self.loop.poll()
        self.assertEqual(log, [1, 2, 3])
        self.loop.poll()
        self.assertEqual(log, [1, 2, 3])





    def testUndoOfCall(self):
        log = []
        def do():
            self.loop.call(log.append, 1)
            sp = self.ctrl.savepoint()
            self.loop.call(log.append, 2)
            self.ctrl.rollback_to(sp)
            self.loop.call(log.append, 3)
        self.ctrl.atomically(do)
        self.assertEqual(log, [])
        self.loop.flush()
        self.assertEqual(log, [1, 3])
        




























class TestTasks(unittest.TestCase):

    ctrl = trellis.ctrl

    def testRunAtomicallyInLoop(self):
        log = []
        def f():
            self.failUnless(self.ctrl.active)
            log.append(1)
            yield trellis.Pause
            self.failUnless(self.ctrl.active)
            log.append(2)
        t = trellis.TaskCell(f)
        self.assertEqual(log, [])
        t._loop.flush()
        self.assertEqual(log, [1])
        t._loop.flush()
        self.assertEqual(log, [1, 2])

    def testDependencyAndCallback(self):
        log = []
        v = trellis.Value(42)
        v1 = trellis.Value(1)
        c1 = trellis.Cell(lambda: v1.value*2)
        def f():
            while v.value:
                log.append(v.value)
                v1.value = v.value
                yield trellis.Pause
        t = trellis.TaskCell(f)
        check = []
        for j in 42, 57, 99, 106, 23, None:
            self.assertEqual(log, check)
            v.value = j
            if j: check.append(j)
            for i in range(5):
                t._loop.flush()
                if j: self.assertEqual(c1.value, j*2)
                self.assertEqual(log, check)
        

    def testPauseAndCall(self):
        log = []
        class TaskExample(trellis.Component):
            trellis.values(
                start = False,
                stop = False
            )
        
            def wait_for_start(self):
                log.append("waiting to start")
                while not self.start:
                    yield trellis.Pause
        
            def wait_for_stop(self):
                while not self.stop:
                    log.append("waiting to stop")
                    yield trellis.Pause
        
            d(trellis.task)
            def demo(self):
                yield self.wait_for_start()
                log.append("starting")
                yield self.wait_for_stop()
                log.append("stopped")
        
        self.assertEqual(log, [])
        t = TaskExample()
        EventLoop.flush()
        self.assertEqual(log, ['waiting to start'])
        log.pop()
        t.start = True
        EventLoop.flush()
        self.assertEqual(log, ['starting', 'waiting to stop'])
        log.pop()
        log.pop()
        t.stop = True
        EventLoop.flush()
        self.assertEqual(log, ['stopped'])



    def testValueReturns(self):
        log = []
        def f1():
            yield 42
        def f2():
            yield f1(); yield trellis.resume()
        def f3():
            yield f2(); v = trellis.resume()
            log.append(v)

        t = trellis.TaskCell(f3)
        EventLoop.flush()
        self.assertEqual(log, [42])

        log = []
        def f1():
            yield trellis.Return(42)

        t = trellis.TaskCell(f3)
        EventLoop.flush()
        self.assertEqual(log, [42])


    def testErrorPropagation(self):
        log = []
        def f1():
            raise DummyError
        def f2():
            try:
                yield f1(); trellis.resume()
            except DummyError:
                log.append(True)
            else:
                pass
            
        t = trellis.TaskCell(f2)
        self.assertEqual(log, [])
        EventLoop.flush()
        self.assertEqual(log, [True])

        
    def testSendAndThrow(self):
        log = []
        class SendThrowIter(object):
            count = 0
            def next(self):
                if self.count==0:
                    self.count = 1
                    def f(): yield 99
                    return f()
                raise StopIteration

            def send(self, value):
                log.append(value)
                def f(): raise DummyError; yield None
                return f()                    

            def throw(self, typ, val, tb):
                log.append(typ)
                log.append(type(val))
                log.append(type(tb))
                raise StopIteration                

        def fs(): yield SendThrowIter()
        t = trellis.TaskCell(fs)
        self.assertEqual(log, [])
        EventLoop.flush()
        self.assertEqual(log, [99, DummyError,DummyError, types.TracebackType])
        













def additional_tests():
    import doctest, sys
    files = [
        'README.txt', 'STM-Observer.txt', 'Collections.txt', 'Internals.txt',
        'Specification.txt',
    ][(sys.version<'2.4')*3:]   # README.txt uses decorator syntax
    return doctest.DocFileSuite(
        optionflags=doctest.ELLIPSIS|doctest.NORMALIZE_WHITESPACE, *files
    )
































