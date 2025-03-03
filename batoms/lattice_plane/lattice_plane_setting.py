"""

Lattice Planes

To insert lattice planes in structural models.
"""
import bpy
from batoms.base.collection import Setting, tuple2string
import numpy as np
from time import time


class LatticePlaneSettings(Setting):
    """
    PlaneSetting object

    The PlaneSetting object store the polyhedra information.

    Parameters:

    label: str
        The label define the batoms object that a Setting belong to.

    """

    def __init__(self, label, parent = None, plane=None) -> None:
        Setting.__init__(self, label, coll_name='%s_plane' % label)
        self.name = 'blatticeplane'
        self.parent = parent
        if plane is not None:
            for key, data in plane.items():
                self[key] = data

    @property
    def no(self, ):
        return self.parent.batoms.get_spacegroup_number()

    @no.setter
    def no(self, no):
        self.no = no

    def __setitem__(self, index, setdict):
        """
        Set properties
        """
        name = tuple2string(index)
        p = self.find(name)
        if p is None:
            p = self.collection.add()
        p.indices = index
        p.name = name
        p.flag = True
        for key, value in setdict.items():
            setattr(p, key, value)
        p.label = self.label

    def add(self, indices):
        self[indices] = {'indices': indices}

    def __repr__(self) -> str:
        s = "-"*60 + "\n"
        s = "Indices   distance  slicing   boundary\n"
        for p in self.collection:
            s += "{0:10s}   {1:1.3f}   ".format(p.name, p.distance)
            s += "{:10s}  {:10s}  \n".format(
                str(p.slicing),  str(p.boundary))
        s += "-"*60 + "\n"
        return s

    