from sqlalchemy.orm.attributes import get_attribute,set_attribute,ClassManager
from trellis import Cells, Effector, NO_VALUE, CellValues, CellFactories
from trellis import ObserverCell
from new import instancemethod

class SAInstrument(ClassManager):
    """Adapter for SQLAlchemy to talk to Trellis components"""

    def install_descriptor(self, key, inst):
        if key not in CellFactories(self.class_):
            setattr(self.class_, key, inst)

    def uninstall_descriptor(self, key):
        if key not in CellFactories(self.class_):
            delattr(self.class_, key)

    def install_state(self, instance, state):
        cells = Cells(instance)
        if not cells:
            cls = instance.__class__
            get_value = CellValues(cls).get
            factories = CellFactories(cls)
            getter = instancemethod(get_attribute, instance)
            attrs = []
            for attr in self:
                if attr not in factories:
                    continue
                attrs.append(attr)
                cells[attr] = Effector(
                    instancemethod(getter, attr), get_value(attr, NO_VALUE),
                )
            def setter():
                for attr in attrs:
                    if cells[attr].was_set:
                        set_attribute(instance, attr, cells[attr].value)
            instance._observer = ObserverCell(setter)
        super(SAInstrument, self).install_state(instance, state)
    

