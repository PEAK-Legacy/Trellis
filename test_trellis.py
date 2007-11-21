from test_sets import *
from peak import context
from peak.events.activity import EventLoop, TwistedEventLoop, Time, NOT_YET
from peak.events import trellis, stm
import unittest

try:
    import testreactor
except ImportError:
    testreactor = None  # either twisted or testreactor are missing
try:
    import wx
except ImportError:
    wx = None

class TestEventLoops(unittest.TestCase):
    def setUp(self):
        self.state = context.new()
        self.state.__enter__()
        super(TestEventLoops, self).setUp()
        self.configure_context()

    def tearDown(self):
        super(TestEventLoops, self).tearDown()
        self.state.__exit__(None, None, None)

    def configure_context(self):
        pass













if wx:
    class TestWxEventLoop(TestEventLoops):
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

    class TestReactorEventLoop(TestEventLoops, testreactor.ReactorTestCase):

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


        









def additional_tests():
    import doctest, sys
    files = [
        'README.txt', 'STM-Observer.txt', 'Collections.txt', 'Internals.txt',
        'Specification.txt',
    ][(sys.version<'2.4')*3:]   # README.txt uses decorator syntax
    return doctest.DocFileSuite(
        optionflags=doctest.ELLIPSIS|doctest.NORMALIZE_WHITESPACE, *files
    )

































