===================================================================
Event-Driven Programming The Easy Way, with ``peak.events.trellis``
===================================================================

(NOTE: As of 0.6a1, many advanced parts of the Trellis API have changed
significantly.  If you've done a lot with the 0.5 version API, we strongly
suggest reading the new manuals, especially the parts dealing with state
change.  Many old restrictions have been lifted, but some were replaced with
new ones.)

Whether it's an application server or a desktop application, any sufficiently
complex system is event-driven -- and that usually means callbacks.

Unfortunately, explicit callback management is to event-driven programming what
explicit memory management is to most other kinds of programming: a tedious
hassle and a significant source of unnecessary bugs.

For example, even in a single-threaded program, callbacks can create race
conditions, if the callbacks are fired in an unexpected order.  If a piece
of code can cause callbacks to be fired "in the middle of something", both that
code *and* the callbacks can get confused.

Of course, that's why most GUI libraries and other large event-driven systems
usually have some way for you to temporarily block callbacks from happening.
This lets you fix or workaround your callback order dependency bugs...  at the
cost of adding even *more* tedious callback management.  And it still doesn't
fix the problem of forgetting to cancel callbacks...  or register needed ones
in the first place!

The Trellis solves all of these problems by introducing *automatic* callback
management, in much the same way that Python does automatic memory management.
Instead of worrying about subscribing or "listening" to events and managing
the order of callbacks, you just write rules to compute values.  The Trellis
"sees" what values your rules access, and thus knows what rules may need to be
rerun when something changes -- not unlike the operation of a spreadsheet.

But even more important, it also ensures that callbacks *can't* happen while
code is "in the middle of something".  Any action a rule takes that would cause
a new event to fire is *automatically* deferred until all of the applicable
rules have had a chance to respond to the event(s) in progress.  And, if you
try to access the value of a rule that hasn't been updated yet, it's
automatically updated on-the-fly so that it reflects the current event in
progress.

No stale data.  No race conditions.  No callback management.  That's what the
Trellis gives you.

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
    ...     @trellis.observer
    ...     def show_values(self):
    ...         print "Celsius......", self.C
    ...         print "Fahrenheit...", self.F

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
``show_values`` action is invoked any time the dependent values change...  but
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

The Trellis package can can be `downloaded from the Python Package Index`_ or
installed using `Easy Install`_, and it has a fair amount of documentation,
including the following manuals:

* `Developer's Guide and Tutorial`_ (Extensively revised for 0.6a1)

* `Time, Event Loops, and Tasks`_ (NEW for 0.6a1)

* `Event-Driven Collections with the Trellis`_ (NEW for 0.6a1)

* `Software Transactional Memory (STM) And Observers`_ (NEW for 0.6a1)

Questions, discussion, and bug reports for the Trellis should be directed to
the `PEAK mailing list`_.

.. _downloaded from the Python Package Index: http://pypi.python.org/pypi/Trellis#toc
.. _Easy Install: http://peak.telecommunity.com/DevCenter/EasyInstall
.. _PEAK mailing list: http://www.eby-sarna.com/mailman/listinfo/PEAK/
.. _Developer's Guide and Tutorial: http://peak.telecommunity.com/DevCenter/Trellis#toc
.. _Time, Event Loops, and Tasks: http://peak.telecommunity.com/DevCenter/TrellisActivity
.. _Event-Driven Collections with the Trellis: http://peak.telecommunity.com/DevCenter/TrellisCollections
.. _Software Transactional Memory (STM) And Observers: http://peak.telecommunity.com/DevCenter/TrellisSTM

.. _toc:
.. contents:: **Table of Contents**


------------------------------
Developer's Guide and Tutorial
------------------------------


Creating Components, Cells, and Rules
=====================================

A ``trellis.Component`` is an object that can have its attributes automatically
maintained by rules, the way a spreadsheet is maintained by its formulas.

These managed attributes are called "cell attributes", because the attribute
values are stored in ``trellis.Cell`` objects.  The ``Cell`` objects can
contain preset values, values computed using rules, or even both at the same
time.  (Like in the temperature converter example above.)

To define a simple cell attribute, you can use the ``trellis.rules()`` and
``trellis.values()`` functions inside the class body to define multiple rules
and values.  Or, you can use the ``@trellis.rule`` decorator to turn an
individual function into a rule, or define a single value attribute by calling
``trellis.value``.  Last, but not least, you can use ``@trellis.observer`` to
define a rule that performs actions outside the Trellis.  Here's an example
that uses all of these approaches, simply for the sake of illustration::

    >>> class Rectangle(trellis.Component):
    ...     trellis.values(
    ...         top = 0,
    ...         width = 20,
    ...     )
    ...     left = trellis.value(0)
    ...     height = trellis.value(30)
    ...
    ...     trellis.rules(
    ...         bottom = lambda self: self.top + self.height,
    ...     )
    ...
    ...     @trellis.rule
    ...     def right(self):
    ...         return self.left + self.width
    ...
    ...     @trellis.observer
    ...     def show(self):
    ...         print self
    ...
    ...     def __repr__(self):
    ...         return "Rectangle"+repr(
    ...             ((self.left,self.top), (self.width,self.height),
    ...              (self.right,self.bottom))
    ...         )

    >>> r = Rectangle(width=40, height=10)
    Rectangle((0, 0), (40, 10), (40, 10))

    >>> r.width = 17
    Rectangle((0, 0), (17, 10), (17, 10))

    >>> r.left = 25
    Rectangle((25, 0), (17, 10), (42, 10))

By the way, any attributes for which you define a rule (but *not* a value) will
be read-only::

    >>> r.bottom = 99
    Traceback (most recent call last):
      ...
    AttributeError: can't set attribute

However, if you define both a rule *and* a value for the attribute, as we did
in the ``TemperatureConverter`` example, then you'll be able to both read and
write the attribute's value.

Note, by the way, that you aren't required to make everything in your program a
``trellis.Component`` in order to use the Trellis.  The ``Component`` class
does only four things, and you are free to accomplish these things some other
way if you need or want to:

1. It sets ``self.__cells__ = trellis.Cells(self)``.  This creates a special
   dictionary that will hold all the ``Cell`` objects used to implement cell
   attributes.

2. The ``__init__`` method takes any keyword arguments it receives, and uses
   them to initialize any named attributes.  (Note that this is the *only*
   thing the ``__init__`` method does, so you don't have to call it unless you
   want this behavior.)

3. It creates a cell for each of the object's non-optional cell attributes,
   in order to initialize their rules and set up their dependencies.  We'll
   cover this in more detail in the next section, `Automatic Activation and
   Dependencies`_.

4. It wraps the entire object creation process in a ``@modifier``, so that all
   of the above operations occur in a single logical transaction.  We'll cover
   this more in a later section on `Managing State Changes`_.

In addition to doing these things another way, you can also use ``Cell``
objects directly, without any ``Component`` classes.  This is discussed more
in the section below on `Working With Cell Objects`_.


Automatic Activation and Dependencies
-------------------------------------

You'll notice that each time we change an attribute value, our Rectangle
instance above prints itself -- including when the instance is first created.
That's because of two important Trellis principles:

1. When a ``Component`` instance is created, all its "non-optional" cell
   attributes are calculated after initialization is finished.  That is,
   if the attribute has a rule or is an observer, the function is invoked,
   and the result is used to determine the cell's initial value.

2. While a cell's rule is running, *any* trellis Cell whose value is looked at
   becomes a dependency of that rule.  If the looked-at cell changes later, it
   triggers recalculation of the rule that "looked".  In Trellis terms, we say
   that the first cell has become a "listener" of the second cell.

The first of these principles explains why the rectangle printed itself
immediately: the ``show`` observer cell was activated.  We can see this if we
look at the rectangle's ``show`` attribute::

    >>> print r.show
    None

(The ``show`` rule is an observer, so the resulting attribute value is
``None``.  Also notice that **rules are not methods** -- they are more like
properties.)

The second principle explains why the rectangle re-prints itself any time one
of the attributes changes value: all six attributes are referenced by the
``__repr__`` method, which is called when the ``show`` observer prints the
rectangle.  Since the cells that store those attributes are being looked at
during the execution of another cell's rule, they become dependencies, and the
``show`` rule is thus recalculated whenever the listened-to cells change.

Each time a rule runs, its dependencies are automatically re-calculated --
which means that if you have more complex rules, they can actually depend on
different cells every time they're calculated.  That way, the rule is only
recalculated when it's absolutely necessary.

By the way, a listened-to cell has to actually *change* its value (as determined
by the ``!=`` operator), in order to trigger recalculation.  Merely setting a
cell doesn't cause its observers to recalculate::

    >>> r.width = 17    # doesn't trigger ``show``

But changing it to a non-equal value *does*::

    >>> r.width = 18
    Rectangle((25, 0), (18, 10), (43, 10))

Note that if a cell rule ever has *no* dependencies -- that is, does not look
at any other cell attributes -- then it will not be recalculated.  This means
you can use trellis rules to create attributes that are automatically
initialized, but then keep the same value thereafter::

    >>> class Demo(trellis.Component):
    ...     aDict = trellis.rule(lambda self: {})

    >>> d = Demo()
    >>> d.aDict
    {}
    >>> d.aDict[1] = 2
    >>> d.aDict
    {1: 2}

A rule like this will return the same object every time, because it doesn't
use any other cells to compute its value.  So it runs once, and never again.
If we also defined a ``trellis.value`` for ``aDict``, then the attribute
would also be writable, and we could put a different value there.  But since
we didn't, it becomes read-only::

    >>> d.aDict = {}
    Traceback (most recent call last):
      ...
    AttributeError: Constants can't be changed

...even though we can override the initial value when the component is created,
or any time before it is first read::

    >>> d = Demo(aDict={3:4})
    >>> d.aDict
    {3: 4}

However, since this rule is not an "optional" rule, it will be read when the
component initialization is finished, meaning that the only chance we get to
override it is via the keyword arguments (or by setting it in a subclass's
``__init__`` method).  In the next section, we'll look at how to create
"optional" rules and observers: ones that don't get automatically calculated
when a component is created.


Observers vs. Rules
-------------------

You may have notice that we're using ``@trellis.observer`` to define rules that
print things out, and ``@trellis.rule`` for rules that calculate things.

We'll explain how and why this works later on.  For right now, just learn this
rule of thumb: if a rule has side-effects that can't be undone, it must be an
``observer``, not a ``rule``.  Observers are also not allowed to change any
cells or Trellis-managed data structures.  If you need to do both, you'll need
a ``rule`` *and* an ``observer``.

And what do we mean by "side-effects that can't be undone"?  Well, the Trellis
has an API for recording undo logs that can be used to roll back the effects of
a calculation in the event of an error or a required recalculation.

(Note, by the way, that this means observers should never raise errors.  If
they do, the changes that caused the observer to fire will be rolled back, but
if any other observers were fired first, their actions will *not* be rolled
back, leaving your application in an inconsistent state.)


We'll discuss the undo log mechanism in more detail later, in the section on
`Creating Your Own Data Structures`_.  For now, just remember that
``@trellis.observer`` should be used for side-effects that can't easily be
undone, like printing, or updating a GUI.  If you have a rule that just changes
other cells or Trellis-managed data structures, it's fine to use a
``@trellis.rule``.  But if you must change non-trellis data structures inside a
rule, you will need to log undo actions.


"Optional" Rules and Subclassing
--------------------------------

The ``show`` observer we've been playing with on our ``Rectangle`` class is
kind of handy for debugging, but it's kind of annoying when you don't need it.
Let's turn it into an "optional" observer, so that it won't run unless we ask
it to::

    >>> class QuietRectangle(Rectangle):
    ...     @trellis.optional
    ...     @trellis.observer
    ...     def show(self):
    ...         print self


By subclassing ``Rectangle``, we inherit all of its cell attribute definitions.
We call our new optional rule ``show`` so that its definition overrides the
noisy version of the rule.  And, because it's marked optional, it isn't
automatically activated when the instance is created.  So we don't get any
announcements when we create an instance or change its values::

    >>> q = QuietRectangle(width=18, left=25)
    >>> q.width = 17

Unless, of course, we activate the ``show`` rule ourselves::

    >>> q.show
    Rectangle((25, 0), (17, 30), (42, 30))

And from now on, it'll be just as chatty as the previous rectangle object::

    >>> q.left = 0
    Rectangle((0, 0), (17, 30), (17, 30))

While any other ``QuietRectangle`` objects we create will of course remain
silent, since we haven't activated *their* ``show`` cells::

    >>> q2 = QuietRectangle()
    >>> q2.top = 99

Notice, by the way, that rules are more like properties than methods, which
means you can't use ``super()`` to call the inherited version of a rule.
(Later, we'll look at other ways to access rule definitions.)


Model-View-Controller and the "Observer" Pattern
------------------------------------------------

As you can imagine, the ability to create rules like this can come in handy
for debugging.  Heck, there's no reason you have to print the values, either.
If you're making a GUI application, you can define rules that update displayed
fields to match application object values.

For that matter, you don't even need to define the rule in the same class!
For example::

    >>> class Viewer(trellis.Component):
    ...     trellis.values(model = None)
    ...
    ...     @trellis.observer
    ...     def view_it(self):
    ...         if self.model is not None:
    ...             print self.model

    >>> view = Viewer(model=q2)
    Rectangle((0, 99), (20, 30), (20, 129))

Now, any time we change q2, it will be printed by the Viewer's ``view_it``
rule, even though we haven't activated q2's ``show`` rule::

    >>> q2.left = 66
    Rectangle((66, 99), (20, 30), (86, 129))

This means that we can automatically update a GUI (or whatever else might need
updating), without adding any code to the thing we want to "observe".  Just
use cell attributes, and *everything* can use the "observer pattern" or be a
"Model-View-Controller" architecture.  Just define rules that can read from the
"model", and they'll automatically be invoked when there are any changes to
"view".

Notice, by the way, that our ``Viewer`` object can be repointed to any object
we want.  For example::

    >>> q3 = QuietRectangle()
    >>> view.model = q3
    Rectangle((0, 0), (20, 30), (20, 30))

    >>> q2.width = 59       # it's not watching us any more, so no output

    >>> view.model = q2     # watching q2 again
    Rectangle((66, 99), (59, 30), (125, 129))

    >>> q3.top = 77         # but we're not watching q3 any more

See how each time we change the ``model`` attribute, the ``view_it`` rule is
recalculated?  The rule references ``self.model``, which is a value cell
attribute.  So if you change ``view.model``, this triggers a recalculation,
too.

Remember: once a rule reads another cell, it will be recalculated whenever the
previously-read value changes.  Each time ``view_it`` is invoked, it renews
its dependency on ``self.model``, but *also* acquires new dependencies on
whatever the ``repr()`` of ``self.model`` looks at.  Meanwhile, any
dependencies on the attributes of the *previous* ``self.model`` are dropped,
so changing them doesn't cause the observer to be re-invoked any more.  This
means we can even do things like set ``model`` to a non-component object, like
this::

    >>> view.model = {}
    {}

But since dictionaries don't use any cells, changing the dictionary won't do
anything:

    >>> view.model[1] = 2

To be able to observe mutable data structures, you need to use data types like
``trellis.Dict`` and ``trellis.List`` instead of the built-in Python types.
We'll cover how that works in the section below on `Mutable Data Structures`_.

By the way, the links from a cell to its listeners are defined using weak
references.  This means that views (and cells or components in general) can
be garbage collected even if they have dependencies.  For more information
about how Trellis objects are garbage collected, see the later section on
`Garbage Collection`_.


Accessing a Rule's Previous Value
---------------------------------

Sometimes it's useful to create a rule whose value is based in part on its
previous value.  For example, a rule that produces an average over time, or
that ignores "noise" in an input value, by only returning a new value when the
input changes more than a certain threshhold since the last value.  It's fairly
easy to do this, using rules that refer to their previous value::

    >>> class NoiseFilter(trellis.Component):
    ...     trellis.values(
    ...         value = 0,
    ...         threshhold = 5,
    ...         filtered = 0
    ...     )
    ...     @trellis.rule
    ...     def filtered(self):
    ...         if abs(self.value - self.filtered) > self.threshhold:
    ...             return self.value
    ...         return self.filtered

    >>> nf = NoiseFilter()
    >>> nf.filtered
    0
    >>> nf.value = 1
    >>> nf.filtered
    0
    >>> nf.value = 6
    >>> nf.filtered
    6
    >>> nf.value = 2
    >>> nf.filtered
    6
    >>> nf.value = 10
    >>> nf.filtered
    6
    >>> nf.threshhold = 3   # changing the threshhold re-runs the filter...
    >>> nf.filtered
    10
    >>> nf.value = -3
    >>> nf.filtered
    -3

As you can see, referring to the value of a cell from inside the rule that
computes the value of that cell, will return the *previous* value of the cell.


Beyond The Spreadsheet: "Receiver" Cells
----------------------------------------

So far, all the stuff we've been doing isn't really any different than what you
can do with a spreadsheet, except maybe in degree.  Spreadsheets usually don't
allow the sort of circular calculations we've been doing, but that's not really
too big of a leap.

But practical programs often need to do more than just reflect the values of
things.  They need to *do* things, too.

While rule and value cells reflect the current "state" of things, discrete and
receiver cells are designed to handle things that are "happening".  They also
let us handle the "Controller" part of "Model-View-Controller".

For example, suppose we want to have a controller that lets you change the
size of a rectangle.  We can use "receiver" attributes to do this, which are
sort of like an "event", "message", or "command" in a GUI or other event-driven
system::

    >>> class ChangeableRectangle(QuietRectangle):
    ...     trellis.receivers(
    ...         wider    = 0,
    ...         narrower = 0,
    ...         taller   = 0,
    ...         shorter  = 0
    ...     )
    ...     trellis.rules(
    ...         width  = lambda self: self.width  + self.wider - self.narrower,
    ...         height = lambda self: self.height + self.taller - self.shorter,
    ...     )

    >>> c = ChangeableRectangle()
    >>> view.model = c
    Rectangle((0, 0), (20, 30), (20, 30))

A ``receiver`` attribute (created with ``trellis.receiver()`` or
``trellis.receivers()``) works by "receiving" an input value, and then
automatically resetting itself to its default value after its dependencies are
updated.  For example::

    >>> c.wider
    0

    >>> c.wider = 1
    Rectangle((0, 0), (21, 30), (21, 30))

    >>> c.wider
    0

    >>> c.wider = 1
    Rectangle((0, 0), (22, 30), (22, 30))

Notice that setting ``c.wider = 1`` updated the rectangle as expected, but as
soon as all updates were finished, the attribute reset to its default value of
zero.  In this way, every time you put a value into a receiver, it gets
processed and discarded.  And each time you set it to a non-default value,
it's treated as a *change*.  Which means that any rule that depends on the
receiver will be recalculated.  If we'd used a normal ``trellis.value`` here,
then set ``c.wider = 1`` twice in a row, nothing would happen the second time!

Now, we *could* write methods for changing value cells that would do this sort
of resetting for us, but why?  We'd need to have both the attribute *and* the
method, and we'd need to remember to never set the attribute directly.  It's
much easier to just use a receiver as an "event sink" -- that is, to receive,
consume, and dispose of any messages or commands you want to send to an object.

But why do we need such a thing at all?  Why not just write code that directly
manipulates the model's width and height?  Well, sometimes you *can*, but it
limits your ability to create generic views and controllers, makes it
impossible to "subscribe" to an event from multiple places, and increases the
likelihood that your program will have bugs -- especially order-dependency
bugs.

If you use rules to *compute* values instead of writing code to *manipulate*
values, then all the code that affects a value is in *exactly one place*.  This
makes it very easy to verify whether that code is correct, because the way
the value is arrived at doesn't depend on what order a bunch of manipulation
methods are being called in, and whether those methods are correctly updating
everything they should.

Thus, as long as a cell's rule doesn't modify *anything* except local
variables, there is no way for it to become "corrupt" or "out of sync" with the
rest of the program.  This is a form of something called "referential
transparency", which roughly means "order independent".  We'll cover this topic
in more detail in the later section on `Managing State Changes`_.  But in the
meantime, let's look at how using receivers instead of methods also helps us
implement generic controllers.


Creating Generic Controllers by Sharing Cells
---------------------------------------------

Let's create a couple of generic "Spinner" controllers, that take a pair of
"increase" and "decrease" receivers, and hook them up to our changeable
rectangle::

    >>> class Spinner(trellis.Component):
    ...     """Increase or decrease a value"""
    ...     increase = trellis.receiver(0)
    ...     decrease = trellis.receiver(0)
    ...     by = trellis.value(1)
    ...
    ...     def up(self):
    ...         self.increase = self.by
    ...
    ...     def down(self):
    ...         self.decrease = self.by

    >>> cells = trellis.Cells(c)
    >>> width = Spinner(increase=cells['wider'], decrease=cells['narrower'])
    >>> height =  Spinner(increase=cells['taller'], decrease=cells['shorter'])

The ``trellis.Cells()`` API returns a dictionary containing all active cells
for the object.  (We'll cover more about this in the section below on `Working
With Cell Objects_`.)  You can then access them directly, assigning them to
other components' attributes.

Assigning a ``Cell`` *object* to a cell *attribute* allows two components to
**share** the same cell.  In this case, that means setting the ``.increase``
and ``.decrease`` attributes of our ``Spinner`` objects will set the
corresponding attributes on the rectangle object, too::

    >>> width.up()
    Rectangle((0, 0), (23, 30), (23, 30))

    >>> width.down()
    Rectangle((0, 0), (22, 30), (22, 30))

    >>> height.by = 5

    >>> height.down()
    Rectangle((0, 0), (22, 25), (22, 25))

    >>> height.up()
    Rectangle((0, 0), (22, 30), (22, 30))


Could you do the same thing with methods?  Maybe.  But can methods be linked
the *other* way?::

    >>> width2 = Spinner()
    >>> height2 = Spinner()
    >>> controlled_rectangle = ChangeableRectangle(
    ...     wider = trellis.Cells(width2)['increase'],
    ...     narrower = trellis.Cells(width2)['decrease'],
    ...     taller = trellis.Cells(height2)['increase'],
    ...     shorter = trellis.Cells(height2)['decrease'],
    ... )

    >>> view.model = controlled_rectangle
    Rectangle((0, 0), (20, 30), (20, 30))

    >>> height2.by = 10
    >>> height2.up()
    Rectangle((0, 0), (20, 40), (20, 40))

A shared cell is a shared cell: it doesn't matter which "direction" you share
it in!  It's a simple way to create an automatic link between two parts
of your program, usually between a view or controller and a model.  For
example, if you create a text editing widget for a GUI application, you can
define a value cell for the text in its class::

    >>> class TextEditor(trellis.Component):
    ...     text = trellis.value('')
    ...
    ...     @trellis.observer
    ...     def display(self):
    ...         print "updating GUI to show", repr(self.text)

    >>> te = TextEditor()
    updating GUI to show ''

    >>> te.text = 'blah'
    updating GUI to show 'blah'

And then you'd write some additional code to automatically set ``self.text``
when there's accepted input from the GUI.  An instance of this editor can then
either maintain its own ``text`` cell, or be given a cell from an object whose
attributes are being edited.

This allows you to independently test your models, views, and controllers, then
simply link them together at runtime in any way that's useful.


"Discrete" Rules
----------------

Receiver attributes are designed to "accept" what might be called events,
messages, or commands.  But what if you want to generate or transform such
events instead?

Let's look at an example.  Suppose you'd like to trigger an action whenever a
new high temperature is seen::

    >>> class HighDetector(trellis.Component):
    ...     value = trellis.value(0)
    ...     last_max = trellis.value(None)
    ...
    ...     @trellis.rule
    ...     def new_high(self):
    ...         last_max = self.last_max
    ...         if last_max is None:
    ...             self.last_max = self.value
    ...             return False    # first seen isn't a new high
    ...         elif self.value > last_max:
    ...             self.last_max = self.value
    ...             return True
    ...         return False
    ...
    ...     @trellis.observer
    ...     def monitor(self):
    ...         if self.new_high:
    ...             print "New high"

The ``max_and_new`` rule returns two values: the current maximum, and a flag
indicating whether a new high was reached.  It refers to itself in order to
see its own *previous* value, so it can tell whether a new high has been
reached.  We set a default value of ``(None, False)`` so that the first time
it's run, it will initialize itself correctly.  We then split out the "new
high" flag from the tuple, using another rule.

The reason we do the calculation this way, is that it makes our rule
"re-entrant".  Because we're not modifying anything but local variables,
it's impossible for an error in this rule to leave any corrupt data behind.
We'll talk more about how (and why) to do things this way in the section below
on `Managing State Changes`_.

In the meantime, let's take our ``HighDetector`` for a test drive::

    >>> hd = HighDetector()

    >>> hd.value = 7
    New high

    >>> hd.value = 9

Oops!  We set a new high value, but the ``monitor`` rule didn't detect a new
high, because ``new_high`` was *already True* from the previous high.

Normal rules return what might be called "continuous" or "steady state" values.
That is, their value remains the same until something causes them to be
recalculated.  In this case, the second recalculation of ``new_high`` returns
``True``, just like the first one...  meaning that there's no change, and no
observer recalculation.

But "discrete" rules are different.  Just like receivers, their value is
automatically reset to a default value as soon as all their observers have
"seen" the original value.  Let's try a discrete version of the same thing::

    >>> class HighDetector2(HighDetector):
    ...     new_high = trellis.value(False)
    ...
    ...     @trellis.discrete
    ...     def new_high(self):
    ...         # this is a bit like a super() call, but for a rule:
    ...         return trellis.CellRules(HighDetector)['new_high'](self)
    
    >>> hd = HighDetector2()

    >>> hd.value = 7
    New high

    >>> hd.value = 9
    New high

    >>> hd.value = 3

    >>> hd.value = 16
    New high

As you can see, each new high is detected correctly now, because the value
of ``new_high`` resets to ``False`` after it's calculated as (or set to) any
other value::

    >>> hd.new_high
    False

    >>> hd.new_high = True
    New high

    >>> hd.new_high
    False

By the way, that ``trellis.CellRules(HighDetector)['new_high']`` in the new
``new_high`` rule retrieves the base class version of the rule.  We could also
have done the same thing this way::

    >>> class HighDetector2(HighDetector):
    ...     new_high = trellis.value(False)
    ...     new_high = trellis.discrete(
    ...         trellis.CellRules(HighDetector)['new_high']
    ...     )

and the result would have been the same, except it would run faster since the
lookup of the inherited rule only happens once.


Wiring Up Multiple Components
-----------------------------

Over the course of this tutorial, we've created a whole bunch of different
objects, like the temperature converter, high detector, changeable rectangle,
and a simple viewer.  Let's link them up together to make a rectangle that
gets wider and taller whenever the Celsius temperature reaches a new high::

    >>> tc = TempConverter()
    Celsius...... 0.0
    Fahrenheit... 32.0

    >>> hd = HighDetector2(value = trellis.Cells(tc)['C'])
    >>> cr = ChangeableRectangle(
    ...     wider  = trellis.Cells(hd)['new_high'],
    ...     taller = trellis.Cells(hd)['new_high'],
    ... )

    >>> viewer = Viewer(model = cr)
    Rectangle((0, 0), (20, 30), (20, 30))

    >>> tc.F = -40
    Celsius...... -40.0
    Fahrenheit... -40

    >>> tc.F = 50
    Celsius...... 10.0
    Fahrenheit... 50
    New high
    Rectangle((0, 0), (21, 31), (21, 31))

Crazy, huh?  None of these components were designed with any of the others in
mind, but because they all "speak Trellis", you can link them up like building
blocks to do new and imaginative things.

By the way, although in this demonstration we saw the three outputs in one
particular order, in general the Trellis does not guarantee what order rules
will be recalculated in, so it's unwise to assume that your program will
always produce results in a certain order, unless you've taken steps to ensure
that it will.

That's why managing the order of Trellis output (and dealing with state changes
in general) is the subject of our next major section.


Managing State Changes
======================

Time is the enemy of event-driven programs.  They say that time is "nature's
way of keeping everything from happening at once", but in event-driven programs
we usually *want* certain things to happen "all at once"!

For example, suppose we want to change a rectangle's top and left
co-ordinates::

    >>> r.top = 66
    Rectangle((25, 66), (18, 10), (43, 76))

    >>> r.left = 53
    Rectangle((53, 66), (18, 10), (71, 76))

Oops!  If we were updating a GUI like this, we would see the rectangle move
first down and then sideways, instead of just going to where it belongs in one
movement.

Therefore, in most practical event-driven systems, certain kinds of changes
are automatically deferred, usually by adding them to some kind of event queue
so that they can happen later, after all the desired changes have happened.
That way, they don't take effect until the current event is completely
finished.


Modifiers
---------

The Trellis actually does something similar, but its internal "event queue" is
automatically flushed whenever you set a value from outside a rule.  If you
want to set multiple values, you need to use a ``@modifier`` function or
method like this one, which we could've made a method of ``Rectangle``, but
didn't::

    >>> @trellis.modifier
    ... def set_position(rectangle, left, top):
    ...     rectangle.left = left
    ...     rectangle.top = top

    >>> set_position(r, 55, 22)
    Rectangle((55, 22), (18, 10), (73, 32))

Notifications of changes made by a ``modifier`` do not take effect until the
*outermost* active ``modifier`` function returns.  (In other words, if one
``modifier`` directly or indirectly calls another ``modifier``, the inner
modifier's changes don't cause notifications to occur until the same time
as the outer modifier's changes do.)

Now, notice that this means that within a ``modifier``, you can't rely on any
values controlled by rules to be updated when you make changes.  This means
it's generally a bad idea for a rule to look at what it's changing.  For
example::

    >>> @trellis.modifier
    ... def set_position(rectangle, left, top):
    ...     rectangle.left = left
    ...     rectangle.top = top
    ...     print rectangle

    >>> set_position(r, 22, 55)
    Rectangle((22, 55), (18, 10), (73, 32))
    Rectangle((22, 55), (18, 10), (40, 65))

The first print is from inside the rule, showing that from the rule's
perspective, the bottom/right co-ordinates are not updated to reflect the
changed top/left co-ordinates.  The second print is from an observer, showing
that the values *do* get updated after the modifier has exited.


The Evil of Order Dependency
----------------------------

The reason that time is the enemy of event driven programs is because time
implies order, and order implies order **dependency** -- a major source of bugs
in event-driven and GUI programs.

Writing a polished GUI program that has no visual glitches or behavioral quirks
is difficult *precisely* because such things are the result of changes in the
order that events occur in.

Worse still, the most seemingly-minor change to a previously working version of
such a program can introduce a whole slew of new bugs, making it hard to
predict how long it will take to implement new features.  And as a program
gets more complex, even fixing bugs can introduce new bugs!

Indeed, Adobe Systems Inc. estimates that nearly *half* of all their reported
desktop application bugs (across all their applications!) are caused by such
event-management problems.

So a major goal of the Trellis' is to not only **wipe out** these kinds of
bugs, but to prevent most of them from happening in the first place.

And all you have to do to get the benefits, is to divide your code three ways:

* Input code, that sets trellis cells or calls modifier methods (but does not
  run *inside* trellis rules).  This kind of code is usually invoked by GUI or
  other I/O callbacks, or by top-level non-trellis code.

* Processing rules that compute values, and/or make undo-able changes to cells
  or other data structures.

* Output rules that send data on to other systems (like the screen, a socket,
  a database, etc.).  This code may appear in ``@trellis.observer`` rules, or
  it can be "application" code that reads results from a finished trellis
  calculation.

The first and third kinds of code are inherently order-dependent, since
information comes in (and must go out) in a meaningful order.  However, by
putting related outputs in the same observer (or non-trellis code), you can
ensure that the required order is enforced by a single piece of code.  This
approach is highly bug-resistant.

Second, you can reduce the order dependency of input code by making it do as
little as possible, simply dumping data into input cells, where it can be
handled by processing rules.  And, since input controllers can be very generic
and highly-reusable, there's a natural limit to how much input code you will
need.

By using these approaches, you can maximize the portion of your application
that appears in side effect-free (or at least undo-able) processing rules,
which the Trellis makes 100% immune to order dependencies.  Anything that
happens in Trellis rules, happens *instantaneously*, in a logical sense.  Ther
is no "order", and thus no order dependency.

In truth, of course, rules do execute in *some* order.  However, as long as the
rules don't do anything but compute their own values, then it cannot matter
what order they do it in.  (The trellis guarantees this by automatically
recalculating rules whenever their dependencies change, and undoing any
calculations that "saw" out-of-date or inconsistent values.)


The Side-Effect Rules
---------------------

To sum up the recommended approach to handling side-effects in Trellis-based
programs, here are a few brief guidelines that will keep your code easy to
write, understand, and debug.


Rule 1 - If Order Matters, Use Only One Observer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you care what order two "outside world" side-effects happen in, code them
both in the same observer.

For example, in the ``TempConverter`` demo, we had an observer that printed the
Celsius and Fahrenheit temperatures.  If we'd put those two ``print`` statements
in separate observers, we'd have had no control over the output order; either
Celsius or Fahrenheit might have come first on any given change to the
temperatures.  So, if you care about the relative order of certain output or
actions, you must put them all in one observer.  If that makes the code too big
or complex, you can always refactor to extract new rules to calculate the
intermediate values.  Just don't put any of the external actions in the other
rules, only the *calculations*.  Then have an observer that *only* does the
external actions.


Rule 2 - When Setting Or Changing, Use One Rule or One Value
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you set a value from more than one place, you are introducing an order
dependency.  In fact, if you set a cell value from more than one rule, the
Trellis will stop you, unless the values are equal.  For example::

    >>> class Conflict(trellis.Component):
    ...     value = trellis.value(99)
    ...
    ...     @trellis.rule
    ...     def ruleA(self):
    ...         self.value = 22
    ...
    ...     @trellis.rule
    ...     def ruleB(self):
    ...         self.value = 33

    >>> Conflict()
    Traceback (most recent call last):
      ...
    InputConflict: (33, 22)

This example fails because the two rules set different values for the ``value``
attribute, causing a conflict error.  Since the rules don't agree, the result
would depend on the order in which the rules happened to run -- which again is
precisely what we don't want in an event-driven program.

So this rule is for your protection, because it makes it impossible for you to
accidentally set the same thing in two different places in response to an
event, and then miss the bug or be unable to reproduce it because the second
change masks the first!

Instead, what happens is that assigning two different values to the same cell
in response to the same event always produces an error message, making it
easier to find the problem.  Of course, if you arrange your input code so that
only one piece of input code is setting trellis values for a given event, or
only one piece of code ever modifies a given cell or data structure, then
you'll never have this problem.

Of course, if all of your code is setting a cell to the *same* value, you won't
get a conflict error either.  This is mostly useful for e.g. receiver cells
that represent a command the program should do.  If you have GUI input code
that triggers a command by setting some receiver to ``True`` whenever that
command is selected from a menu, invoked by a keyboard shorcut, or accessed
with a toolbar button click, then it doesn't matter which event happens or
even if all three could somehow happen at the same time, because the end result
is exactly the same: the receiver processes the ``True`` message once and then
discards it.


Rule 3 - Rule Side-Effects MUST Be Logged For Undo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If your rules only set cell values or modify trellis-managed data structures,
you don't need to worry about undo logging, as it's taken care of for you.

However, if you implement any other kind of side-effects in a rule (such as
updating a mutable data structure that's not trellis-managed), you **must**
record undo actions to allow the trellis to roll back your rule's action(s), in
the event that it must be recalculated due to an order inconsistency, or if an
error occurs during recalculation.  If you don't do this, you risk corrupting
your program's state.  This is especially important if you are creating a new
trellis-managed data structure type.

In general, it's best to keep side-effects in rules to a minimum, and use only
cells and other trellis-managed data structures.  And of course, any side
effects that can't easily be undone should be placed in an @observer, which is
guaranteed to run no more than once per overall recalculation of the trellis.

However, if you are creating your own trellis-managed data structure type, you
will need to use the ``trellis.on_undo()`` API to register undo callbacks, to
protect your data structure's integrity.  See the section below on `Creating
Your Own Data Structures`_ for more details on how this works.


Rule 4 - If You Write, Don't Read!
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Be aware that rules with side-effects **cannot** see the ultimate effect of
their changes, and so should avoid reading anything but their minimum required
inputs.  For example::

    >>> import sys
    
    >>> class ChangeTakesTime(trellis.Component):
    ...     v1 = trellis.value(2)
    ...     v2 = trellis.rule(lambda self: self.v1*2)
    ...     @trellis.rule
    ...     def update(self):
    ...         if self.v1!=3:
    ...             print "before", self.v1, self.v2
    ...             self.v1 = 3
    ...             print "after", self.v1, self.v2

    >>> x = ChangeTakesTime()
    before 2 4
    after 3 4

    >>> x.v2
    6

Here's what's happening: first, ``v2`` is calculated as ``2*2 == 4``.  Then,
the ``update`` rule sets ``v1`` to 3.  However, ``v2`` is NOT immediately
updated.  Instead, it's put on a schedule of rules to be re-run.  So the
``update`` rule still sees the OLD value of ``v2``.

So, if you are making any kind of changes from inside a rule, beware of trying
to read anything that might be affected by those changes, as you will likely
see something that's out of date.  This is particularly important when changing
trellis-managed data structures, since many data structures rely on rules for
their internal consistency.  So if you write and read the same data structure
from a single rule, you will almost certainly see inconsistent results.


Mutable Data Structures
-----------------------

So far, all of our Trellis examples have worked with atomic cell values, like
integers, strings, and so forth.  We've avoided working with lists, sets,
dictionaries, and similar structures, because the standard Python
implementations of these types can't be "observed" by rules, which means that
they won't be automatically updated.

But this doesn't mean you can't use sets, lists, and dictionaries.  You just
need to use Trellis-managed ones.  (Of course, all the warnings above about
changing values still apply; just because you're modifying something other
than attributes, doesn't mean you're not still modifying things!)

The Trellis package provides three primary mutable types for you to use in your
components: ``Set``, ``List``, and ``Dict``.  You can also subclass them or
create your own mutable types, as we'll discuss in a later section.  (And, the
``peak.events.collections`` module also provides some fancier data structures;
see the `Collections manual`_ for details.)

.. _Collections manual: http://peak.telecommunity.com/DevCenter/TrellisCollections


trellis.Dict
~~~~~~~~~~~~

The ``trellis.Dict`` type looks pretty much like any dictionary, but it can
be observed by rules.  Any change to the dictionary's contents will result
in its observers being recalculated.  For example, if we use our ``view``
object (defined way back in the section on `Model-View-Controller and the
"Observer" Pattern`_), we can print it whenever it changes, no matter how it
changes::

    >>> d = trellis.Dict(a=1)
    >>> view.model = d
    {'a': 1}

    >>> del d['a']
    {}

    >>> d['a'] = 2
    {'a': 2}

Unlike normal values, however, even changing a dictionary entry to the same
value will trigger a recalculation::

    >>> d['a'] = 2
    {'a': 2}

This is because the ``Dict`` type doesn't try to compare the values you put
into it.  If you need to prevent such recalculations from happening, you can
always check the dictionary contents first, or create a subclass and override
``__setitem__`` (but be sure to read the section on `Creating Your Own Data
Structures`_ for some important information first).

In addition to these basic features, the ``Dict`` type provides three receiver
attributes (``added``, ``changed``, and ``deleted``) that reflect changes
currently in progress.  Ordinarily, they are empty dictionaries, but while a
change is taking place they temporarily become non-empty.  For example::

    >>> view.model = None

    >>> class Dumper(trellis.Component):
    ...     @trellis.observer
    ...     def dump(self):
    ...         for name in 'added', 'changed', 'deleted':
    ...             if getattr(d, name):
    ...                 print name, '=', getattr(d, name)
    >>> dumper=Dumper()

    >>> del d['a']
    deleted = {'a': 2}

    >>> d[3] = 4
    added = {3: 4}

    >>> d[3] = 5
    changed = {3: 5}

    >>> @trellis.modifier
    ... def two_at_once():
    ...     del d[3]
    ...     d[4] = 5

    >>> two_at_once()
    added = {4: 5}
    deleted = {3: 5}

These dictionaries immediately reset to empty as soon as a change has been
fully processed, so you'll never see anything in them if you look from non-rule
code::

    >>> d.added
    {}

Also note that you cannot use the ``.pop()``, ``.popitem()``, or
``.setdefault()`` methods of ``Dict`` objects::

    >>> d.setdefault(1, 2)
    Traceback (most recent call last):
      ...
    InputConflict: Can't read and write in the same operation

Remember: the trellis wants all changes to be deferred until the next
recalculation.  That means you can't see the effect of a change in the same
moment during which you *make* the change, so operations like ``pop()`` are
disallowed, because they would have to return the same value no matter how
many times you called it during the same recalculation!  (Otherwise, the
change hasn't really been deferred.)

This limitation also applies to the ``pop()`` method of ``List`` and ``Set``
objects, as we'll see in the next two sections.


trellis.Set
~~~~~~~~~~~

Trellis ``Set`` objects offer nearly all the comforts of the Python standard
library's ``sets.Set`` objects (minus ``.pop()``, and support for sets of
mutable sets), but with observability::

    >>> s = trellis.Set("abc")
    >>> view.model = s
    Set(['a', 'c', 'b'])

    >>> s.add('d')
    Set(['a', 'c', 'b', 'd'])

    >>> s.remove('c')
    Set(['a', 'b', 'd'])

    >>> s -= trellis.Set(['a', 'b'])
    Set(['d'])

Similar to the ``Dict`` type, the ``Set`` type offers receiver set attributes,
``added`` and ``removed``, that reflect changes-in-progress to the set::

    >>> view.model = None

    >>> class Dumper(trellis.Component):
    ...     @trellis.observer
    ...     def dump(self):
    ...         for name in 'added', 'removed':
    ...             if getattr(s, name):
    ...                 print name, '=', list(getattr(s, name))
    >>> dumper=Dumper()

    >>> s.add('a')
    added = ['a']

    >>> s.add('a')      # duplicates are ignored

    >>> s.remove('d')
    removed = ['d']

Note, however, that you cannot use the ``.pop()`` method of ``Set`` objects::

    >>> s.pop()
    Traceback (most recent call last):
      ...
    InputConflict: Can't read and write in the same operation

Remember: as with ``trellis.Dict``, operations like ``pop()`` are disallowed
here because they would require reading the effect of a change, before the
logical future moment in which the change actually takes effect.


trellis.List
~~~~~~~~~~~~

A ``trellis.List`` looks and works pretty much the same as a normal Python
list, except that it can be observed by rules::

    >>> myList = trellis.List([1,2,3])
    >>> myList
    [1, 2, 3]

    >>> myList.reverse()    # no output while not being observed

    >>> view.model = myList
    [3, 2, 1]

    >>> myList.reverse()    # but now we're being watched
    [1, 2, 3]

    >>> myList.insert(0, 4)
    [4, 1, 2, 3]

    >>> myList.sort()
    [1, 2, 3, 4]

``trellis.List`` objects also have a receiver attribute called ``changed``.
It's normally false, but is temporarily ``True`` during the recalculation
triggered by a change to the list.  But as with all receiver attributes, you'll
never see a value in it from non-rule code::

    >>> myList.changed
    False

Only in rule code will you ever see it true, a moment before it becomes false::

    >>> view.model = None   # quiet, please

    >>> class Watcher(trellis.Component):
    ...     @trellis.observer
    ...     def dump(self):
    ...         print myList.changed

    >>> watcher=Watcher()
    False

    >>> del myList[0]
    True
    False

    >>> myList
    [2, 3, 4]

Note, however, that you cannot use the ``.pop()`` method of ``List`` objects::

    >>> myList.pop()
    Traceback (most recent call last):
      ...
    InputConflict: Can't read and write in the same operation

Remember: as with ``trellis.Dict`` and ``trellis.Set``, operations like
``pop()`` are disallowed here because they would require reading the effect of
a change, before the logical future moment in which the change actually takes
effect.

``trellis.List`` objects also have some inherent inefficiencies due to the wide
variety of operations supported by Python lists.  While ``trellis.Set``
and ``trellis.Dict`` objects update themselves in place by applying change
logs, ``trellis.List`` has to use a copy-on-write strategy to manage updates,
because there isn't any simple way to reduce operations like ``sort()``,
``reverse()``, ``remove()``, etc. to a meaningful change log.  (That's why
it only provides a simple ``changed`` flag.)

So if you need to use large lists in an application, you may be better off
creating a custom data structure of your own design.  That way, if you only
need a subset of the list interface, you can implement a changelog-based
structure.  For example, the Trellis package includes a ``SortedSet`` type
that maintains an index of items sorted by keys, with a cell that lists
changed regions.  (See the `Collections manual`_ for more details.)


Creating Your Own Data Structures
---------------------------------

If you want to create your own data structures along the lines of ``Dict``,
``List``, and ``Set``, you have a few options.  First, you can just build
components that use those existing data types, and use ``@modifier`` methods
to perform operations on them.  (If you just directly perform operations, then
listeners of your data structure may be recalculated in the middle of your
changes, and see an inconsistent state.)

Depending on the nature of the data structure you need, however, this may not
be sufficient.  For example, when you perform multiple operations on a
``trellis.Dict``, the later operations need to know about changes made by the
earlier ones.  If you add some items and then delete one, for example, the dict
needs to know whether the item you're deleting is one of the ones that you
added.

But, if you use normal read operations on the dictionary (like ``.has_key()``),
these will only reflect the "before" state -- what the dictionary had in it
during the current recalculation, before any new changes were made.

So, the Trellis-supplied data types use a couple of special tools to allow them
to "see the future" (and change it).

Let's suppose that we're creating a simple "queue" type, that keeps track of
items added to it.  Its output is a list of the most-recently added items,
and the list becomes empty in the next recalculation if nobody adds anything to
it::

    >>> class Queue(trellis.Component):
    ...     items = trellis.todo(lambda self: [])
    ...     to_add = items.future
    ...
    ...     @trellis.modifier
    ...     def add(self, item):
    ...         self.to_add.append(item)
    ...
    ...     def __repr__(self):
    ...         return str(self.items)

    >>> q = Queue()
    >>> view.model = q
    []

    >>> q.add(1)
    [1]
    []

    >>> @trellis.modifier
    ... def add_many(*args):
    ...     for arg in args: q.add(arg)

    >>> add_many(1,2,3)
    [1, 2, 3]
    []

Let's break down the pieces here.  First, we create a "todo" cell.  A todo
cell is discrete (like a ``receiver`` cell or ``@discrete`` rule), which means
it resets to its default value after any changes.  (By the way, you can define
todo cells with either a direct call as shown here, a ``@trellis.todo``
decorator on a function, or using ``trellis.todos(attr=func, ...)`` in your
class body.)

The default value of a ``@todo`` cell is determined by calling the function it
wraps, when the cell is created.  This value is then saved as the default value
for the life of the cell.

The second thing that we do in this class is create a "future" view.  Todo
cell properties have a ``.future`` attribute that returns a new property.  This
property accesses the "future" version of the todo cell's value.

Next, we define a modifier method, ``add()``.  This method accesses the
``to_add`` attribute, and gets the *future* value of the ``items`` attribute.
This future value is initially created by calling the "todo" cell's function.
In this case, the todo function returns an empty list, so that's what ``add()``
sees, and adds a value to it.

(Note, by the way, that you cannot access future values except from inside a
``@modifier`` function, which in turn is called from either a rule or from
non-Trellis code.)

In our second example above, we create another ``@modifier`` that adds more
than one item to the ``to_add`` attribute.  This works because only a single
"future value" is created during a given recalculation sweep, and ``@modifier``
methods guarantee that no new sweeps can occur while they are running.  Thus,
the changes made in the modifier don't take effect until it returns.

Finally, after each change, the queue resets itself to empty, because the
default value of the ``items`` cell is the empty list created when the cell
was initialized.

Of course, since "todo" attributes are discrete (i.e., transient), what we've
seen so far isn't enough to create a data structure that actually *keeps* any
data around.  To do that, we need to combine "todo" attributes with a rule to
update an existing data structure::

    >>> class Queue2(Queue):
    ...     added = trellis.todo(lambda self: [])
    ...     to_add = added.future
    ...
    ...     @trellis.rule
    ...     def items(self):
    ...         items = self.items
    ...         if items is None:
    ...             items = []
    ...         if self.added:
    ...             return items + self.added
    ...         return items

    >>> q = Queue2()
    >>> view.model = q
    []

    >>> q.add(1)
    [1]

    >>> add_many(2, 3, 4)
    [1, 2, 3, 4]

This version is very similar to the first version, but it separates ``added``
from ``items``, and the ``items`` rule is set up to compute a new value that
includes the added items.

Notice, by the way, that the ``items`` rule returns a new list every time there
is a change.  If it didn't, the updates wouldn't be tracked::

    >>> class Queue3(Queue2):
    ...     @trellis.rule
    ...     def items(self):
    ...         items = self.items
    ...         if items is None:
    ...             items = []
    ...         if self.added:
    ...             items.extend(self.added)
    ...         return items

    >>> q = Queue3()
    >>> view.model = q
    []

    >>> q.add(1)

    >>> add_many(2, 3, 4)

Why are no updates displayed here?  Because ``items`` is being modified
in-place, and when the trellis compares the "before" and "after" versions of
its value, it concludes they are the *same*.  This didn't happen when we
returned a new list, because the old list still had its old contents, and the
new list was different.

If you are modifying a return value in place like this, you should use the
the ``trellis.mark_dirty()`` API to flag that your return value has changed,
even though it's the same object.  In addition, you should log an undo action
so that if the trellis needs to roll back some calculations involving your data
structure, it can do so::

    >>> class Queue4(Queue2):
    ...     @trellis.rule
    ...     def items(self):
    ...         items = self.items
    ...         if items is None:
    ...             items = []
    ...         if self.added:
    ...             trellis.on_undo(items.__delitem__, slice(len(items),None))
    ...             items.extend(self.added)
    ...             trellis.mark_dirty()
    ...         return items

    >>> q = Queue4()
    >>> view.model = q
    []

    >>> q.add(1)
    [1]

    >>> add_many(2, 3, 4)
    [1, 2, 3, 4]

As you can see, calling ``mark_dirty()`` caused the trellis to notice the
change to the list, even though the newly-returned list is (by definition)
still equal to the previous value of the rule (i.e., the same list).

The ``on_undo()`` function lets you register a callback function (with optional
positional arguments) that will be invoked if the trellis needs to roll back
changes due to an error, or due to an out-of-order calculation.  (If a rule
makes a change to a data structure that has already been read by another rule,
the trellis has to undo any changes made by the earlier rule and re-run it to
ensure consistent results.)

Registered functions are called in reverse order, so that callbacks registered
by later ``on_undo()`` calls will run before earlier ones.  The Trellis keeps
track of what callbacks were registered during each rule's execution, so that
it can roll back the minimum number of changes needed to resolve a calculation
order conflict.  In the event of an error, however, all changes are rolled
back::

    >>> @trellis.modifier
    ... def error_demo():
    ...     @trellis.ObserverCell   # make a cell w/out an attribute
    ...     def bad_observer():
    ...         print q
    ...         raise RuntimeError("ha!")
    ...     q.add(5)

    >>> try: error_demo()
    ... except RuntimeError: print "caught error"
    [1, 2, 3, 4, 5]
    caught error

    >>> print q
    [1, 2, 3, 4]

This example is a bit odd, because it's somewhat difficult to force the trellis
to get an error in such a way as to test your undo logging.  If we had simply
raised an error in the modifier, the change would *appear* to have been rolled
back, when in fact it hadn't happened yet!  (It's easy to see this if you add
a "print" to the ``items`` rule -- if you raise an error in the modifier, it
will never be called, because the rules don't run until the modifier is over.)

So to actually test the undo-ing, we have to raise the error in a new observer
cell, which then runs after ``q.items`` is updated. (Observers don't run
until/unless there are no normal rules pending.)

In later sections on `Working with Cell Objects`_, we'll see more about how to
create and use one-off cells like this ``ObserverCell``, without needing to
make them part of a component.

In the meantime, please note that creating good trellis data structures can be
tricky: be sure to write automated tests for your code, and verify that they
actually test what you *think* they test.  This is one situation where it's
REALLY a good idea to write your tests first, and try to make them fail
*before* you add any ``mark_dirty()`` or ``on_undo()`` calls to your code.
Otherwise, you won't be sure that your tests are really testing anything!

Of course, you don't need to deal with ``mark_dirty()`` and ``undo()`` at all,
if you stick to using immutable values as a basis for your data structure, or
use a copy-on-write approach like that shown in our ``Queue2`` example above.
Such data structures are less efficient than updating in-place, if they contain
large amounts of data, but not every data structure needs to contain large
quantities of data!  We suggest that you start with simpler data structures
first, and only add in-place updates if and when you can prove that the data
copying is unacceptable overhead, since such updates are harder to write
in a provably-correct way.  (Note, too, that Python's built-in data types can
often copy data a lot faster than you'd expect...)


Other Things You Can Do With A Trellis
======================================

XXX This section isn't written yet and should include examples

* MVC/Live UI Updates
* Testable UI Models
* Live Object Validation
* Persistence/ORM
* Async I/O
* Process Monitoring
* Live Business Statistics



---------------------------------
Advanced Features and API Details
---------------------------------


Working With Cell Objects
=========================

Throughout the main tutorial, we worked only with component attributes.  But
it's also possible to work directly with ``Cell`` objects.  For example, here's
a temperature converter implemented directly with cells::

    >>> F = trellis.Cell(lambda: C.value * 1.8 + 32, 32)
    >>> C = trellis.Cell(lambda: (F.value - 32)/1.8, 0)

    >>> F.value
    32.0
    >>> C.value
    0.0
    >>> F.value = 212
    >>> C.value
    100.0

The ``trellis.Cell()`` constructor takes three arguments: a zero-argument
callable (or ``None``), an optional value, and an optional "discrete" flag.
In our example above, we created a pair of cells with both rules and values,
that are not discrete.

Notice, by the way, that when you are directly creating cells, you must use
zero-argument callables.  That is, Cell objects don't pass in a "self" argument
to their rules.  (The reason rules in a component use a "self" is that those
rules are turned into methods before the cell is created.  The Cell doesn't
pass in a "self", but it's already bound to the method, so it shows up anyway.)

The ``value`` attribute of a ``Cell`` can be read or set, to get or change the
value of the cell, and it works just like getting or setting a component cell
attribute (except that setting a cell's value to another cell doesn't cause the
cell to be replaced!).  In addition to the ``.value`` attribute, there are also
``get_value()`` and ``set_value()`` methods::

    >>> C.set_value(-40)

    >>> F.get_value()
    -40.0

These can be useful if you need to register callbacks with other systems.  For
example, you could use a cell's ``set_value()`` method as a callback for a
Twisted "deferred" object, so that the cell would receive the deferred's value
when it became available.

Here's our earlier "noise filter" example, reconstituted as a set of cells::

    >>> value = trellis.Cell(value=0)
    >>> threshhold = trellis.Cell(value=5)
    >>> def filtered():
    ...     if abs(value.value - filtered.value) > threshhold.value:
    ...         return value.value
    ...     return filtered.value

    >>> filtered = trellis.Cell(filtered, 0)

    >>> filtered.value
    0
    >>> value.value = 1
    >>> filtered.value
    0
    >>> value.value = 6
    >>> filtered.value
    6


Read-Only and Constant Cells
----------------------------

As you can see, you can provide either a value only, or a rule and a value when
you create a cell.  However, if you provide just a rule and no value, you end
up with a read-only cell whose value can't be set::

    >>> roc = trellis.Cell(lambda: 123)

    >>> roc.value = 456
    Traceback (most recent call last):
      ...
    AttributeError: can't set attribute

In fact, it's not even a ``Cell`` instance, but of a different type
altogether::

    >>> roc
    ReadOnlyCell(<function <lambda> at ...>, None [uninitialized])

What the above means is that you have a read-only cell whose current value is
``None``, but has not yet been initialized.  This means that if you actually
try to *read* the value of this cell, it may or may not match what the
``repr()`` showed.  (This is because simply looking at the cell shouldn't
cause the cell's value to be calculated; that could be very painful when
debugging).

If we actually read the value of this cell, the rule will be run::

    >>> roc.value
    123

But since the rule doesn't depend on any other cells, the cell changes type
again, to a ``Constant``::

    >>> roc
    Constant(123)

Since the rule didn't depend on any other cells, there is never any way that
it could be meaningfully recalculated.  Thus, it becomes constant, and cannot
be listened-to by any other rules.  If we create another rule that reads this
cell, it will not end up depending on it::

    >>> cell2 = trellis.Cell(lambda: roc.value)
    >>> cell2.value
    123

    >>> cell2
    Constant(123)

Thus, constant values propagate automatically through the cell network,
eliminating dependencies on things that can't possibly change.  Of course, if a
read-only cell depends on a cell that *can* change, it remains a read-only
cell, and will be recalculated whenever its dependencies change::

    >>> c1 = trellis.Cell(value=0)
    >>> c2 = trellis.Cell(lambda: c1.value * 2)

    >>> c2.value
    0
    >>> c1.value = 27
    >>> c2
    ReadOnlyCell(<function <lambda>...>, 54)

Note that you can take advantage of constant propagation by explicitly setting
a component attribute to a ``trellis.Constant`` at creation time.  For example,
if for some reason you wanted a temperature converter that could only be used
once::

    >>> tc = TempConverter(C=trellis.Constant(100))
    Celsius...... 100
    Fahrenheit... 212.0

    >>> tc.C = -40
    Traceback (most recent call last):
      ...
    AttributeError: Constants can't be changed

(This would probably be more useful with something like the ``NoiseFilter``
example, in that you could set its ``threshhold`` to a ``Constant()``,
eliminating the need for the ``filtered`` rule to check for changes to the
``threshhold`` in order to know if it should be recalculated.)


Working With A Component's Cells
--------------------------------

As we saw in the main tutorial, the ``trellis.Cells()`` API returns a
dictionary of active cells for a component::

    >>> trellis.Cells(view)
    {'model': Value([1, 2, 3, 4]),
     'view_it': ObserverCell(<bound method Viewer.view_it of
                             <Viewer object at 0x...>>, None)}

In the case of a ``Component``, this data is also stored in the component's
``__cells__`` attribute::

    >>> trellis.Cells(view) is view.__cells__
    True

This makes it possible for you to set up direct links between components using
shared cells.  It also lets you access cell objects directly, in order to e.g.
register their ``set_value()`` methods as callbacks for other systems.


Discrete and Observer Cells
---------------------------

To make a cell "discrete" (i.e. a receiver or discrete rule), you set its
third constructor argument (i.e., ``discrete``) to true::

    >>> aReceiver = trellis.Cell(value=0, discrete=True)
    >>> aReceiver.value
    0

    >>> v = Viewer(model = aReceiver)
    0
    >>> aReceiver.value = 42
    42
    0

As you can see, the value a discrete cell is created with, is the default value
it resets to between received (or calculated) values.  If you want to make
a discrete rule, just include a rule in addition to the default value and the
discrete flag.

"Observer" cells are implemented with the ``trellis.ObserverCell`` class::

    >>> trellis.Cells(view)['view_it']
    ObserverCell(<bound method Viewer.view_it of
               <Viewer object at 0x...>>, None)

The ObserverCell constructor takes only one parameter: a zero-argument callable,
such as a bound method or a function with no parameters.  You can't set a value
for an ``ObserverCell`` (because it's not writable), nor can you make it discrete
(since that would imply a readable value, and observer cells exist only for
their side-effects).  Creating an observer cell schedules it for execution, as
soon as the current modifier is complete and any normal rules are finished.  It
will then be re-executed in the future, after any cells or other trellis-
managed data structures it depended on are changed.  (As long as the
ObserverCell isn't garbage collected, of course.)


Cell Attribute Metadata
-----------------------

The various decorators and APIs that set up cell attributes in components all
work by registering metadata for the enclosing class.  This metadata can be
accessed using various ``peak.util.roles.Registry`` objects.  (See the
documentation of the ``ObjectRoles`` package at the Python Package Index for
more info on registries.)

In the current version of the Trellis library, these registries should mostly
be considered implementation details; they are not officially documented and
may change in a future release.  However, if you need to be able to access a
superclass' definition of a rule, you can do so using the ``CellRules``
registry::

    >>> trellis.CellRules(NoiseFilter)
    {'filtered': <function filtered at 0x...>}

As you can see, calling ``trellis.CellRules(sometype)`` will return you a
dictionary of rules for that type.  You can then pull out the definition you
need and call it.  This particular registry should be a relatively stable API
across releases.


Garbage Collection
==================

Cells keep strong references to all of the cells whose values they accessed
during rule calculation, and weak references to all of the cells that accessed
them.  This ensures that as long as a listener exists, its most-recently
read subject(s) will also continue to exist.

Cells whose rules are effectively methods (i.e., cells that represent component
attributes) also keep a strong reference to the object that owns them, by
way of the method's ``im_self`` attribute.  This means that as long as some
attribute of a component is being observed, the whole component will continue
to exist.

In addition, a component's ``__cells__`` dictionary keeps a reference to all
its cells, creating a reference cycle between the cells and the component.
Thus, ``Component`` instances can only be reclaimed by Python's cycle collector,
and are not destroyed as soon as they go out of scope.  You should therefore
avoid giving Component objects a ``__del__`` method, and should explicitly
dispose of any resources that you want to reclaim early.

You should NOT, however, attempt to break the cycle between a component and its
cells.  If the cells have any observers, this will just cause the rules to
break upon recalculation, or else recreate some of the cells, depending on how
you tried to break the cycle.  It's better to simply let Python detect the
cycle and get rid of it itself.

However, if you absolutely MUST mess with this, the best thing to do is delete
the component's ``__cells__`` attribute with ``del ob.__cells__``, as this will
ensure that any dangling observers will at least get attribute errors when
recalculation occurs.  Thus, if the component is really still in use, at least
you'll get an error message, instead of weird results.  But it still won't be a
fun problem to debug, so it's highly recommended that you leave the garbage
collection to Python.  Python always knows more about what's happening in your
program than you do!


------------------------
Additional Documentation
------------------------

There's a lot more to the Trellis package than what's in this brief guide and
tutorial.  Here are some links to other documentation provided with the
package:

`Time, Event Loops, and Tasks`_ (``Activity.txt`` in the source distribution)
    This manual explains how to create generator-based pseudo-threads, schedule
    activities for idle moments, integrate the Trellis with other event loops
    (e.g. Twisted and wxPython), and implement things like timeouts, delays,
    alarms, etc. in Trellis rules.


`Event-Driven Collections with the Trellis`_ (``Collections.txt`` in the source)
    This document provides a brief overview of some additional Trellis data
    structures provided by the package, such as the ``SortedSet`` type.

`Software Transactional Memory (STM) And Observers`_ (aka ``STM-Observer.txt``)
    This document shows how some of the underlying Trellis pieces work, and
    in future revisions, it'll include some hints on how to create your own
    custom cell types, etc.


----------
Appendices
----------

The "Trellis" Name
==================

The "Trellis" name comes from Dr. David Gelernter's 1991 book, "Mirror Worlds",
where he describes a parallel programming architecture he called "The Trellis".
In the excerpted passages below, he describes the portions of his architecture
that are roughly the same as in this Python implementation:

    "Consider an upward-stretching network of infomachines tethered together,
    rung-upon-rung (billowing slightly in the breeze?)  No two rungs need have
    exactly the same number of machines....  There might be ten rungs in all or
    hundreds or thousands, and the average rung might have anywhere from a
    handful to hundreds of members.  This architecture spans a huge range of
    shapes and sizes....

    So, these things are "tethered together" -- meaning?  Those lines are
    *lines of communication*.  Each member of the Trellis is tethered to some
    lower-down machines and to some higher-ups....  A machine deals *only* with
    the machines to which it is tethered.  So far as it's concerned, the rest
    don't exist.  It deals with inferiors in a certain way and superiors in a
    certain other way, and that's it....

    Information rushes upward through the network, and the machines on each
    rung respond to it on their own terms....  Each machine focuses on one
    piece of the problem -- on answering a single question about the thing out
    there...that is being monitored.  Each machine's entire and continuous
    effort is thrown into answering its one question.  You can query a machine
    at any time -- what's the current best answer to your particular question?
    -- and it will produce an up-to-the-second response....

    So data flows upward through the ensemble; there's also a reverse, downward
    flow of what you might call "anti-data" -- *inquiries* about what's going
    on.  A high ranking element might attempt to generate a new value, only to
    discover it's missing some key datum from an inferior.  It sends a query
    downward....  The inferior tries to come up with some new data....  If a
    bottom-level machine is missing data,.... It can ask the outside world
    directly for information....

    The fact that data flows up and anti-data flows downwards means that, in a
    certain sense, a Trellis can run either forwards or backwards, or both at
    the same time....

    A Trellis, it turns out, is a lot like a crystal....  When you turn it on,
    it vibrates at a certain frequency.

    Meaning?  In concept, each Trellis element is an infomachine.  All these
    infomachines run separately and simultaneously.

    In practice, we do things somewhat differently....

    We run the Trellis in a series of sweeps.  During the first sweep, each
    machine gets a chance to [produce one output value].  During the second,
    each [produces a second value], and so on.  No machine [produces] a
    second [value] until every [machine] has [produced] a *first* [value]."

While Dr. Gelernter's Trellis was designed to be run by an arbitary number of
parallel processors, our Trellis is scaled down to run in a single Python
thread.  But on the plus side, our Trellis automatically connects its "tethers"
as it goes, so we don't have to explicitly plot out an entire network of
dependencies, either!


The Implementation
==================

Ken Tilton's "Cells" library for Common Lisp inspired the implementation of
the Trellis.  While Tilton had never heard of Gelernter's Trellis, he
independently discovered the value of having synchronous updates, like the
"sweeps" of Gelernter's design, and combined them with automatic dependency
detection to create his "Cells" library.

I heard about this library only because Google sponsored a "Summer of Code"
project to port Cells to Python - a project that produced the PyCells
implementation.  My implementation, however, is not a port but a re-visioning
based on native Python idioms and extended to handle mutually recursive rules,
side-effects, rollback, and various other features that do not precisely map
onto the features of Cells, PyCells, or other Python frameworks inspired by
Cells (such as "Cellulose").

While the first very rough drafts of this package were done in 2006 on my own
time, virtually all of the work since has been generously funded by OSAF, the
Open Source Applications Foundation.


Roadmap
=======

Open Issues
  * Debugging code that does modifications can be difficult because it can be
    hard to know which cells are which.  There should be a way to give cells
    an identifier, so you know what you're looking at.

  * Currently, there's no protection against accessing Cells from other
    threads, nor support for having different logical tasks in the same thread
    with their own contexts, services, etc.  This should be fixed by using
    the "Contextual" library to manage thread-local (and task-local) state for
    the Trellis, and by switching to the appropriate ``context.State`` whenever
    non-rule/non-modifier code tries to read or write a cell.

  * There should probably be an easier way to reference cells directly, instead
    of using Cells(ob)['name'] -- perhaps a ``.link`` property, similar to the
    ``.future`` of "todo" cells, would make this easier.

  * The ``poll()`` and ``repeat()`` functions are undocumented in this release.

TrellisDB
  * A system for processing relational-like records and "active queries" mapped
    from zero or more backend storage mechanism.

TrellisUI
  * Framework for mapping application components to UI views.

  * Widget specification, styling, and layout system that's backend-agnostic,
    ala Adobe's "Eve2" layout constraint system.  Should be equally capable of
    spitting out text-mode drawings of a UI, as it is of managing complex wx
    "GridBagSizer" layouts.

TrellisIO
  * IO events

  * Cross-thread bridge cells

  * signal() events


