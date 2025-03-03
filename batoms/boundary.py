"""
# TODO add locaiton in geometry node
"""
from time import time

import bpy
import numpy as np
from ase.geometry import complete_cell

from batoms.base.object import ObjectGN
from batoms.utils import number2String, string2Number
from batoms.utils.butils import compareNodeType, object_mode

default_attributes = [
    ['atoms_index', 'INT'],
    ['species_index', 'INT'],
    ['show', 'BOOLEAN'],
    ['select', 'INT'],
    ['model_style', 'INT'],
    ['scale', 'FLOAT'],
    ['radius_style', 'INT'],
]

default_GroupInput = [
    ['atoms_index', 'NodeSocketInt'],
    ['species_index', 'NodeSocketInt'],
    ['show', 'NodeSocketBool'],
    ['select', 'NodeSocketInt'],
    ['model_style', 'NodeSocketInt'],
    ['scale', 'NodeSocketFloat'],
    ['radius_style', 'NodeSocketInt'],
]

default_boundary_datas = {
    'atoms_index': np.ones(0, dtype=int),
    'species_index': np.ones(0, dtype=int),
    'species': np.ones(0, dtype='U4'),
    'positions': np.zeros((0, 3)),
    'scales': np.zeros(0),
    'offsets': np.zeros((0, 3)),
    'model_styles': np.ones(0, dtype=int),
    'shows': np.ones(0, dtype=int),
    'selects': np.ones(0, dtype=int),
}


def search_boundary(atoms,
                    boundary=[[0, 1], [0, 1], [0, 1]],
                    ):
    """Search atoms in the boundary

    Args:
        atoms: _description_
        boundary (list, optional): _description_.
            Defaults to [[0, 1], [0, 1], [0, 1]].

    Returns:
        _type_: _description_
    """
    # tstart = time()
    cell = atoms.cell
    positions = atoms.positions
    species = atoms.arrays['species']
    if isinstance(boundary, float):
        boundary = [[-boundary, 1 + boundary],
                    [-boundary, 1+boundary], [-boundary, 1+boundary]]
    boundary = np.array(boundary)
    # find supercell
    f = np.floor(boundary)
    c = np.ceil(boundary)
    ib = np.array([f[:, 0], c[:, 1]]).astype(int)
    M = np.product(ib[1] - ib[0] + 1)
    positions = np.linalg.solve(complete_cell(cell).T,
                                positions.T).T
    n = len(positions)
    npositions = np.tile(positions, (M - 1,) + (1,)
                         * (len(positions.shape) - 1))
    i0 = 0
    # index
    offsets = np.zeros((M*n, 4), dtype=int)
    ind0 = np.arange(n).reshape(-1, 1)
    species0 = species
    species = []
    # repeat the positions so that
    # it completely covers the boundary
    for m0 in range(ib[0, 0], ib[1, 0] + 1):
        for m1 in range(ib[0, 1], ib[1, 1] + 1):
            for m2 in range(ib[0, 2], ib[1, 2] + 1):
                if m0 == 0 and m1 == 0 and m2 == 0:
                    continue
                i1 = i0 + n
                npositions[i0:i1] += (m0, m1, m2)
                offsets[i0:i1] = np.append(
                    ind0, np.array([[m0, m1, m2]]*n), axis=1)
                species.extend(species0)
                i0 = i1
    # boundary condition
    ind1 = np.where((npositions[:, 0] > boundary[0][0]) &
                    (npositions[:, 0] < boundary[0][1]) &
                    (npositions[:, 1] > boundary[1][0]) &
                    (npositions[:, 1] < boundary[1][1]) &
                    (npositions[:, 2] > boundary[2][0]) &
                    (npositions[:, 2] < boundary[2][1]))[0]
    offsets_b = offsets[ind1]
    # print('search boundary: {0:10.2f} s'.format(time() - tstart))
    return offsets_b


class Boundary(ObjectGN):
    def __init__(self,
                 label=None,
                 boundary=np.array([[-0.0, 1.0], [-0.0, 1.0], [-0.0, 1.0]]),
                 boundary_datas=None,
                 batoms=None,
                 location=(0, 0, 0)
                 ):
        """_summary_

        Args:
            label (str, optional):
                _description_. Defaults to None.
            boundary (list, optional):
                search atoms at the boundary.
                Defaults to np.array([[-0.0, 1.0], [-0.0, 1.0], [-0.0, 1.0]]).
            boundary_datas (_type_, optional):
                _description_. Defaults to None.
            batoms (_type_, optional):
                _description_. Defaults to None.
        """
        #
        self.batoms = batoms
        self.label = label
        name = 'boundary'
        ObjectGN.__init__(self, label, name)
        if boundary_datas is not None:
            if batoms is not None:
                location = batoms.location
            self.build_object(boundary_datas)  # , location=location)
        else:
            self.load(label)
        self.boundary = boundary

    def build_object(self, datas, location=[0, 0, 0], attributes={}):
        """
        build child object and add it to main objects.
        """
        # tstart = time()
        if len(datas['positions'].shape) == 2:
            self._frames = {'positions': np.array([datas['positions']]),
                            'offsets': np.array([datas['offsets']]),
                            }
            positions = datas['positions']
            offsets = datas['offsets']
        elif len(datas['positions'].shape) == 3:
            self._frames = {'positions': datas['positions'],
                            'offsets': datas['offsets'],
                            }
            positions = datas['positions'][0]
            offsets = datas['offsets'][0]
        else:
            raise Exception('Shape of positions is wrong!')
        #
        attributes.update({
            'atoms_index': datas['atoms_index'],
            'species_index': datas['species_index'],
            'show': datas['shows'],
            'model_style': datas['model_styles'],
            'select': datas['selects'],
            'scale': datas['scales'],
        })
        name = '%s_boundary' % self.label
        self.delete_obj(name)
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(positions, [], [])
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        for attribute in default_attributes:
            mesh.attributes.new(
                name=attribute[0], type=attribute[1], domain='POINT')
        self.batoms.coll.objects.link(obj)
        obj.location = location
        obj.parent = self.batoms.obj
        #
        name = '%s_boundary_offset' % self.label
        self.delete_obj(name)
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(offsets, [], [])
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        self.batoms.coll.objects.link(obj)
        obj.hide_set(True)
        obj.parent = self.batoms.obj
        bpy.context.view_layer.update()
        self.set_attributes(attributes)
        self.build_geometry_node()
        self.set_frames(self._frames, only_basis=True)
        # print('boundary: build_object: {0:10.2f} s'.format(time() - tstart))

    def build_geometry_node(self):
        """
        """
        from batoms.utils.butils import get_nodes_by_name
        name = 'GeometryNodes_%s_boundary' % self.label
        modifier = self.obj.modifiers.new(name=name, type='NODES')
        modifier.node_group.name = name
        # ------------------------------------------------------------------
        inputs = modifier.node_group.inputs
        GroupInput = modifier.node_group.nodes[0]
        GroupOutput = modifier.node_group.nodes[1]
        # add new output sockets
        for att in default_GroupInput:
            GroupInput.outputs.new(type=att[1], name=att[0])
            inputs.new(att[1], att[0])
            id = inputs[att[0]].identifier
            modifier['%s_use_attribute' % id] = True
            modifier['%s_attribute_name' % id] = att[0]
        gn = modifier
        # ------------------------------------------------------------------
        JoinGeometry = get_nodes_by_name(gn.node_group.nodes,
                                         '%s_JoinGeometry' % self.label,
                                         'GeometryNodeJoinGeometry')
        gn.node_group.links.new(
            GroupInput.outputs['Geometry'], JoinGeometry.inputs['Geometry'])
        gn.node_group.links.new(
            JoinGeometry.outputs['Geometry'], GroupOutput.inputs['Geometry'])
        # ------------------------------------------------------------------
        # calculate bond vector, length, rotation based on the index
        # Get four positions from batoms, bond and the second bond for
        # high order bond plane
        ObjectBatoms = get_nodes_by_name(gn.node_group.nodes,
                                         '%s_ObjectBatoms' % self.label,
                                         'GeometryNodeObjectInfo')
        ObjectBatoms.inputs['Object'].default_value = self.batoms.obj
        PositionBatoms = get_nodes_by_name(gn.node_group.nodes,
                                           '%s_PositionBatoms' % (self.label),
                                           'GeometryNodeInputPosition')
        TransferBatoms = get_nodes_by_name(gn.node_group.nodes,
                                           '%s_TransferBatoms' % (self.label),
                                           'GeometryNodeAttributeTransfer')
        TransferBatoms.mapping = 'INDEX'
        TransferBatoms.data_type = 'FLOAT_VECTOR'
        gn.node_group.links.new(ObjectBatoms.outputs['Geometry'],
                                TransferBatoms.inputs[0])
        gn.node_group.links.new(PositionBatoms.outputs['Position'],
                                TransferBatoms.inputs['Attribute'])
        gn.node_group.links.new(GroupInput.outputs[1],
                                TransferBatoms.inputs['Index'])
        # ------------------------------------------------------------------
        # add positions with offsets
        # transfer offsets from object self.obj_o
        ObjectOffsets = get_nodes_by_name(gn.node_group.nodes,
                                          '%s_ObjectOffsets' % (self.label),
                                          'GeometryNodeObjectInfo')
        ObjectOffsets.inputs['Object'].default_value = self.obj_o
        PositionOffsets = get_nodes_by_name(gn.node_group.nodes,
                                            '%s_PositionOffsets' % (
                                                self.label),
                                            'GeometryNodeInputPosition')
        TransferOffsets = get_nodes_by_name(gn.node_group.nodes,
                                            '%s_TransferOffsets' % self.label,
                                            'GeometryNodeAttributeTransfer')
        TransferOffsets.mapping = 'INDEX'
        TransferOffsets.data_type = 'FLOAT_VECTOR'
        gn.node_group.links.new(ObjectOffsets.outputs['Geometry'],
                                TransferOffsets.inputs[0])
        gn.node_group.links.new(PositionOffsets.outputs['Position'],
                                TransferOffsets.inputs['Attribute'])
        OffsetNode = self.vectorDotMatrix(gn, TransferOffsets,
                                          self.batoms.cell, '')
        # we need one add operation to get the positions with offset
        VectorAdd = get_nodes_by_name(gn.node_group.nodes,
                                      '%s_VectorAdd' % (self.label),
                                      'ShaderNodeVectorMath')
        VectorAdd.operation = 'ADD'
        gn.node_group.links.new(TransferBatoms.outputs[0], VectorAdd.inputs[0])
        gn.node_group.links.new(OffsetNode.outputs[0], VectorAdd.inputs[1])
        # set positions
        SetPosition = get_nodes_by_name(gn.node_group.nodes,
                                        '%s_SetPosition' % self.label,
                                        'GeometryNodeSetPosition')
        gn.node_group.links.new(
            GroupInput.outputs['Geometry'], SetPosition.inputs['Geometry'])
        gn.node_group.links.new(
            VectorAdd.outputs[0], SetPosition.inputs['Position'])

    def add_geometry_node(self, spname):
        """
        """
        from batoms.utils.butils import get_nodes_by_name
        gn = self.gnodes
        GroupInput = gn.node_group.nodes[0]
        SetPosition = get_nodes_by_name(gn.node_group.nodes,
                                        '%s_SetPosition' % self.label)
        JoinGeometry = get_nodes_by_name(gn.node_group.nodes,
                                         '%s_JoinGeometry' % self.label,
                                         'GeometryNodeJoinGeometry')
        CompareSpecies = get_nodes_by_name(gn.node_group.nodes,
                                           'CompareFloats_%s_%s' % (
                                               self.label, spname),
                                           compareNodeType)
        CompareSpecies.operation = 'EQUAL'
        # CompareSpecies.data_type = 'INT'
        CompareSpecies.inputs[1].default_value = string2Number(spname)
        InstanceOnPoint = get_nodes_by_name(gn.node_group.nodes,
                                            'InstanceOnPoint_%s_%s' % (
                                                self.label, spname),
                                            'GeometryNodeInstanceOnPoints')
        ObjectInfo = get_nodes_by_name(gn.node_group.nodes,
                                       'ObjectInfo_%s_%s' % (
                                           self.label, spname),
                                       'GeometryNodeObjectInfo')
        ObjectInfo.inputs['Object'].default_value = \
            self.batoms.species.instancers[spname]
        BoolShow = get_nodes_by_name(gn.node_group.nodes,
                                     'BooleanMath_%s_%s_1' % (
                                         self.label, spname),
                                     'FunctionNodeBooleanMath')
        #
        gn.node_group.links.new(
            SetPosition.outputs['Geometry'], InstanceOnPoint.inputs['Points'])
        gn.node_group.links.new(
            GroupInput.outputs[2], CompareSpecies.inputs[0])
        gn.node_group.links.new(GroupInput.outputs[3], BoolShow.inputs[0])
        gn.node_group.links.new(
            GroupInput.outputs[6], InstanceOnPoint.inputs['Scale'])
        gn.node_group.links.new(CompareSpecies.outputs[0], BoolShow.inputs[1])
        gn.node_group.links.new(
            BoolShow.outputs['Boolean'], InstanceOnPoint.inputs['Selection'])
        gn.node_group.links.new(
            ObjectInfo.outputs['Geometry'], InstanceOnPoint.inputs['Instance'])
        gn.node_group.links.new(InstanceOnPoint.outputs['Instances'],
                                JoinGeometry.inputs['Geometry'])

    def update(self):
        """Main function to update boundary
        1) for each frame, search the boundary list
        2) mearch all boundary list, and find the unique boundary list
        3) calculate all boundary data
        """
        object_mode()
        # clean_coll_objects(self.coll, 'bond')
        frames = self.batoms.get_frames()
        images = self.batoms.as_ase()
        nframe = self.batoms.nframe
        if nframe == 1:
            images = [images]
        tstart = time()
        for f in range(nframe):
            # print('update boundary: ', f)
            # print(images[f].positions)
            # use local positions for boundary search
            boundary_list = search_boundary(images[f],
                                            self.boundary)
            if f == 0:
                boundary_lists = boundary_list
            else:
                boundary_lists = np.append(
                    boundary_lists, boundary_list, axis=0)
        boundary_lists = np.unique(boundary_lists, axis=0)
        boundary_datas = self.calc_boundary_data(
            boundary_lists, images[0].arrays, frames, self.batoms.cell)
        # update unit cell

        #
        self.set_arrays(boundary_datas)
        self.batoms.draw()
        print('draw bond: {0:10.2f} s'.format(time() - tstart))

    @property
    def obj(self):
        return self.get_obj()

    def get_obj(self):
        obj = bpy.data.objects.get(self.obj_name)
        if obj is None:
            # , self.batoms.location)
            self.build_object(default_boundary_datas)
        return obj

    @property
    def obj_o(self):
        return self.get_obj_o()

    def get_obj_o(self):
        name = '%s_boundary_offset' % self.label
        obj_o = bpy.data.objects.get(name)
        if obj_o is None:
            raise KeyError('%s object is not exist.' % name)
        return obj_o

    @property
    def boundary(self):
        return self.get_boundary()

    @boundary.setter
    def boundary(self, boundary):
        if boundary is not None:
            if isinstance(boundary, (int, float)):
                boundary = np.array([[-boundary, 1 + boundary]]*3)
            elif len(boundary) == 3:
                if isinstance(boundary[0], (int, float)):
                    boundary = np.array([[-boundary[0], 1 + boundary[0]],
                                         [-boundary[1], 1 + boundary[1]],
                                         [-boundary[2], 1 + boundary[2]]])
                elif len(boundary[0]) == 2:
                    boundary = np.array(boundary)
            else:
                raise Exception('Wrong boundary setting!')
            self.batoms.coll.batoms.boundary = boundary[:].flatten()
        self.update()

    def get_boundary(self):
        boundary = np.array(self.batoms.coll.batoms.boundary)
        return boundary.reshape(3, -1)

    def set_arrays(self, arrays):
        """
        """
        attributes = self.attributes
        # same length
        dnvert = len(arrays['species_index']) - \
            len(attributes['species_index'])
        if dnvert > 0:
            self.add_vertices_bmesh(dnvert)
            self.add_vertices_bmesh(dnvert, self.obj_o)
        elif dnvert < 0:
            self.delete_vertices_bmesh(range(-dnvert))
            self.delete_vertices_bmesh(range(-dnvert), self.obj_o)
        self.positions = arrays["positions"][0]
        self.offsets = arrays["offsets"][0]
        self.set_frames(arrays)
        self.update_mesh()
        species_index = [string2Number(sp) for sp in arrays['species']]
        self.set_attributes({
                            'atoms_index': arrays["atoms_index"],
                            'species_index': species_index,
                            'scale': arrays['scales'],
                            'show': arrays['shows'],
                            })
        species = np.unique(arrays['species'])
        for sp in species:
            self.add_geometry_node(sp)

    def get_arrays(self):
        """
        """
        object_mode()
        # tstart = time()
        arrays = self.attributes
        arrays.update({'positions': self.positions})
        arrays.update({'offsets': self.offsets})
        # radius
        radius = self.batoms.radius
        arrays.update({'radius': np.zeros(len(self))})
        species = np.array([number2String(i)
                           for i in arrays['species_index']], dtype='U20')
        arrays['species'] = species
        for sp, value in radius.items():
            mask = np.where(arrays['species'] == sp)
            arrays['radius'][mask] = value
        # size
        arrays['size'] = arrays['radius']*arrays['scale']
        # main elements
        main_elements = self.batoms.species.main_elements
        elements = [main_elements[sp] for sp in arrays['species']]
        arrays.update({'elements': np.array(elements, dtype='U20')})
        # print('get_arrays: %s'%(time() - tstart))
        return arrays

    @property
    def boundary_data(self):
        return self.get_boundary_data()

    def get_boundary_data(self, include_batoms=False):
        """
        using foreach_get and foreach_set to improve performance.
        """
        arrays = self.arrays
        boundary_data = {'positions': arrays['positions'],
                         'species': arrays['species'],
                         'indices': arrays['atoms_index'],
                         'offsets': arrays['offsets']}
        return boundary_data

    @property
    def offsets(self):
        return self.get_offsets()

    def get_offsets(self):
        """
        using foreach_get and foreach_set to improve performance.
        """
        n = len(self)
        offsets = np.empty(n*3, dtype=int)
        self.obj_o.data.shape_keys.key_blocks[0].data.foreach_get(
            'co', offsets)
        return offsets.reshape((n, 3))

    @offsets.setter
    def offsets(self, offsets):
        self.set_offsets(offsets)

    def set_offsets(self, offsets):
        """
        Set global offsets to local vertices
        """
        object_mode()
        n = len(self.obj_o.data.vertices)
        if len(offsets) != n:
            raise ValueError('offsets has wrong shape %s != %s.' %
                             (len(offsets), n))
        offsets = offsets.reshape((n*3, 1))
        self.obj_o.data.shape_keys.key_blocks[0].data.foreach_set(
            'co', offsets)
        self.obj_o.data.update()
        # bpy.context.view_layer.objects.active = self.obj_o
        # bpy.ops.object.mode_set(mode='EDIT')
        # bpy.ops.object.mode_set(mode='OBJECT')

    @property
    def bondlists(self):
        return self.get_bondlists()

    def get_bondlists(self):
        bondlists = self.batoms.bonds.arrays
        return bondlists

    def get_frames(self):
        """
        """
        frames = {}
        frames['positions'] = self.get_obj_frames(self.obj)
        frames['offsets'] = self.get_obj_frames(self.obj_o)
        return frames

    def set_frames(self, frames=None, frame_start=0, only_basis=False):
        if frames is None:
            frames = self._frames
        nframe = len(frames)
        if nframe == 0:
            return
        name = '%s_boundary' % (self.label)
        obj = self.obj
        self.set_obj_frames(name, obj, frames['positions'])
        #
        name = '%s_boundary_offset' % (self.label)
        obj = self.obj_o
        self.set_obj_frames(name, obj, frames['offsets'])

    def calc_boundary_data(self, boundary_lists, arrays, positions, cell):
        """
        """
        # tstart = time()
        # properties
        model_styles = arrays['model_style'][boundary_lists[:, 0]]
        shows = arrays['show'][boundary_lists[:, 0]]
        selects = arrays['select'][boundary_lists[:, 0]]
        scales = arrays['scale'][boundary_lists[:, 0]]
        species_indexs = arrays['species_index'][boundary_lists[:, 0]]
        species = arrays['species'][boundary_lists[:, 0]]
        # ------------------------------------
        offset_vectors = boundary_lists[:, 1:4]
        offsets = np.dot(offset_vectors, cell)
        # use global positions to build boundary positions
        if len(positions.shape) == 2:
            positions = np.array([positions])
        positions = positions[:, boundary_lists[:, 0]] + offsets
        datas = {
            'atoms_index': np.array(boundary_lists[:, 0]),
            'species_index': species_indexs,
            'species': species,
            'positions': positions,
            # 'offsets':offsets,
            'offsets': np.array([offset_vectors]),
            'model_styles': model_styles,
            'shows': shows,
            'selects': selects,
            'scales': scales,
        }
        # print('datas: ', datas)
        # print('calc_boundary_data: {0:10.2f} s'.format(time() - tstart))
        return datas

    def __getitem__(self, index):
        return self.boundary[index]

    def __setitem__(self, index, value):
        """Set boundary vectors.
        """
        boundary = self.boundary
        if isinstance(value, (int, float)):
            boundary = np.array([-boundary, 1 + boundary])
        boundary[index] = value
        self.boundary = boundary

    def __repr__(self) -> str:
        s = self.boundary.__repr__()
        return s
