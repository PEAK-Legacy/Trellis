===================================================================
Event-Driven Programming The Easy Way, with ``peak.events.trellis``
===================================================================

Whether it's an application server or a desktop application, any sufficiently
complex system is event-driven -- and that usually means callbacks.

Unfortunately, explicit callback management is to event-driven programming what
explicit memory management is to most other kinds of programming: a tedious
hassle and a significant source of unnecessary bugs.

For example, even in a single-threaded program, callbacks can create race
conditions, due to the callbacks being made in an unexpected order.  If a piece
of code can cause callbacks to be fired "in the middle of something", both that
code *and* the callbacks can get confused.

Of course, that's why most GUI libraries and other large event-driven systems
usually have some way for you to temporarily block callbacks from happening.
This lets you fix or workaround your callback order dependency bugs...  at the
cost of adding even *more* tedious callback management.  And it still doesn't
fix the problem of forgetting to cancel callbacks...  or register needed ones
in the first place!

The Trellis solves these problems by introducing *automatic* callback
management, in much the same way that Python does automatic memory management.
Instead of worrying about subscribing or "listening" to events, and managing
the order of callbacks, you just write rules to compute values.  The Trellis
"sees" what values your rules access, and thus knows what rules may need to be
rerun when something changes.

But even more important, it also ensures that callbacks *can't* happen while
code is "in the middle of something".  Any action a piece of code takes that
would cause a new event to fire is automatically deferred until all of the
current event's listeners have been updated.  And, if you try to access the
value of a rule that hasn't been updated yet, it's updated on the fly so it
reflects the current event-in-progress.

No stale data.  No race conditions.  No callback management.  That's the
Trellis in action.

Here's a super-trivial example::

    >>> from peak.events import trellis

    >>> class TempConverter(trellis.Component):
    ...     trellis.values(
    ...         F = 32,
    ...         C = 0,
    ...     )
    ...     trellis.rules(
    ...         F = lambda self: self.C * 1.8 + 32,
    ...         C = lambda self: (self.F - 32)/1.8,
    ...     )
    ...     #@trellis.rule   <-- decorator can be used in Python 2.4+
    ...     def show_values(self):
    ...         print "Celsius......", self.C
    ...         print "Fahrenheit...", self.F
    ...     show_values = trellis.rule(show_values)

    >>> tc = TempConverter(C=100)
    Celsius...... 100
    Fahrenheit... 212.0

    >>> tc.F = 32
    Celsius...... 0.0
    Fahrenheit... 32

    >>> tc.C = -40
    Celsius...... -40
    Fahrenheit... -40.0

As you can see, each attribute is updated if the other one changes, and the
``show_values`` rule is invoked any time the dependent values change...  but
not if they don't::

    >>> tc.C = -40

Since the value didn't change, none of the rules based on it were recalculated.

Now, imagine all this, but scaled up to include rules that can depend on things
like how long it's been since something happened...  whether a mouse button was
clicked...  whether a socket is readable...  or whether a Twisted "deferred"
object has fired.  With automatic dependency tracking that spans function
calls, so you don't even need to *know* what values your rule depends on, let
alone having to explicitly code any dependencies in!

Imagine painless MVC, where you simply write rules like the above to update
GUI widgets with application values... and vice versa.

And then, you'll have the tiny beginning of a mere glimpse...  of what the
Trellis can do for you.

Other Python libraries exist which attempt to do similar things, of course;
PyCells and Cellulose are two.  However, only the Trellis supports fully
circular rules (like the temperature conversion example above), and intra-pulse
write conflict detection.  The Trellis also uses less memory for each cell
(rule/value object), and offers many other features that either PyCells or
Cellulose lack.

Questions, discussion, and bug reports for this software should be directed to
the PEAK mailing list; see http://www.eby-sarna.com/mailman/listinfo/PEAK/
for details.


.. contents:: **Table of Contents**


------------------
Programmer's Guide
------------------


The Primary Principles:

* Avoid writing to cells in rules; writing is for non-trellis code

* If you must write, either write from only one rule, or write only one value!

* If you care what order two things happen in, make them happen in the same
  rule.



-------------
API Reference
-------------

Component, Cell, Constant, repeat, rule, rules, event, events, value,
values, optional, cell_factory, cell_factories

__cells__ attribute

component class metadata?



----
TODO
----

* List and dictionary models

* Time service & timestamp rules

* Generator-based tasks

* refresh(), volatile()

* .has_listeners(), .has_dependencies(), .clear_dependencies()

* IO events

* Cross-thread bridge cells

* signal() events

* Allow custom comparison function for "changedness"




