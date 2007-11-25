from test_sets import *
from peak import context
from peak.events.activity import EventLoop, TwistedEventLoop, Time, NOT_YET
from peak.events import trellis, stm
from peak.util.decorators import rewrap, decorate as d
from peak.util.extremes import Max
import unittest, heapq, mocker

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
                alarm = trellis.action(alarm)

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
        self.failUnless(isinstance(stm.ctrl, stm.Controller))
        self.failUnless(isinstance(stm.ctrl, stm.threading.local))

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




    def runAs(self, listener, rule):
        listener.run = rule
        self.ctrl.run(listener)

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
    def testClearLastListener(self):
        self.runAs(self.t1, lambda:1)
        self.assertEqual(self.ctrl.last_listener, self.t1)
        # last_listener should be cleared by cleanup()

    d(a)
    def testScheduleUndoRedo(self):
        sp = self.ctrl.savepoint()
        self.ctrl.schedule(self.t2)
        self.assertEqual(self.ctrl.queues, {2: {self.t2:1}})
        self.ctrl.rollback_to(sp)
        self.assertEqual(self.ctrl.queues, {})
        self.ctrl.schedule(self.t2, reschedule=True)
        self.assertEqual(self.ctrl.queues, {2: {self.t2:1}})
        self.ctrl.rollback_to(sp)
        self.assertEqual(self.ctrl.queues, {2: {self.t2:1}})
        self.ctrl.cancel(self.t2)





    d(a)
    def testWriteProcessingInRun(self):
        stm.Link(self.s1, self.t0)
        stm.Link(self.s2, self.t1)
        stm.Link(self.s2, self.t3)
        stm.Link(self.s2, self.t0)
        def rule():
            self.ctrl.changed(self.s1)
            self.ctrl.changed(self.s2)
            self.assertEqual(self.ctrl.writes, {self.s1:1, self.s2:1})
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
    def testNestedRetry(self):
        def rule0():
            self.runAs(self.t1, rule1)
        def rule1():
            pass
        def rule2():
            pass #raise AssertionError("I should not be run")
        self.runAs(self.t2, rule1)
        self.runAs(self.t0, rule0)
        self.ctrl.schedule(self.t1)
        self.assertEqual(self.ctrl.to_retry, {self.t0:1})
        self.ctrl._retry()
        self.assertEqual(self.ctrl.last_listener, self.t2)
        self.assertEqual(self.ctrl.queues, {})

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
        #import pdb; pdb.set_trace()
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





    d(a)
    def testNestedRule(self):
        def rule1():
            self.assertEqual(self.ctrl.last_listener, self.t1)
            self.assertEqual(self.ctrl.current_listener, self.t1)
            self.ctrl.used(self.s1)
            self.ctrl.changed(self.s2)
            self.assertEqual(self.ctrl.reads, {self.s1:1})
            self.assertEqual(self.ctrl.writes, {self.s2:1})
            self.runAs(self.t2, rule2)
            self.assertEqual(self.ctrl.last_listener, self.t1)
            self.assertEqual(self.ctrl.current_listener, self.t1)
            self.assertEqual(self.ctrl.reads, {self.s1:1})
            self.assertEqual(self.ctrl.writes, {self.s2:1, s3:1})

        def rule2():
            self.assertEqual(self.ctrl.last_listener, self.t1)
            self.assertEqual(self.ctrl.current_listener, self.t2)
            self.assertEqual(self.ctrl.reads, {})
            self.assertEqual(self.ctrl.writes, {self.s2:1})
            self.ctrl.used(self.s2)
            self.ctrl.changed(s3)

        def rule0():
            pass

        s3 = TestSubject()
        self.runAs(self.t0, rule0)
        self.runAs(self.t1, rule1)
        self.assertEqual(self.ctrl.has_run,
            {self.t1:self.t1, self.t2:self.t1, self.t0: self.t0}
        )
        self.assertEqual(list(self.t1.iter_subjects()), [self.s1])
        self.assertEqual(list(self.t2.iter_subjects()), [self.s2])
        self.ctrl.rollback_to(self.ctrl.last_save)  # should undo both t1/t2
        self.assertEqual(self.ctrl.last_listener, self.t0)





    def testCommitCanLoop(self):
        log=[]
        def go():
            log.append(True)
        self.t0.run = go
        self.ctrl.atomically(self.ctrl.on_commit, self.ctrl.schedule, self.t0)
        self.assertEqual(log,[True])


































class TestCells(mocker.MockerTestCase):

    ctrl = stm.ctrl

    def testValueBasics(self):
        self.failUnless(issubclass(stm.Value, stm.AbstractCell))
        self.failUnless(issubclass(stm.Value, stm.AbstractSubject))
        v = stm.Value()
        self.assertEqual(v.value, None)
        self.assertEqual(v._set_by, stm._sentinel)
        self.assertEqual(v._reset, stm._sentinel)
        v.value = 21
        self.assertEqual(v._set_by, stm._sentinel)

    d(a)
    def testValueUndo(self):
        v = stm.Value(42)
        self.assertEqual(v.value, 42)
        sp = self.ctrl.savepoint()
        v.value = 43
        self.assertEqual(v.value, 43)
        self.ctrl.rollback_to(sp)
        self.assertEqual(v.value, 42)

    d(a)
    def testValueUsed(self):
        v = stm.Value(42)
        ctrl = self.mocker.replace(self.ctrl) #'peak.events.stm.ctrl')
        ctrl.used(v)
        self.mocker.replay()
        self.assertEqual(v.value, 42)

    def testValueChanged(self):
        v = stm.Value(42)
        ctrl = self.mocker.replace(self.ctrl)
        ctrl.lock(v)
        ctrl.changed(v)
        self.mocker.replay()
        v.value = 43
        self.assertEqual(v.value, 43)

    def testValueUnchanged(self):
        v = stm.Value(42)
        ctrl = self.mocker.replace(self.ctrl)
        ctrl.lock(v)
        mocker.expect(ctrl.changed(v)).count(0)
        self.mocker.replay()
        v.value = 42
        self.assertEqual(v.value, 42)

    d(a)
    def testValueSetLock(self):
        v = stm.Value(42)
        v.value = 43
        self.assertEqual(v.value, 43)
        self.assertEqual(v._set_by, None)
        def go():
            v.value = 99
        t = TestListener(); t.name = 't'
        t.run = go
        self.assertRaises(stm.InputConflict, self.ctrl.run, t)
        self.assertEqual(v.value, 43)
        def go():
            v.value = 43
        t = TestListener(); t.name = 't'
        t.run = go
        self.ctrl.run(t)
        self.assertEqual(v.value, 43)

    def testDiscrete(self):
        v = stm.Value(None, True)
        v.value = 42
        self.assertEqual(v.value, None)









    def testReadOnlyCellBasics(self):
        log = []
        c = stm.Cell(lambda:log.append(1))
        self.failUnless(type(c) is stm.ReadOnlyCell)
        c.value
        self.assertEqual(log,[1])
        c.value
        self.assertEqual(log,[1])

    def testDiscreteValue(self):
        log = []
        v = stm.Value(False, True)
        c = stm.Cell(lambda: log.append(v.value))
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
        self.failUnless(type(stm.Cell(value=42)) is stm.Value)
        self.failUnless(type(stm.Cell(lambda:42)) is stm.ReadOnlyCell)
        self.failUnless(type(stm.Cell(lambda:42, value=42)) is stm.Cell)

    def testRuleChain(self):
        v = stm.Value(0)
        log = []
        c1 = stm.Cell(lambda:int(v.value/2))
        c2 = stm.Cell(lambda:log.append(c1.value))
        c2.value
        self.assertEqual(log, [0])
        v.value = 1
        self.assertEqual(log, [0])
        v.value = 2
        self.assertEqual(log, [0, 1])

    def testConstant(self):
        for v in (42, [57], "blah"):
            c = stm.Constant(v)
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
        c = stm.Cell(go)
        self.assertEqual(c.value, 42)
        self.assertEqual(log, [1])
        self.failUnless(isinstance(c, stm.ConstantRule))
        self.assertEqual(repr(c), "Constant(42)")
        self.assertEqual(c.value, 42)
        self.assertEqual(c.get_value(), 42)
        self.assertEqual(c.rule, None)
        self.assertEqual(log, [1])
        self.failIf(c.dirty())
        c.__class__ = stm.ReadOnlyCell  # transition must be reversible to undo
        self.failIf(isinstance(c, stm.ConstantRule))















    def testDiscreteToConstant(self):
        log = []
        c1 = stm.ReadOnlyCell(lambda:True, False, True)
        c2 = stm.Cell(lambda:log.append(c1.value))
        c2.value
        self.assertEqual(log, [True, False])
        self.failUnless(isinstance(c1, stm.ConstantRule))

    def testReadWriteCells(self):
        C = stm.Cell(lambda: (F.value-32) * 5.0/9, -40)
        F = stm.Cell(lambda: (C.value * 9.0)/5 + 32, -40)
        self.assertEqual(C.value, -40)
        self.assertEqual(F.value, -40)
        C.value = 0
        self.assertEqual(C.value, 0)
        self.assertEqual(F.value, 32)

























def additional_tests():
    import doctest, sys
    files = [
        'README.txt', 'STM-Observer.txt', 'Collections.txt', 'Internals.txt',
        'Specification.txt',
    ][(sys.version<'2.4')*3:]   # README.txt uses decorator syntax
    return doctest.DocFileSuite(
        optionflags=doctest.ELLIPSIS|doctest.NORMALIZE_WHITESPACE, *files
    )
































