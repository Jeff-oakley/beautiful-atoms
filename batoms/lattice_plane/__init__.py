"""Definition of the plane class.

This module defines the plane object in the Batoms package.

"""

import bpy
import bmesh
from time import time
import numpy as np
from batoms.base.object import BaseObject
from batoms.lattice_plane.lattice_plane_setting import LatticePlaneSettings
from batoms.draw import draw_cylinder, draw_surface_from_vertices


class LatticePlane(BaseObject):
    def __init__(self,
                 label=None,
                 location=np.array([0, 0, 0]),
                 batoms=None,
                 ):
        """Plane Class

        Args:
            label (_type_, optional): _description_. Defaults to None.
            location (_type_, optional): _description_. Defaults to np.array([0, 0, 0]).
            batoms (_type_, optional): _description_. Defaults to None.
        """
        #
        self.batoms = batoms
        self.label = label
        name = 'plane'
        BaseObject.__init__(self, label, name)
        self.setting = LatticePlaneSettings(
            self.label, parent=self)

    def build_materials(self, name, color, node_inputs=None,
                        material_style='default'):
        """
        """
        from batoms.material import create_material
        if name in bpy.data.materials:
            mat = bpy.data.materials.get(name)
            bpy.data.materials.remove(mat, do_unlink=True)
        mat = create_material(name,
                              color=color,
                              node_inputs=node_inputs,
                              material_style=material_style,
                              backface_culling=False)
        return mat

    def build_plane(self, bcell, include_center=False):
        """
        Build vertices, edges and faces of plane.

        """
        cellEdges = bcell.edges
        cellVerts = bcell.local_positions
        planes = {}
        for p in self.setting:
            intersect_points = []
            normal = np.dot(p.indices, bcell.reciprocal)
            normal = normal/np.linalg.norm(normal)
            # get intersection point
            for edge in cellEdges:
                line = cellVerts[edge]
                point = p.distance*normal
                intersect_point = linePlaneIntersection(line, normal, point)
                if intersect_point is not None:
                    intersect_points.append(intersect_point)
                # get verts, edges, faces by Hull
            if len(intersect_points) < 3:
                continue
            vertices, edges, faces = faces_from_vertices(
                intersect_points, normal,
                include_center=include_center, scale=p.scale)
            planes[p.name] = self.get_plane_data(vertices, edges, faces, p)
        self.planes = planes
        return planes

    def get_plane_data(self, vertices, edges, faces, p):
        """
        build edge
        """
        plane = {}
        if len(faces) > 0:
            plane = {'vertices': vertices,
                     'edges': edges,
                     'faces': faces,
                     'color': p.color,
                     'indices': p.indices,
                     'edges_cylinder': {'lengths': [], 'centers': [],
                                        'normals': [], 'vertices': 6,
                                        'color': (0.0, 0.0, 0.0, 1.0),
                                        'width': p.width,
                                        'battr_inputs': {},
                                        },
                     'battr_inputs': {'plane': p.as_dict()},
                     'show_edge': p.show_edge,
                     'slicing': p.slicing,
                     'boundary': p.boundary,
                     }
            for edge in edges:
                center = (vertices[edge[0]] + vertices[edge[1]])/2.0
                vec = vertices[edge[0]] - vertices[edge[1]]
                length = np.linalg.norm(vec)
                nvec = vec/length
                plane['edges_cylinder']['lengths'].append(length)
                plane['edges_cylinder']['centers'].append(center)
                plane['edges_cylinder']['normals'].append(nvec)
        return plane

    def build_slicing(self, name, volume, bcell, cuts=None, cmap='Spectral'):
        """
        Change plane to a 2D slicing plane.
        Use vertex color
        """
        from scipy import ndimage
        from ase.cell import Cell
        from batoms.utils.butils import object_mode
        import matplotlib
        cell = Cell(bcell.array)
        plane = bpy.data.objects.get(name)
        object_mode()
        me = plane.data
        bm = bmesh.new()
        bm.from_mesh(me)
        # get maximum cuts based on the density
        if cuts is None:
            density = bcell.length/volume.shape
            maxlength = 0
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            for edge in bm.edges:
                v = bm.verts[edge.verts[0].index].co - \
                    bm.verts[edge.verts[1].index].co
                length = np.linalg.norm(v)
                if length > maxlength:
                    maxlength = length
            cuts = maxlength/np.min(density)
            print('cuts: ', cuts)
        # make mesh by subdivided
        bmesh.ops.subdivide_edges(bm,
                                  edges=bm.edges,
                                  cuts=cuts,
                                  use_grid_fill=True,
                                  )
        bm.to_mesh(me)
        me.update()
        # vertices to coordinates
        n = len(me.vertices)
        local_positions = np.empty(n*3, dtype=np.float64)
        me.vertices.foreach_get('co', local_positions)
        local_positions = local_positions.reshape((n, 3))
        n = len(local_positions)
        # positions (natom, 3) to (natom, 4)
        local_positions = np.append(local_positions, np.ones((n, 1)), axis=1)
        mat = np.array(plane.matrix_world)
        positions = mat.dot(local_positions.T).T
        # (natom, 4) back to (natom, 3)
        positions = positions[:, :3] - bcell.origin
        # get scaled positions
        scaled_positions = cell.scaled_positions(positions)
        index = scaled_positions*volume.shape
        # map new value
        new_volume = ndimage.map_coordinates(volume, index.T, order=1)
        dv = np.max(new_volume) - np.min(new_volume)
        new_volume = (new_volume - np.min(new_volume))/dv
        # map value to color by colormap
        cmap = matplotlib.cm.get_cmap(cmap)
        object_mode()
        bm = bmesh.new()
        bm.from_mesh(plane.data)
        volume_layer = bm.loops.layers.color.new('volume')

        for v in bm.verts:
            for loop in v.link_loops:
                color = cmap(new_volume[v.index])
                loop[volume_layer] = color
        bm.to_mesh(plane.data)
        plane.data.update()
        plane.data.materials[0].use_backface_culling = True
        plane.data.materials[0].show_transparent_back = False
        # add node
        node_tree = plane.data.materials[0].node_tree
        nodes = node_tree.nodes
        mat_links = node_tree.links
        bsdf = nodes.get("Principled BSDF")
        assert(bsdf)
        vcol = nodes.new(type="ShaderNodeVertexColor")
        vcol.layer_name = "volume"
        mat_links.new(vcol.outputs['Color'], bsdf.inputs['Base Color'])
        # bpy.context.view_layer.objects.active = plane
        # bpy.ops.object.mode_set(mode='VERTEX_PAINT')

    def build_slicing_image(self, volume, bcell):
        """
        2D slicings of volumetric data by an arbitrary plane.
        Todo: calculate size
        """
        self.get_symmetry_indices()
        shape = volume.shape
        slicings = {}
        for p in self:
            if not p.slicing:
                continue
            length = bcell.length
            d = p.distance/length
            index = [int(i) for i in d*shape]
            data = []
            if p.indices[0] == 1:
                data = volume[index[0], :, :]
                positions = d*bcell.array[0] + \
                    (bcell.array[1] + bcell.array[1])/2.0
                rotation = (np.pi/2, 0, 0)
                size = (length[1], length[2], 1)
            if p.indices[1] == 1:
                data = volume[:, index[1], :]
                positions = d*bcell.array[1] + \
                    (bcell.array[0] + bcell.array[2])/2.0
                rotation = (0, np.pi/2, 0)
                size = (length[0], length[2], 1)
            if p.indices[2] == 1:
                data = volume[:, :, index[2]]
                positions = d*bcell.array[2] + \
                    (bcell.array[0] + bcell.array[1])/2.0
                rotation = (0, 0, 0)
                size = (length[0], length[1], 1)
            imagename = '%s_image_%s.png' % (self.label, p.name)
            save_image(data, imagename, interpolation='bicubic')
            slicings[p.name] = {'imagename': imagename,
                                'location': positions,
                                'rotation': rotation,
                                'size': size}
        return slicings

    def build_boundary(self, indices):
        """
        Remove vertices above the plane
        """
        p = self.setting[indices]
        normal = np.dot(np.array(p.indices), self.batoms.cell.reciprocal)
        normal = normal/np.linalg.norm(normal)
        point = p.distance*normal
        # isosurface, plane
        colls = self.batoms.coll.children.keys()
        for coll_name in colls:
            objs = bpy.data.collections.get(coll_name).all_objects.keys()
            if 'cell' in coll_name:
                continue
            for obj_name in objs:
                obj = bpy.data.objects.get(obj_name)
                if obj.type != 'MESH':
                    continue
                if 'volume' in obj.name:
                    continue
                n = len(obj.data.vertices)
                vertices = np.empty(n*3, dtype=np.float64)
                obj.data.vertices.foreach_get('co', vertices)
                vertices = vertices.reshape((n, 3))
                x1 = np.dot(vertices, normal) - np.dot(point, normal)
                index = np.where(x1 > -1e-6)[0]
                if len(index) == 0:
                    continue
                if obj.batoms.type == 'BATOMS':
                    self.batoms.delete(obj.batoms.batom.species, index)
                else:
                    bm = bmesh.new()
                    bm.from_mesh(obj.data)
                    bm.verts.ensure_lookup_table()
                    verts_select = [bm.verts[i] for i in index]
                    bmesh.ops.delete(bm, geom=verts_select, context='VERTS')
                    bm.to_mesh(obj.data)

    def draw(self, plane_name='ALL', no=None,
             cuts=None, cmap='bwr', include_center=False):
        """Draw plane
        no: int
            spacegroup of structure, if None, no will be determined by
            get_spacegroup_number()
        cuts: int
            The number of subdivide for selected plane for 2d slicing
        camp: str,
        default 'bwr'
            colormaps for 2d slicing.
        include_center: bool
            include center of plane in the mesh
        """
        from batoms.utils.butils import clean_coll_object_by_type
        # delete old plane
        clean_coll_object_by_type(self.batoms.coll, 'LATTICEPLANE')
        if no is not None:
            self.no = no
        planes = self.build_plane(
            self.batoms.cell, include_center=include_center)
        for species, plane in planes.items():
            if plane_name.upper() != "ALL" and species != plane_name:
                continue
            if plane['boundary']:
                name = '%s_%s_%s' % (self.label, 'plane', species)
                self.delete_obj(name)
                self.build_boundary(plane['indices'])
                bpy.context.view_layer.update()
            else:
                name = '%s_%s_%s' % (self.label, 'plane', species)
                self.delete_obj(name)
                obj = draw_surface_from_vertices(name, plane,
                                                 coll=self.batoms.coll,
                                                 )
                mat = self.build_materials(name, color=plane['color'])
                obj.data.materials.append(mat)
                obj.parent = self.batoms.obj
                obj.batoms.type = 'LATTICEPLANE'
                obj.batoms.label = self.batoms.label
                if plane['show_edge']:
                    name = '%s_%s_%s' % (self.label, 'plane_edge', species)
                    self.delete_obj(name)
                    obj = draw_cylinder(name=name,
                                        datas=plane['edges_cylinder'],
                                        coll=self.batoms.coll,
                                        )
                    obj.parent = self.batoms.obj
                    obj.batoms.type = 'LATTICEPLANE'
                    obj.batoms.label = self.batoms.label
                if plane['slicing']:
                    name = '%s_%s_%s' % (self.label, 'plane', species)
                    self.build_slicing(name, self.batoms.volume,
                                       self.batoms.cell,
                                       cuts=cuts,
                                       cmap=cmap)


def save_image(data, filename, interpolation='bicubic'):
    """
    """
    import pylab as plt
    import numpy as np
    data = data.T
    size = np.shape(data)
    print('size: ', size)
    fig = plt.figure(figsize=(size[1]/size[0]*10, 10))
    ax = plt.Axes(fig, [0., 0., 1., 1.])
    ax.set_axis_off()
    fig.add_axes(ax)
    ax.imshow(data, interpolation=interpolation)
    plt.savefig(filename, dpi=300)


def faces_from_vertices(vertices, normal,
                        include_center=False, scale=[1, 1, 1]):
    """
    get faces from vertices
    """
    # remove duplicative point
    vertices = np.unique(vertices, axis=0)
    n = len(vertices)
    if n < 3:
        return vertices, [], []
    center = np.mean(vertices, axis=0)
    v1 = vertices[0] - center
    angles = [[0, 0]]
    normal = normal/(np.linalg.norm(normal) + 1e-6)
    for i in range(1, n):
        v2 = vertices[i] - center
        x = np.cross(v1, v2)
        c = np.sign(np.dot(x, normal))
        angle = np.arctan2(c, np.dot(v1, v2))
        angles.append([i, angle])
    # scale
    vec = vertices - center
    # length = np.linalg.norm(vec, axis = 1)
    # nvec = vec/length[:, None]
    vertices = center + np.array([scale])*vec
    # search convex polyhedra
    angles = sorted(angles, key=lambda l: l[1])
    if not include_center:
        faces = [[a[0] for a in angles]]
        edges = [[angles[0][0], angles[-1][0]]]
        for i in range(0, n - 1):
            edges.append([angles[i][0], angles[i + 1][0]])
    else:
        # add center to vertices
        vertices = np.append(vertices, center.reshape(1, 3), axis=0)
        icenter = len(vertices) - 1
        faces = [[angles[0][0], angles[-1][0], icenter]]
        edges = [[angles[0][0], icenter],
                 [angles[0][0], angles[-1][0]],
                 [angles[-1][0], icenter]]
        for i in range(0, n - 1):
            faces.append([angles[i][0], angles[i + 1][0], icenter])
            edges.extend([[angles[i][0], angles[i + 1][0]],
                          [angles[i][0], icenter],
                          [angles[i + 1][0], icenter]])
    return vertices, edges, faces


def linePlaneIntersection(line, normal, point):
    """
    3D Line Segment and Plane Intersection
    - Point
    - Line contained in plane
    - No intersection
    """
    d = np.dot(point, normal)
    normalLine = line[0] - line[1]
    a = np.dot(normalLine, normal)
    # No intersection or Line contained in plane
    if np.isclose(a, 0):
        return None
    # in same side
    b = np.dot(line, normal) - d
    if b[0]*b[1] > 0:
        return None
    # Point
    v = point - line[0]
    d = np.dot(v, normal)/a
    point = np.round(line[0] + normalLine*d, 6)
    return point


def threePlaneIntersection(planes):
    """
    3D three Planes Intersection
    """
    # Condition for a single point of intersection
    mat = np.concatenate([[plane['normal']] for plane in planes], axis=0)
    det = np.linalg.det(mat)
    if np.isclose(det, 0):
        return None
    darray = np.array([np.dot(plane['point'], plane['normal'])
                      for plane in planes])
    point = np.zeros(3)
    for i in range(3):
        temp = mat.copy()
        temp[:, i] = darray
        point[i] = round(np.linalg.det(temp)/det, 6)
    return point


def convexhull(planes, point):
    """
    find points at the same side of origin for all planes
    Todo: '+' or '-'
    """
    if point is None:
        return None
    for name, plane in planes.items():
        x1 = np.dot(point, plane['normal']) - \
            np.dot(plane['point'], plane['normal'])
        x2 = np.dot(np.array([0, 0, 0]), plane['normal']) - \
            np.dot(plane['point'], plane['normal'])
        if abs(x1) > 1e-6 and x1*x2 < -1e-6:
            return None
    return point
