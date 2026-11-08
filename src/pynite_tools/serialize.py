"""
Serialization of Pynite.FEModel3D objects to/from JSON-compatible data.

The schemas in this module mirror the *input* data of a Pynite model (geometry,
properties, supports, loads, load combinations and mesh/shear wall/mat foundation
definitions). Analysis results are not serialized; re-run the analysis after loading.

Models are rebuilt through FEModel3D's public `add_*` API so that every object is
constructed exactly as Pynite expects.
"""
import json
import pathlib
from typing import Any, Literal, Optional, TextIO

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

import Pynite
from Pynite import FEModel3D
from Pynite import Mesh as pynite_mesh

pynite_version = Pynite.__version__


def to_json(model: FEModel3D, filepath: str | pathlib.Path) -> None:
    """
    Serializes the model to a new JSON file at 'filepath'.
    """
    filepath = pathlib.Path(filepath)
    with open(filepath, 'w') as file:
        dump(model, file)


def from_json(filepath: str | pathlib.Path) -> FEModel3D:
    """
    Reads the JSON file at 'filepath' and returns the Pynite.FEModel3D.
    """
    with open(filepath, 'r') as file:
        model = load(file)
    return model


def dump(model: FEModel3D, file_io: TextIO, indent: int = 2) -> None:
    """
    Writes the 'model' as a JSON data to the file-handler object, 'file_io'.

    'indent': the number of spaces to indent in the file.
    """
    model_dict = dump_dict(model)
    json.dump(model_dict, fp=file_io, indent=indent)


def dumps(model: FEModel3D, indent: int = 2) -> str:
    """
    Returns the model as JSON string.
    """
    model_schema = get_model_schema(model)
    return model_schema.model_dump_json(indent=indent)


def dump_dict(model: FEModel3D) -> dict:
    """
    Returns a Python dictionary representing the model.

    The Python dictionary is serializable to JSON.
    """
    model_schema = get_model_schema(model)
    return model_schema.model_dump(mode="json")


def load(file_io: TextIO) -> FEModel3D:
    """
    Returns an FEModel3D from the json data contained within the file.
    """
    json_data = json.load(file_io)
    return load_dict(json_data)


def loads(model_json: str) -> FEModel3D:
    """
    Returns an FEModel3D based on the provided 'model_json'.

    'model_json': a JSON-serialized str representing an FEModel3D
    """
    model_schema = TypeAdapter(FEModel3DSchema).validate_json(model_json)
    return model_schema.to_femodel3d()


def load_dict(model_dict: dict) -> FEModel3D:
    """
    Returns an FEModel3D based on the provided 'model_dict'.

    'model_dict': A JSON-serializable dict representing an FEModel3D
    """
    model_schema = TypeAdapter(FEModel3DSchema).validate_python(model_dict)
    return model_schema.to_femodel3d()


def get_model_schema(model: FEModel3D) -> "FEModel3DSchema":
    """
    Returns an FEModel3DSchema based on the supplied model.
    """
    return TypeAdapter(FEModel3DSchema).validate_python(model, from_attributes=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _attrs(obj: Any) -> dict:
    """Returns the instance attributes of 'obj' (or 'obj' itself if it is already a dict)."""
    if isinstance(obj, dict):
        return obj
    return dict(vars(obj))


def _name(obj: Any) -> Any:
    """Returns obj.name for Pynite objects (or dicts with a 'name' key), else obj."""
    if obj is None or isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return obj.get("name")
    return getattr(obj, "name", obj)


def _find_material_name(model: FEModel3D, E: float, nu: float) -> Optional[str]:
    """Returns the name of the first material in 'model' with matching E and nu."""
    for mat_name, material in model.materials.items():
        if material.E == E and material.nu == nu:
            return mat_name
    return None


def _node_ref(node: "NodeRef") -> str:
    return node if isinstance(node, str) else node.name


class _Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Basic model objects
# ---------------------------------------------------------------------------

class LoadComboSchema(_Schema):
    name: str
    factors: dict[str, float]
    combo_tags: Optional[list[str] | str] = None  # Used to categorize the load combination (e.g. strength or serviceability)


class Node3DSchema(_Schema):
    """
    A node in a 3D finite element model.
    """
    name: str  # A unique name for the node assigned by the user
    X: float   # Global X coordinate
    Y: float   # Global Y coordinate
    Z: float   # Global Z coordinate

    NodeLoads: list[tuple[str, float, str]] = []  # (Direction, P, case) or (Direction, M, case)

    # Support conditions
    support_DX: bool = False
    support_DY: bool = False
    support_DZ: bool = False
    support_RX: bool = False
    support_RY: bool = False
    support_RZ: bool = False

    # Support springs: [stiffness, direction, active]
    spring_DX: list[float | str | bool | None] = [None, None, None]
    spring_DY: list[float | str | bool | None] = [None, None, None]
    spring_DZ: list[float | str | bool | None] = [None, None, None]
    spring_RX: list[float | str | bool | None] = [None, None, None]
    spring_RY: list[float | str | bool | None] = [None, None, None]
    spring_RZ: list[float | str | bool | None] = [None, None, None]

    # Enforced displacements
    EnforcedDX: float | None = None
    EnforcedDY: float | None = None
    EnforcedDZ: float | None = None
    EnforcedRX: float | None = None
    EnforcedRY: float | None = None
    EnforcedRZ: float | None = None

    contour: list[float] = []

    def apply_to(self, node) -> None:
        """Copies the non-constructor attributes onto an existing Pynite Node3D."""
        for attr_name, attr_value in self:
            if attr_name in ("name", "X", "Y", "Z"):
                continue
            if isinstance(attr_value, list):
                attr_value = list(attr_value)
            setattr(node, attr_name, attr_value)


# Elements reference nodes either by an embedded node (the historical format, which is
# still written for backwards compatibility) or by name.
NodeRef = Node3DSchema | str


class MaterialSchema(_Schema):
    name: str
    E: float
    G: float
    nu: float
    rho: float
    fy: Optional[float] = None


class SectionSchema(_Schema):
    name: str
    A: float
    Iy: float
    Iz: float
    J: float
    # The following are only present for steel sections (FEModel3D.add_steel_section)
    Zy: Optional[float] = None
    Zz: Optional[float] = None
    material_name: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _extract_steel_section(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        attrs = _attrs(data)
        if "Zy" in attrs:
            attrs["material_name"] = _name(attrs.get("material"))
        return attrs


class Member3DSchema(_Schema):
    name: str
    i_node: NodeRef
    j_node: NodeRef
    material: MaterialSchema | str
    section: SectionSchema | str
    rotation: float = 0.0
    PtLoads: list[tuple] = []    # (Direction, P, x, case) or (Direction, M, x, case)
    DistLoads: list[tuple] = []  # (Direction, w1, w2, x1, x2, case[, self_weight])
    Releases: list[bool] = [False] * 12
    tension_only: bool = False
    comp_only: bool = False
    ID: int | None = None


class PhysMemberSchema(Member3DSchema):
    # Sub-members are derived by Pynite during analysis so they are not written out. The
    # field is retained so that files written by earlier versions can still be read.
    sub_members: dict[str, Any] = Field(default={}, exclude=True)


class Spring3DSchema(_Schema):
    name: str
    i_node: NodeRef
    j_node: NodeRef
    ks: float
    # Springs share the model's load combinations; retained for backwards compatibility
    load_combos: dict[str, LoadComboSchema] = {}
    tension_only: bool = False
    comp_only: bool = False
    ID: Optional[int] = None


class _PlateBaseSchema(_Schema):
    name: str
    i_node: NodeRef
    j_node: NodeRef
    m_node: NodeRef
    n_node: NodeRef
    t: float
    kx_mod: float = 1.0
    ky_mod: float = 1.0
    pressures: list[tuple[float, str]] = []  # [(pressure, case), ...]
    ID: Optional[int] = None
    # Pynite stores E and nu on the element rather than the material name
    E: Optional[float] = None
    nu: Optional[float] = None
    material_name: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _extract_material_name(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        attrs = _attrs(data)
        model = attrs.get("model")
        if model is not None and attrs.get("E") is not None:
            attrs["material_name"] = _find_material_name(model, attrs["E"], attrs.get("nu"))
        return attrs


class Quad3DSchema(_PlateBaseSchema):
    type: Literal["Quad"] = "Quad"


class Plate3DSchema(_PlateBaseSchema):
    type: Literal["Rect"] = "Rect"


# ---------------------------------------------------------------------------
# Generated objects: meshes, shear walls and mat foundations
#
# These are serialized as the "recipe" used to create them. If they were already
# generated, the names of the generated nodes/elements are also stored (the nodes and
# elements themselves are serialized with the rest of the model) so they can be
# re-linked without regenerating.
# ---------------------------------------------------------------------------

# Maps each supported mesh class to {constructor parameter: instance attribute}
MESH_PARAMS: dict[str, dict[str, str]] = {
    "RectangleMesh": {
        p: p for p in [
            "mesh_size", "width", "height", "thickness", "material_name", "kx_mod",
            "ky_mod", "origin", "plane", "x_control", "y_control", "start_node",
            "start_element", "element_type",
        ]
    },
    "AnnulusMesh": {
        p: p for p in [
            "mesh_size", "outer_radius", "inner_radius", "thickness", "material_name",
            "kx_mod", "ky_mod", "origin", "axis", "start_node", "start_element",
        ]
    },
    "FrustrumMesh": {
        "mesh_size": "mesh_size", "large_radius": "outer_radius", "small_radius": "inner_radius",
        "height": "height", "thickness": "thickness", "material_name": "material_name",
        "kx_mod": "kx_mod", "ky_mod": "ky_mod", "origin": "origin", "axis": "axis",
        "start_node": "start_node", "start_element": "start_element",
    },
    "CylinderMesh": {
        "mesh_size": "mesh_size", "radius": "radius", "height": "h", "thickness": "thickness",
        "material_name": "material_name", "kx_mod": "kx_mod", "ky_mod": "ky_mod",
        "origin": "origin", "axis": "axis", "start_node": "start_node",
        "start_element": "start_element", "num_elements": "num_elements",
        "element_type": "element_type",
    },
}


def _to_plain(value: Any) -> Any:
    """Converts tuples to lists (recursively) so recipe params are JSON-friendly."""
    if isinstance(value, (list, tuple)):
        return [_to_plain(v) for v in value]
    return value


def _generated_names(attrs: dict) -> tuple[list[str], list[str]]:
    if not attrs.get("is_generated"):
        return [], []
    return list(attrs.get("nodes", {}) or {}), list(attrs.get("elements", {}) or {})


def _link_generated(obj, model: FEModel3D, node_names: list[str], element_names: list[str]) -> None:
    """Points a generated mesh-like object at the (already rebuilt) nodes/elements in 'model'."""
    if hasattr(obj, "nodes"):
        obj.nodes = {name: model.nodes[name] for name in node_names if name in model.nodes}
    elements = {}
    for name in element_names:
        if name in model.quads:
            elements[name] = model.quads[name]
        elif name in model.plates:
            elements[name] = model.plates[name]
    obj.elements = elements
    if hasattr(obj, "last_node"):
        obj.last_node = list(obj.nodes.values())[-1] if obj.nodes else None
    if hasattr(obj, "last_element"):
        obj.last_element = list(elements.values())[-1] if elements else None
    obj.is_generated = True


class RectOpeningSchema(_Schema):
    x_left: float
    y_bott: float
    width: float
    height: float


class MeshSchema(_Schema):
    mesh_type: str
    params: dict[str, Any]
    openings: dict[str, RectOpeningSchema] = {}
    is_generated: bool = False
    needs_update: bool = False
    node_names: list[str] = []
    element_names: list[str] = []

    @model_validator(mode="before")
    @classmethod
    def _extract_recipe(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        mesh_type = type(data).__name__
        if mesh_type not in MESH_PARAMS:
            raise ValueError(
                f"Serialization of '{mesh_type}' meshes is not supported. "
                f"Supported mesh types: {sorted(MESH_PARAMS)}"
            )
        attrs = _attrs(data)
        node_names, element_names = _generated_names(attrs)
        return {
            "mesh_type": mesh_type,
            "params": {p: _to_plain(attrs[a]) for p, a in MESH_PARAMS[mesh_type].items()},
            "openings": attrs.get("openings", {}),
            "is_generated": attrs.get("is_generated", False),
            "needs_update": attrs.get("needs_update", False),
            "node_names": node_names,
            "element_names": element_names,
        }

    def build(self, model: FEModel3D):
        mesh_class = getattr(pynite_mesh, self.mesh_type)
        if self.is_generated:
            # Some mesh types (e.g. CylinderMesh) generate eagerly in __init__. The generated
            # nodes/elements are already in 'model', so construct against a scratch model
            # (with the same materials) and then re-point the mesh at the real model.
            scratch = FEModel3D()
            for material in model.materials.values():
                scratch.add_material(material.name, material.E, material.G, material.nu, material.rho, material.fy)
            mesh = mesh_class(model=scratch, **self.params)
            mesh.model = model
        else:
            mesh = mesh_class(model=model, **self.params)
        for opening_name, opening in self.openings.items():
            mesh.openings[opening_name] = pynite_mesh.RectOpening(**opening.model_dump())
        if self.is_generated:
            _link_generated(mesh, model, self.node_names, self.element_names)
        mesh.needs_update = self.needs_update
        return mesh


class ShearWallSchema(_Schema):
    name: str
    mesh_size: float
    length: float
    height: float
    ky_mod: float = 0.35
    origin: list[float] = [0, 0, 0]
    plane: str = "XY"
    openings: list[list[Any]] = []
    flanges: list[list[Any]] = []
    supports: list[list[Any]] = []
    stories: list[list[Any]] = []
    shears: list[list[Any]] = []
    axials: list[list[Any]] = []
    materials: list[list[Any]]  # [[material_name, t, x_start, x_end, y_start, y_end], ...]
    is_generated: bool = False
    element_names: list[str] = []

    @model_validator(mode="before")
    @classmethod
    def _extract_recipe(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        attrs = _attrs(data)
        _, element_names = _generated_names(attrs)
        recipe = {
            "name": attrs["name"],
            "mesh_size": attrs["mesh_size"],
            "length": attrs["L"],
            "height": attrs["H"],
            "ky_mod": attrs["ky_mod"],
            "origin": _to_plain(attrs["origin"]),
            "plane": attrs["plane"],
            "is_generated": attrs.get("is_generated", False),
            "element_names": element_names,
        }
        for key in ("openings", "flanges", "supports", "stories", "shears", "axials", "materials"):
            recipe[key] = _to_plain(attrs[f"_{key}"])
        return recipe

    def build(self, model: FEModel3D):
        material_name, thickness = self.materials[0][0], self.materials[0][1]
        model.add_shear_wall(
            self.name, self.mesh_size, self.length, self.height, thickness, material_name,
            ky_mod=self.ky_mod, plane=self.plane, origin=list(self.origin),
        )
        wall = model.shear_walls[self.name]
        for key in ("openings", "flanges", "supports", "stories", "shears", "axials", "materials"):
            setattr(wall, f"_{key}", [list(item) for item in getattr(self, key)])
        if self.is_generated:
            _link_generated(wall, model, [], self.element_names)
            # Piers and coupling beams are derived data: regenerate them on the next analysis
            wall.needs_update = True
        return wall


class MatFoundationSchema(_Schema):
    name: str
    mesh_size: float
    length_X: float
    length_Z: float
    thickness: float
    material_name: str
    ks: float
    origin: list[float] = [0, 0, 0]
    x_control: list[float] = []
    y_control: list[float] = []
    pt_loads: list[list[Any]] = []  # [[[X, Z], direction, magnitude, case], ...]
    openings: dict[str, RectOpeningSchema] = {}
    is_generated: bool = False
    needs_update: bool = False
    node_names: list[str] = []
    element_names: list[str] = []

    @model_validator(mode="before")
    @classmethod
    def _extract_recipe(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        attrs = _attrs(data)
        node_names, element_names = _generated_names(attrs)
        return {
            "name": attrs["name"],
            "mesh_size": attrs["mesh_size"],
            "length_X": attrs["width"],
            "length_Z": attrs["height"],
            "thickness": attrs["thickness"],
            "material_name": attrs["material_name"],
            "ks": attrs["ks"],
            "origin": _to_plain(attrs["origin"]),
            "x_control": _to_plain(attrs["x_control"]),
            "y_control": _to_plain(attrs["y_control"]),
            "pt_loads": _to_plain(attrs["pt_loads"]),
            "openings": attrs.get("openings", {}),
            "is_generated": attrs.get("is_generated", False),
            "needs_update": attrs.get("needs_update", False),
            "node_names": node_names,
            "element_names": element_names,
        }

    def build(self, model: FEModel3D):
        model.add_mat_foundation(
            self.name, self.mesh_size, self.length_X, self.length_Z, self.thickness,
            self.material_name, self.ks, origin=list(self.origin),
            x_control=list(self.x_control), y_control=list(self.y_control),
        )
        mat = model.mats[self.name]
        mat.pt_loads = [list(load) for load in self.pt_loads]
        for opening_name, opening in self.openings.items():
            mat.openings[opening_name] = pynite_mesh.RectOpening(**opening.model_dump())
        if self.is_generated:
            _link_generated(mat, model, self.node_names, self.element_names)
        mat.needs_update = self.needs_update
        return mat


# ---------------------------------------------------------------------------
# The model
# ---------------------------------------------------------------------------

class FEModel3DSchema(_Schema):
    """A 3D finite element model object. This object has methods and dictionaries to create, store,
       and retrieve results from a finite element model.
    """
    nodes: dict[str, Node3DSchema] = {}
    materials: dict[str, MaterialSchema] = {}
    sections: dict[str, SectionSchema] = {}
    springs: dict[str, Spring3DSchema] = {}
    members: dict[str, PhysMemberSchema] = {}
    quads: dict[str, Quad3DSchema] = {}
    plates: dict[str, Plate3DSchema] = {}
    meshes: dict[str, MeshSchema] = {}
    shear_walls: dict[str, ShearWallSchema] = {}
    mats: dict[str, MatFoundationSchema] = {}
    load_combos: dict[str, LoadComboSchema] = {}

    def to_femodel3d(self) -> FEModel3D:
        model = FEModel3D()

        # Load combinations first (springs keep a reference to the model's combos)
        for combo in self.load_combos.values():
            model.add_load_combo(combo.name, dict(combo.factors), combo.combo_tags)

        for material in self.materials.values():
            model.add_material(
                material.name, material.E, material.G, material.nu, material.rho, material.fy
            )

        for section in self.sections.values():
            if section.Zy is not None and section.material_name is not None:
                model.add_steel_section(
                    section.name, section.A, section.Iy, section.Iz, section.J,
                    section.Zy, section.Zz, section.material_name,
                )
            else:
                model.add_section(section.name, section.A, section.Iy, section.Iz, section.J)

        for node in self.nodes.values():
            model.add_node(node.name, node.X, node.Y, node.Z)
            node.apply_to(model.nodes[node.name])

        for member in self.members.values():
            model.add_member(
                member.name,
                _node_ref(member.i_node),
                _node_ref(member.j_node),
                _name(member.material),
                _name(member.section),
                rotation=member.rotation,
                tension_only=member.tension_only,
                comp_only=member.comp_only,
            )
            new_member = model.members[member.name]
            new_member.Releases = list(member.Releases)
            new_member.PtLoads = [tuple(load) for load in member.PtLoads]
            new_member.DistLoads = [tuple(load) for load in member.DistLoads]

        for spring in self.springs.values():
            model.add_spring(
                spring.name,
                _node_ref(spring.i_node),
                _node_ref(spring.j_node),
                spring.ks,
                tension_only=spring.tension_only,
                comp_only=spring.comp_only,
            )

        for elements, add_element in ((self.quads, model.add_quad), (self.plates, model.add_plate)):
            for element in elements.values():
                material_name = element.material_name
                if material_name is None and element.E is not None:
                    material_name = _find_material_name(model, element.E, element.nu)
                if material_name is None:
                    if not model.materials:
                        raise ValueError(
                            f"Cannot rebuild element '{element.name}': the model has no materials."
                        )
                    material_name = next(iter(model.materials))
                add_element(
                    element.name,
                    _node_ref(element.i_node),
                    _node_ref(element.j_node),
                    _node_ref(element.m_node),
                    _node_ref(element.n_node),
                    element.t,
                    material_name,
                    kx_mod=element.kx_mod,
                    ky_mod=element.ky_mod,
                )
                new_element = model.quads[element.name] if element.type == "Quad" else model.plates[element.name]
                # Preserve the element's own elastic properties
                if element.E is not None:
                    new_element.E = element.E
                if element.nu is not None:
                    new_element.nu = element.nu
                new_element.pressures = [tuple(p) for p in element.pressures]

        for mesh_name, mesh in self.meshes.items():
            model.meshes[mesh_name] = mesh.build(model)

        for wall in self.shear_walls.values():
            wall.build(model)

        for mat in self.mats.values():
            mat.build(model)

        model.solution = None
        return model
