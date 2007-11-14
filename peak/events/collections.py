import trellis, bisect
from peak.util import decorators
from trellis import set
from new import instancemethod

__all__ = [
    'SortedSet', 'SubSet', 'Observing',
]

class SubSet(trellis.Set):
    """Set that's constrained to be a subset of another set"""

    trellis.values(
        base = None
    )
    trellis.rules(
        base = lambda self: trellis.Set()
    )

    decorators.decorate(trellis.rule)
    def added(self):
        base = self.base
        return set([item for item in self._added if item in base])

    decorators.decorate(trellis.rule)
    def removed(self):
        base = self.base
        if self.base.removed:
            # XXX need to filter this by self._data somehow
            return set(self._removed) | set(self.base.removed)
        else:
            return self._removed









class Observing(trellis.Component):
    """Monitor a set of keys for changes"""

    trellis.values(
        lookup_func = lambda x:x,
        changes = {},
        watched_values = ({}, {}),
        _watching = None
    )

    keys = trellis.rule(lambda self: trellis.Set())

    decorators.decorate(trellis.rule)
    def _watching(self):
        cells = self._watching or {}
        for k in self.keys.removed:
            if k in cells:
                del cells[k]
                trellis.dirty()
        lookup = self.lookup_func
        for k in self.keys.added:
            cells[k] = trellis.Cell(instancemethod(lookup, k, type(k)))
            trellis.dirty()
        return cells

    decorators.decorate(trellis.rule)
    def watched_values(self):
        forget, old = self.watched_values
        lookup = self.lookup_func
        return old, dict([(k, v.value) for k,v in self._watching.iteritems()])
        
    decorators.decorate(trellis.discrete)
    def changes(self):
        old, current = self.watched_values
        changes = {}
        if old!=current:
            for k,v in current.iteritems():
                if k not in old or v!=old[k]:
                    changes[k] = v, old.get(k, v)
        return changes
        
class SortedSet(trellis.Component):
    """Represent a set as a list sorted by a key"""

    trellis.values(
        data = None,
        state = None,
        sort_key  = lambda x:x,  # sort on the object
        changes = []
    )
    trellis.rules(
        data = lambda self: trellis.Set(),
        items = lambda self: self.state[0],
    )

    changes = trellis.discrete(lambda self: self.state[2])

    def __getitem__(self, key):
        return self.items[int(key)][1]

    def __len__(self):
        return len(self.items)

    decorators.decorate(trellis.rule)
    def state(self):
        if self.state is None:
            items, old_key, old_change = None, None, []
        else:
            items, old_key, old_change = self.state # XXX needs .data too!

        key = self.sort_key
        if key != old_key or items is None: # or self.data is not old_data!
            data = [(key(ob),ob) for ob in self.data]
            data.sort()
            size = len(data)
            return data, key, [(0,size,size)]

        return items, key, self.compute_changes(key, items)

    def __repr__(self):
        return repr([i[1] for i in self.items])

    def compute_changes(self, key, items):
        changes = [
            (key(ob), "+", ob) for ob in self.data.added] + [
            (key(ob), "-", ob) for ob in self.data.removed
        ]
        changes.sort()
        changes.reverse()

        lo = 0
        hi = len(items)
        regions = []

        for k, op, ob in changes:
            ind = (k, ob)
            if lo<hi and items[hi-1][0]>=ind:
                pos = hi-1    # shortcut
            else:
                pos = bisect.bisect_left(items, ind, lo, hi)

            if op=='-':
                del items[pos]
                if regions and regions[-1][0]==pos+1:
                    regions[-1] = (pos, regions[-1][1], regions[-1][2])
                else:
                    regions.append((pos, pos+1, 0))
            else:
                items.insert(pos, ind)
                if regions and regions[-1][0]==pos:
                    regions[-1] = (pos, regions[-1][1], regions[-1][2]+1)
                else:
                    regions.append((pos, pos, 1))
            hi=pos
                
        return regions







