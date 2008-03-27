from sqlalchemy.orm.attributes import get_attribute,set_attribute,ClassManager
from trellis import Cells, Effector, NO_VALUE, CellValues, CellFactories
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
            setter = instancemethod(set_attribute, instance)
            for attr in self:
                if attr not in factories:
                    continue
                cells.setdefault(attr, Effector(
                    instancemethod(getter, attr), get_value(attr, NO_VALUE),
                    writer = instancemethod(setter, attr)
                ))
        super(SAInstrument, self).install_state(instance, state)
    

