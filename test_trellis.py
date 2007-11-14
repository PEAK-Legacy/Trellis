from test_sets import *
from peak import context
from peak.events.activity import EventLoop, TwistedEventLoop, Time, NOT_YET
from peak.events import trellis
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




def additional_tests():
    import doctest, sys
    files = [
        'README.txt', 'Collections.txt', 'Internals.txt', 'Specification.txt'
    ][sys.version<'2.4':]   # README.txt uses decorator syntax
    return doctest.DocFileSuite(
        optionflags=doctest.ELLIPSIS|doctest.NORMALIZE_WHITESPACE, *files        
    )

































