===================================================================
Event-Driven Programming The Easy Way, with ``peak.events.trellis``
===================================================================

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
    ...     @trellis.rule
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
``trellis.value``.  Here's an example that uses all of these approaches, simply
for the sake of illustration::

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
    ...         right  = lambda self: self.left + self.width,
    ...     )
    ...
    ...     @trellis.rule
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
does only three things, all in its ``__init__`` method, and you are free to
accomplish these things some other way (e.g. in your own ``__init__`` method)
if you need or want to:

1. It sets ``self.__cells__ = trellis.Cells(self)``.  This creates a special
   dictionary that will hold all the ``Cell`` objects used to implement cell
   attributes.

2. It takes any keyword arguments it receives, and uses them to initialize any
   named attributes.  (Note that you don't have to do this, but it often comes
   in handy.)

3. It does a getattr() on each of the object's non-optional cell attributes,
   in order to initialize their rules and set up their dependencies.  We'll
   cover this in detail in the next section, `Automatic Activation and
   Dependencies`_.

In addition to doing these things another way, you can also use ``Cell``
objects directly, without any ``Component`` classes.  This is discussed more
in the section below on `Working With Cell Objects`_.


Automatic Activation and Dependencies
-------------------------------------

You'll notice that each time we change an attribute value, our Rectangle
instance above prints itself -- including when the instance is first created.
That's because of two important Trellis principles:

1. When a ``Component`` instance is created, all its "non-optional" cell
   attributes are calculated at the end of ``Component.__init__()``.  That is,
   if they have a rule, it gets invoked, and the result is used to determine
   the cell's initial value.

2. While a cell's rule is running, *any* trellis Cell that is looked at becomes
   a dependency of that rule.  If the looked-at cell changes later, it triggers
   recalculation of the rule that looked.  In Trellis terms, we say that the
   first cell has become an "observer" of the second cell.

The first of these principles explains why the rectangle printed itself
immediately: the ``show`` rule was calculated.  We can see this if we look
at the rectangle's ``show`` attribute::

    >>> print r.show
    None

(The ``show`` rule didn't return a specific value, so the resulting attribute
value is ``None``.  Also notice that *rules are not methods* -- they are more
like properties.)

The second principle explains why the rectangle re-prints itself any time one
of the attributes changes value: all six attributes are referenced by the
``__repr__`` method, which is called when the ``show`` rule prints the
rectangle.  Since the cells that store those attributes are being looked at
during the execution of another cell's rule, they become dependencies, and the
``show`` rule is thus recalculated whenever the observed cells change.

Each time a rule runs, its dependencies are automatically re-calculated --
which means that if you have more complex rules, they can actually depend on
different cells every time they're calculated.  That way, the rule is only
recalculated when it's absolutely necessary.

By the way, an observed cell has to actually *change* its value (as determined
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

Even though we can override the initial value when the component is created,
or any time before it is first read::

    >>> d = Demo(aDict={3:4})
    >>> d.aDict
    {3: 4}

However, since this rule is not an "optional" rule, the ``Component.__init__``
method will read it, meaning that the only chance we get to override it is
via the keyword arguments.  In the next section, we'll look at how to create
"optional" rules: ones that don't get calculated the moment a component is
created.


"Optional" Rules and Subclassing
--------------------------------

The ``show`` rule we've been playing with on our ``Rectangle`` class is kind of
handy for debugging, but it's kind of annoying when you don't need it.  Let's
turn it into an "optional" rule, so that it won't run unless we ask it to::

    >>> class QuietRectangle(Rectangle):
    ...     @trellis.optional
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
    ...     @trellis.rule
    ...     def view_it(self):
    ...         if self.model is not None:
    ...             print self.model

    >>> view = Viewer(model=q2)
    Rectangle((0, 99), (20, 30), (20, 129))

Now, any time we change q2, it will be printed by our ``q2_view`` rule, even
though we haven't activated q2's ``show`` rule::

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

Remember: once a rule observes another cell, it will be recalculated whenever
the observed value changes.  Each time ``view_it`` is recalculated, it renews
its dependency on ``self.model``, but *also* acquires new dependencies on
whatever the ``repr()`` of ``self.model`` looks at.  Meanwhile, any
dependencies on the attributes of the *previous* ``self.model`` are dropped,
so changing them doesn't cause the rule to be recalculated any more.  This
means we can even do things like set ``model`` to a non-component object, like
this::

    >>> view.model = {}
    {}

But since dictionaries don't use any cells, changing the dictionary won't do
anything:

    >>> view.model[1] = 2

To be able to observe mutable data structures, you need to use data types like
``trellis.Dict`` and ``trellis.List`` instead of the built-in Python types.
We'll cover how that works in the section below on `Sets, Lists, and Dicts`_.

By the way, the links from a cell to its observers are defined using weak
references.  This means that views (and cells or components in general) can
be garbage collected even if they have dependencies.  For more information
about how Trellis objects are garbage collected, see the later section on
`Garbage Collection`_.


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

Thus, as long as a cell's rule doesn't raise an uncaught exception, there is no
way for it to become "corrupt" or "out of sync" with the rest of the program.
This is a form of something called "referential transparency", which roughly
means "order independent".  We'll cover this topic in more detail in the later
section on `Managing State Changes`_.  But in the meantime, let's look at how
using receivers instead of methods also helps us implement generic controllers.


Creating Generic Controllers by Sharing Cells
---------------------------------------------

Let's create a couple of generic "Spinner" controller, that take a pair of
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
give it a value cell for the text in its class::

    >>> class TextEditor(trellis.Component):
    ...     text = trellis.value('')
    ...
    ...     @trellis.rule
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
messages, or commands.  But what if you want to *generate* them, instead?

Normal rules return what might be called "continuous" or "steady state" values.
That is, their value remains the same until something causes them to be
recalculated.

But "discrete" rules are different.  Just like receivers, their value is
automatically reset to a default value as soon as all their observers have
"seen" the value.  Let's look at an example.

Suppose you're writing some code that receives data from a socket, and you want
to issue an event for each line of text that's been received over the socket.
We can make a ``LineReceiver`` component that receives blocks of bytes, and
emits lines one by one::

    >>> class LineReceiver(trellis.Component):
    ...     bytes = trellis.receiver('')
    ...     delimiter = trellis.value('\r\n')
    ...     _buffer = ''
    ...
    ...     @trellis.discrete
    ...     def line(self):
    ...         buffer = self._buffer = self._buffer + self.bytes
    ...         lines = buffer.split(self.delimiter, 1)
    ...         self._buffer = lines.pop()
    ...         if lines:
    ...             trellis.repeat()    # flag this rule for recalculation
    ...             return lines[0]
    ...
    ...     @trellis.rule
    ...     def show(self):
    ...         if self.line is not None:
    ...             print "Line:", self.line

The ``@trellis.discrete`` decorator creates a discrete rule cell.  By default,
it will reset to ``None`` after each calculation of a non-``None`` value.
However, you can change this default value by defining a ``trellis.value()``
for the same attribute.

For example, we could have included a statement like ``trellis.values(line='')``
in the ``LineReceiver`` class, to make the default value an empty string
instead of ``None``.  Of course, if we did that, we'd also have to make the
``line`` method return an empty string instead of implicitly returning ``None``
when there is no line to emit.  But we don't want to do all that because we
need to be able to receive *empty lines* from the socket.

Thus, the default value for a discrete rule (or a receiver, for that matter),
should always be something that can't possibly be a valid event or message.
That way, rules reading the value can't mistake the default value for something
that actually needs to be processed.

Let's take a look at how our ``LineReceiver`` works, as it receives some
bytes::

    >>> lp = LineReceiver()
    >>> lp.bytes = 'xyz'
    >>> lp.bytes = '\r'
    >>> lp.bytes = '\n'
    Line: xyz

As you can see, the line is built up until a delimiter is found.  During that
process, the ``line`` rule keeps returning ``None``, until it finally issues
an actual value, causing the ``show`` rule to recalculate and print the output.
We can also send multiple lines in a single input::

    >>> lp.bytes = "abcdef\r\nghijkl\r\nmnopq"
    Line: abcdef
    Line: ghijkl

Calling ``trellis.repeat()`` forces a rule to be recalculated as soon as the
current recalculation pass is over.  (That is, after all observers have been
updated.)  This enables us to keep producing new values in succession, but it
must be used with caution, since an unconditional ``repeat()`` will produce
an infinite loop.  In this case, we need it because we need to be able to
produce more than two values in a row, e.g.::

    >>> lp.bytes = "FOObarFOObazFOOspam\n"
    >>> lp.delimiter = "FOO"
    Line: mnopq
    Line: bar
    Line: baz

Notice that changing the delimiter caused the leftover ``mnopq`` to be
processed as a FOO-delimited line, because the ``line`` rule depends on
``delimiter``.  Thus, changing the delimiter causes an immediate
re-interpretation of anything that's left in the buffer::

    >>> lp.delimiter = "\n"
    Line: spam

Also notice that even if a discrete rule produces the same value on two
successive recalculations, it is still treated as if its value had changed,
triggering a recalculation of any observers.  Thus, if two lines in a row
have the same value, both still get printed::

    >>> lp.bytes = 'abc\nabc\n'
    Line: abc
    Line: abc

This is a particularly important difference between discrete rules and regular
ones.  Always use a discrete rule when you want to produce values that are
processed indepdendently of any previous value for that rule.  Discrete rules
are also especially appropriate for filtering or transforming events or
commands received from ``receiver`` cells.

By the way, you may not have realized this, but we can create a ``LineReceiver``
that shares its ``bytes`` cell with say, an object like this::

    >>> class StreamReceiver(trellis.Component):
    ...     trellis.values(
    ...         socket = None,
    ...         buffer_size = 512,
    ...         bytes = '',
    ...     )
    ...     @trellis.discrete
    ...     def bytes(self):
    ...         trellis.poll()  # repeat this rule if anybody asks about it
    ...         return self.socket.recv(self.buffer_size)

Notice that here we define a default value of ``''`` for the ``bytes``
rule, so that repeatedly receiving zero bytes doesn't trigger any observers to
recalculate.  We also see here the use of another trellis API, ``poll()``,
which marks the rule to be recalculated if an observer asks for its value.
(``poll()`` and ``repeat()`` are both covered in more detail in the section
below on `Recalculation and Dependency Management`_.)

This isn't really the best way to repeatedly read a socket, of course.  You're
better off using an async I/O library like Twisted and registering a callback
to set the ``bytes`` receiver for you.  But it serves well enough to illustrate
the basic idea of chaining discrete rules.  With our ``StreamReceiver``, we can
then do something like this::

    stream = StreamReceiver(socket = aNonBlockingSocket)
    lines = LineReceiver(bytes = trellis.Cells(stream)['bytes'])

In order to create a line receiver that gets its bytes from a socket.  However,
unlike Twisted deferreds (which pass a value to only one recipient at a time),
a shared receiver setup like this lets you have multiple rules "reading" from
the same stream at the same time.


Managing State Changes
======================




Sets, Lists, and Dicts
----------------------

Set, List, Dict



InputConflict

modifier(method)
    Mark a method as performing modifications to Trellis data

@todo/todo(func), todos(**attrs)
    Define one or more todo-cell attributes, that can send "messages to the
    future"

.future


Things To Do With A Trellis
===========================

MVC/Live UI Updates
Testable UI Models
Live Object Validation
Persistence/ORM
Async I/O
Process Monitoring
Live Business Statistics


Connecting to Other Systems
===========================




---------------------------------
Advanced Features and API Details
---------------------------------


Working With Cell Objects
=========================

* no value makes a read-only cell

* read-only cells become constant

__cells__ attribute

Cell, Constant

.link

.value

.get_value()

.set_value(value)


Recalculation and Dependency Management
=======================================

modifier(method)
    Mark a method as performing modifications to Trellis data

poll()
    Recalculate this rule the next time *any* other cell is set

repeat()
    Schedule the current rule to be run again, repeatedly

without_observer(func, *args, **kw)
    Run func(*args, **kw) without making the current rule depend on it

.ensure_recalculation()
    Ensure that this cell's rule will be (re)calculated


Co-operative Multitasking
=========================

@task, Pause, Value, resume(), TaskCell


Cell Metadata
=============


Garbage Collection
==================



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
the Trellis.  While Tilton had never heard of Gelernter's Trellis, he did
come to see the value of having synchronous updates, like the "sweeps" of
Gelernter's design, and combined them with automatic dependency detection to
create his "Cells" library.

I heard about this library only because Google sponsored a "Summer of Code"
project to port Cells to Python - a project that produced the PyCells
implementation.  My implementation, however, is not a port but a re-visioning
based on native Python idioms and extended to handle mutually recursive rules,
and various other features that do not precisely map onto the features of
Cells, PyCells, or other Python frameworks inspired by Cells (such as
"Cellulose").

While the first very rough drafts of this package were done in 2006 on my own
time, virtually all of the work since has been generously funded by OSAF, the
Open Source Applications Foundation.


Todo/Ideas
==========

Trellis
  * .has_listeners(), .has_dependencies()

TrellisIO
  * Time service & timestamp rules

  * IO events

  * Cross-thread bridge cells

  * signal() events

