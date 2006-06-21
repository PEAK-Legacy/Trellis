===============================================================
Event-Driven Dependency Management with ``peak.events.trellis``
===============================================================

``peak.events.trellis`` is a dependency management framework for updating
values in a program.  When a value is changed, other values are automatically
updated, and code can be run to respond to value changes, somewhat like a
spreadsheet.

There are two things that are different from most other dependency-management
tools: synchronous updating, and automatic dependency discovery.

Synchronous updates means that all values are conceptually updated in lockstep,
such that there is never a time when the program's state is inconsistent due to
values being updated out of order.  In most event-driven systems, updates
are *asynchronous*, meaning that any value can change at any time, and some
values might change multiple times in response to a single input change,
leading to subtle bugs, especially as programs become more complex.

In contrast, synchronous updates ensure that every relevant value is updated
at most once for a change in a given input, making the system's dynamic
behavior easier to understand and far more likely to be bug-free.

Automatic dependency discovery means that there is no need to explicitly
"subscribe" or "listen" to anything.  Values that use other values in their
calculations automatically become dependent on the values they use.  If a
subsequent recalculation results in a new dependency relationship, that's kept
up-to-date also.

The concepts and algorithms used are courtesy of two systems, the "trellis
process architecture" described by David Gelernter in his book, "Mirror
Worlds", and the Lisp "Cells" library by Ken Tilton.  ``peak.events.trellis``
also takes some of its terminology from the Smalltalk "Value Model" frameworks.


.. contents:: **Table of Contents**


--------------
Programmer API
--------------

Value Objects
=============

``Value`` objects are the basis of the framework.  Each holds a value upon
which other values may depend.  There are three basic value types, ``Value``,
``Input``, and ``Constant``::

    >>> from peak.events.trellis import Value, Input, Constant

``Input`` objects simply hold a value::

    >>> v = Input(42)
    >>> v.value
    42

but ``Value`` objects use a *rule* to determine their value::

    >>> v_times_two = Value(lambda: v.value * 2)
    >>> v_times_two.value
    84

And that value always reflects the current values of any values that it depends
on::

    >>> v.value = 23
    >>> v_times_two.value
    46

``Constant`` values are initialized with a value, and are unchangeable
thereafter::

    >>> c = Constant(99)
    >>> c.value
    99
    >>> c.value -= 1
    Traceback (most recent call last):
      ...
    AttributeError: Constants can't be changed

Most of the time you won't use ``Constant`` objects directly, though, because
``Value`` objects automatically become ``Constant`` when they no longer depend
on any other ``Value`` or ``Input`` for their calculation.


-------------------
Internals and Tests
-------------------


Data Pulse Axioms
=================

Overview: updates must be synchronous (all changed values are updated at
once), consistent (no rule sees out of date values), and minimal (only
necessary rules run).

1. Per-Cell "As Of" Value: Every value has a "current-as-of" update count, that
is initialized with a value that is less than the global update count will ever
be::

    >>> v = Input(42)
    >>> def rule(): print "computing"; return v.value
    >>> c = Value(rule)
    >>> c.as_of
    -1

2. Global Update Counter: There is a global update counter that is incremented
whenever an ``Input`` value is changed.  This guarantees that there is a
globally-consistent notion of the "time" at which updates occur::

    >>> from peak.events.trellis import state

    >>> start = state.version
    >>> state.version - start
    0

3. Inputs Move The System Forward: When an ``Input`` changes, it increments
the global update count and stores the new value in its own update count::

    >>> i = Input(22)
    >>> state.version - start
    1

    >>> i.as_of - start
    1

    >>> i.value = 21
    >>> i.as_of - start
    2
    >>> state.version - start
    2

4. Out-of-dateness: A value is out of date if its update count is lower than
the update count of any of the values it depends on::

    >>> c.needs
    0
    >>> c.as_of < c.needs
    True

5. Out-of-date Before: When a ``Value`` object's ``.value`` is queried, its
rule is only run if the value is out of date; otherwise a cached previous value
is returned.  This guarantees that a rule is not run unless its dependencies
have changed since the last time the rule was run::

    >>> c.value
    computing
    42

6. Up-to-date After: Once a ``Value`` object's rule is run (or its ``.value``
is set, if it is an ``Input``), its update count must be equal to the global
update count.  This guarantees that a rule will not run more than once per
update::

    >>> c.as_of == state.version
    True

    >>> c.value
    42


Dependency Management Axioms
============================

Overview: values automatically notice when other value depend on them, then
notify them at most once if there is a change.

1. Thread-local "current rule": There is a thread-local variable that always
   contains the ``Value`` whose rule is currently being evaluated in the
   corresponding thread.  This variable can be empty (e.g. None)::

    >>> print state.computing
    None

2. "Currentness" Maintenance: While a ``Value`` object's rule is being run, the
   variable described in #1 must be set to point to the ``Value`` whose rule is
   being run.  When the rule is finished, the variable must be restored to
   whatever value it had before the rule began.  (Guarantees that values will
   be able to tell who is using them::

    >>> def rule():
    ...     print "computing", state.computing
    >>> v = Value(rule)

    >>> print state.computing   # between calculations
    None

    >>> v.value                 # during calculations
    computing <peak.events.trellis.Value object at ...>

    >>> print state.computing   # returns to None
    None

    >>> def rule1():
    ...     print "computing r1?", state.computing is r1
    ...     v = r2.value
    ...     print "r2 value =", v
    ...     print "computing r1?", state.computing is r1

    >>> def rule2():
    ...     print "computing r2?", state.computing is r2
    ...     return 42

    >>> r1, r2 = Value(rule1), Value(rule2)
    >>> r1.value        # verify that this works recursively
    computing r1? True
    computing r2? True
    r2 value = 42
    computing r1? True

3. Dependency Creation: When a value is read, it adds the "currently-being
   evaluated" value as a listener that it will notify of changes::

    >>> v1 = Input(99)
    >>> v2 = Value(lambda: v1.value * 2)
    >>> v3 = Value(lambda: v2.value * 2)

    >>> v1.listeners()
    []
    >>> v2.listeners()
    []
    >>> v3.listeners()
    []

    >>> v2.value    # causes v1 to depend on v2
    198
    >>> v1.listeners() == [v2]
    True

    >>> v2.listeners()
    []
    >>> v3.value
    396

    >>> v2.listeners() == [v3]
    True

4. Dependency Creation Order: New listeners are added only *after* the value
   being read has brought itself up-to-date, and notified any *previous*
   listeners of the change.  This ensures that the listening value does not
   receive redundant notification if the listened-to value has to be brought
   up-to-date first::

    >>> i1 = Input(1)
    >>> r1 = Value(lambda: i1.value)
    >>> r2 = Value(lambda x=[]: x or x.append(r1.value))    # one-time rule
    >>> print r2.value
    None

    >>> i1.listeners() == [r1]   # r1 is i1's only listener
    True
    >>> r1.listeners() == [r2]   # r2 is r1's only listener
    True

    >>> def showme():
    ...     r1.value    # r3 will be a listener of r2 now
    ...     if r1.listeners()==[r3]:
    ...         print "listeners of r1==[r3]"
    ...     elif r3 in r1.listeners():
    ...         print "subscribed"
    ...     if r1.as_of == i1.as_of: print "r1 is up-to-date"
    ...     if r2.as_of == i1.as_of: print "r2 is up-to-date"

    >>> r3 = Value(showme)
    >>> r3.value
    subscribed
    r1 is up-to-date
    r2 is up-to-date

    >>> i1.value = 2    # r2 will be notified and unsubscribed before listening
    listeners of r1==[r3]
    r1 is up-to-date
    r2 is up-to-date

    >>> i1.value = 3    # and r2 will not keep up with r1 any more
    listeners of r1==[r3]
    r1 is up-to-date

    >>> type(r2)        # because it's now a constant
    <class 'peak.events.trellis.Constant'>

5. Dependency Minimalism: A listener should only be added if it is not already
   present in the value's listener collection.  This isn't strictly
   mandatory, the system behavior will be correct but inefficient if this
   requirement isn't met::

   >>> i1 = Input(1)
   >>> r1 = Value(lambda: i1.value + i1.value)
   >>> r1.value
   2
   >>> i1.listeners()==[r1]
   True

6. Dependency Removal: Just before a value's rule is run, it must cease to be a
   listener for any other values.  (Guarantees that a dependency from a
   previous update cannot trigger an unnecessary repeated calculation.)

7. Dependency Notification: Whenever a ``Value`` or ``Input`` changes, it must
   notify all of its listeners that it has changed, in such a way that *none*
   of the listeners are asked to recalculate their value until *all* of
   the listeners have first been notified of the change.  (This guarantees
   that inconsistent views cannot occur.)

8. One-Time Notification Only: A value's listeners are removed from its
   listener collection as soon as they have been notified.  In particular, the
   value's collection of listeners must be cleared *before* *any* of the
   listeners are asked to recalculate themselves.  (This guarantees that
   listeners reinstated as a side effect of recalculation will not get a
   duplicate notification in the current update, or miss a notification in a
   future update.)

9. Conversion to Constant: If a ``Value`` object's rule is run and no
   dependencies were created, it must become a ``Constant``, doing no further
   listener additions or notification, once any necessary notifications to
   existing listeners are completed.  That is, if the rule's run changed its
   value, it must notify its existing listeners, but then the listener
   collection must be cleared -- *again*, in addition to the clearing described
   in #8.  (See #4 for the actual test of this.)

10. No Changes During Notification: It is an error to change an ``Input`` value
    while change notifications are taking place.

11. Weak Notification: Automatically created inter-value links must not inhibit
    garbage collection of either value::

    >>> del v3
    >>> v2.listeners()
    []

    >>> del v2
    >>> v1.listeners()
    []


Update Algorithm
================

A value must be computed if and only if it is out of date; otherwise, it should
just return its previous cached value.  A value is out of date if a
value it depends on has changed since the value was last calculated.  The
``as_of`` attribute tracks the version the value was last calculated "as of",
and the ``needs`` attribute records the latest version of any value this value
depends on.  If ``needs>=as_of``, the value is out of date::

    >>> x = Input(23)
    >>> def rule():
    ...     print "computing y from x"
    ...     return x.value * 2
    >>> y = Value(rule)
    >>> y.value
    computing y from x
    46

    >>> y.value
    46

    >>> x.value = 10
    computing y from x
    >>> y.value
    20

    >>> x.value = 10
    >>> y.value
    20

    >>> def rule2():
    ...     print "computing z from y"
    ...     return y.value - 1
    >>> z = Value(rule2)
    >>> z.value
    computing z from y
    19

    >>> x.value = 7
    computing y from x
    computing z from y


When a value changes, the values that depend on it must be brought up to date.
To ensure that no stale values can ever be seen, values must be marked
"out of date" before any values are recomputed.  Thus, update notification
has two phases: first, the listeners of a value are marked out-of-date, and
only then does recomputation occur.  This breadth-first traversal ensures that
inter-value dependencies can't cause a stale value to be seen, as might happen
if updates were done depth-first.

A value must not be marked out of date using a dependency that no longer
exists, however.  For example, if a value C depends on values A and B, and A
changes, then later B, the change to B should not mark C out-of-date unless
a new dependency was set up.

    >>> def C_rule():
    ...     print "computing",
    ...     if A.value<5:
    ...         print A.value, B.value
    ...     else:
    ...         print "...done"

    >>> A = Input(1)
    >>> B = Input(2)
    >>> C = Value(C_rule)

    >>> C.value
    computing 1 2
    >>> C.value

    >>> A.value = 3
    computing 3 2

    >>> B.value = 4
    computing 3 4

    >>> A.value = 5
    computing ...done

    >>> B.value = 6     # nothing happens, since C no longer depends on B
    >>> A.value = 3
    computing 3 6

    >>> B.value = 7     # but now it's back depending on B again.
    computing 3 7

    >>> B.value = 7
    >>> A.value = 1
    computing 1 7

    >>> A.value = 1


TODO
====

* Allow custom comparison function for "changedness"

* Allow rules to see their value owner, previous value, ???

* Value attributes

* Circular dependency checking

* Deferred updates or errors during propagation

* Observers

