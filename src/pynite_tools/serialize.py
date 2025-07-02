import json
import io
import pathlib
from pydantic import TypeAdapter, BaseModel, Field
from typing import Optional, Any, Union, ClassVar, TextIO

from Pynite import FEModel3D, Node3D, Member3D, PhysMember, Material, Section, Spring3D, Quad3D, Plate3D, Mesh, LoadCombo


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
    return model_schema.model_dump()


def load(file_io: TextIO) -> FEModel3D:
    """
    Returns an FEModel3D from the json data contained within the file.
    """
    json_data = json.load(file_io)
    model_adapter = TypeAdapter(FEModel3DSchema)
    model_schema = model_adapter.validate_python(json_data)
    return model_schema.to_femodel3d()


def loads(model_json: str) -> FEModel3D:
    """
    Returns an FEModel3D based on the provided 'model_json'.

    'model_json': a JSON-serialized str representing an FEModel3D
    """
    model_adapter = TypeAdapter(FEModel3DSchema)
    model_schema = model_adapter.validate_json(model_json)
    femodel3d = model_schema.to_femodel3d()
    return femodel3d


def load_dict(model_dict: dict) -> FEModel3D:
    """
    Returns an FEModel3D based on the provided 'model_dict'.

    'model_dict': A JSON-serializable dict representing an FEModel3D
    """
    model_adapter = TypeAdapter(FEModel3DSchema)
    model_schema = model_adapter.validate_python(model_dict)
    femodel3d = model_schema.to_femodel3d()
    return femodel3d


def get_model_schema(model: FEModel3D) -> dict[str, dict]:
    """
    Returns an FEModel3DSchema based on the supplied model.
    """
    model_adapter = TypeAdapter(FEModel3DSchema)
    model_schema = model_adapter.validate_python(model, from_attributes=True)
    return model_schema


class ExporterMixin:
    def to_init_dict(self):
        init_dict = {}
        if self._init_attrs is None:
            return init_dict
        for attr_name in self._init_attrs:
            attr_value = getattr(self, attr_name)
            if hasattr(attr_value, "_pynite_class"):
                attr_value = attr_value._pynite_class(**attr_value.to_init_dict())
            init_dict.update({attr_name: attr_value})
        return init_dict

        
class LoadComboSchema(BaseModel, ExporterMixin):
    name: str
    factors: dict[str, float]
    combo_tags: Optional[list[str]] = None  # Used to categorize the load combination (e.g. strength or serviceability)
    _init_attrs: ClassVar[Optional[list[str]]] = ['name', 'factors']
    _pynite_class: ClassVar[type] = LoadCombo.LoadCombo

class Node3DSchema(BaseModel, ExporterMixin):
    """
    A class representing a node in a 3D finite element model.
    """
    name: str                 # A unique name for the node assigned by the user   
    X: float          # Global X coordinate
    Y: float          # Global Y coordinate
    Z: float          # Global Z coordinate
    
    NodeLoads: list[tuple[str, float, str]] = [] # A list of loads applied to the node (Direction, P, case) or (Direction, M, case)

    # Initialize all support conditions to `False`
    support_DX: bool = False
    support_DY: bool = False
    support_DZ: bool = False
    support_RX: bool = False
    support_RY: bool = False
    support_RZ: bool = False

    # Inititialize all support springs
    spring_DX: list[float | str | bool | None] = [None, None, None]  # [stiffness, direction, active]
    spring_DY: list[float | str | bool | None] = [None, None, None]
    spring_DZ: list[float | str | bool | None] = [None, None, None]
    spring_RX: list[float | str | bool | None] = [None, None, None]
    spring_RY: list[float | str | bool | None] = [None, None, None]
    spring_RZ: list[float | str | bool | None] = [None, None, None]

    # Initialize all enforced displacements to `None`
    EnforcedDX: float | None = None
    EnforcedDY: float | None = None
    EnforcedDZ: float | None = None
    EnforcedRX: float | None = None
    EnforcedRY: float | None = None
    EnforcedRZ: float | None = None
    contour: list[float] = []
    model: Optional[Any] = Field(exclude=True, default=None)
    
    _init_attrs: ClassVar[Optional[list[str]]] = ["name", "X", "Y", "Z"]
    _pynite_class: ClassVar[type] = Node3D.Node3D

class Plate3DSchema(BaseModel, ExporterMixin):
    name: str
    type: str = 'Rect'
    i_node: Node3DSchema
    j_node: Node3DSchema
    m_node: Node3DSchema
    n_node: Node3DSchema
    t: float
    kx_mod: float
    ky_mod: float
    pressures: list[tuple[float, str]] = []  # A list of surface pressures [pressure, case='Case 1']
    ID: Optional[int] = None
    model: Optional[Any] = Field(exclude=True, default=None)
    _init_attrs: ClassVar[Optional[list[str]]] = [
        'name',
        'type',
        'i_node',
        'j_node',
        'm_node',
        'n_node',
        't',
        'kx_mod',
        'ky_mod',
        'model',
    ]
    _pynite_class: ClassVar[type] = Plate3D.Plate3D

class Quad3DSchema(BaseModel, ExporterMixin):
    name: str
    i_node: Node3DSchema
    j_node: Node3DSchema
    m_node: Node3DSchema
    n_node: Node3DSchema
    t: float
    kx_mod: float
    ky_mod: float
    pressures: list[tuple[float, str]] = []
    ID: Optional[int] = None
    type: str = 'Quad'
    # Quads need a link to the model they belong to
    model: Optional[Any] = Field(exclude=True, default=None)
    _init_attrs: ClassVar[Optional[list[str]]] = [
        "name",
        "i_node",
        "j_node",
        "m_node",
        "n_node",
        "t",
        "kx_mod",
        "ky_mod",
        "pressures",
        "ID",
        "model",
    ]
    _pynite_class: ClassVar[type] = Quad3D.Quad3D

class MeshSchema(BaseModel, ExporterMixin):
    thickness: float
    material_name: str
    kx_mod: float
    ky_mod: float
    start_node: str
    last_node: str
    start_element: str
    last_element: str
    nodes: dict[str, Node3DSchema] = {}
    elements: dict[str, Union[Quad3DSchema, Plate3DSchema]] = {}  # A dictionary containing the elements in the mesh
    element_type: str = 'Quad'
    model: Optional[Any] = Field(exclude=True, default=None)
    _init_attrs: ClassVar[Optional[list[str]]] = [
        "thickness",
        "material_name",
        "kx_mod",
        "ky_mod",
        "start_node",
        "last_node",
        "start_element",
        "last_element",
        "element_type",
        "model"
    ]
    _pynite_class: ClassVar[type] = Mesh.Mesh

class MaterialSchema(BaseModel, ExporterMixin):
    name: str
    E: float
    G: float
    nu: float
    rho: float 
    fy: Optional[float] = None
    model: Optional[Any] = Field(exclude=True, default=None)
    _init_attrs: ClassVar[Optional[list[str]]] = ["name", "G", "E", "nu", "rho", "fy", "model"]
    _pynite_class: ClassVar[type] = Material.Material

class SectionSchema(BaseModel, ExporterMixin):
    name: str
    A: float
    Iy: float
    Iz: float
    J: float
    model: Optional[Any] = Field(exclude=True, default=None)
    _init_attrs: ClassVar[Optional[list[str]]] = ["name", "A", "Iy", "Iz", "J", "model"]
    _pynite_class: ClassVar[type] = Section.Section

class Member3DSchema(BaseModel, ExporterMixin):
    name: str
    i_node: Node3DSchema
    j_node: Node3DSchema
    material: MaterialSchema
    section: SectionSchema
    rotation: float
    PtLoads: list[tuple] = []  # A list of point loads & moments applied to the element (Direction, P, x, case='Case 1') or (Direction, M, x, case='Case 1')
    DistLoads: list[tuple] = []       # A list of linear distributed loads applied to the element (Direction, w1, w2, x1, x2, case='Case 1')
    Releases: list[bool] = [False, False, False, False, False, False, False, False, False, False, False, False]
    tension_only: bool = False
    comp_only: bool = False
    ID: int | None = None
    model: Optional[Any] = Field(exclude=True, default=None)
    _init_attrs: ClassVar[Optional[list[str]]] = [
        "name",
        "i_node",
        "j_node",
        "material",
        "section",
        "model",
    ]
    _pynite_class: ClassVar[type] = Member3D.Member3D

class PhysMemberSchema(Member3DSchema):
    sub_members: dict[str, Member3DSchema] = {}
    _init_attrs: ClassVar[Optional[list[str]]] = [
        "name",
        "i_node",
        "j_node",
        "material",
        "section",
        "model",
    ]
    _pynite_class: ClassVar[type] = PhysMember.PhysMember

class Spring3DSchema(BaseModel, ExporterMixin):
    name: str
    i_node: Node3DSchema
    j_node: Node3DSchema
    ks: float
    load_combos: dict[str, LoadComboSchema]
    tension_only: bool
    comp_only: bool
    ID: Optional[int] = None
    _init_attrs: ClassVar[Optional[list[str]]] = [
        "name",
        "i_node",
        "j_node",
        "ks",
        "tension_only",
        "comp_only",
    ]
    _pynite_class: ClassVar[type] = Spring3D.Spring3D

class FEModel3DSchema(BaseModel, ExporterMixin):
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
    load_combos: dict[str, LoadComboSchema] = {}    
    _init_attrs: ClassVar[Optional[list[str]]] = None

    def to_femodel3d(self):
        model_object_classes = {
            "nodes": Node3D.Node3D,
            "materials": Material.Material,
            "sections": Section.Section,
            "springs": Spring3D.Spring3D,
            "members": PhysMember.PhysMember,
            "quads": Quad3D.Quad3D,
            "plates": Plate3D.Plate3D,
            "meshes": Mesh.Mesh,
            "load_combos": LoadCombo.LoadCombo,
        }
        femodel3d = FEModel3D()
        for key, schema_objects in self.__dict__.items():
            model_object_class = model_object_classes[key]
            model_objects = {}
            for key_name, schema_object in schema_objects.items():
                schema_init_dict = schema_object.to_init_dict()

                # Modify the init dict with special case attributes
                if "model" in schema_init_dict:
                    # Need to add the model as an attr to several object types
                    schema_init_dict.update({"model": femodel3d})
                if "material" in schema_init_dict:
                    # Need to use the material_name (not the material object) as the init value
                    material_name = schema_init_dict['material'].name
                    schema_init_dict.pop("material")
                    schema_init_dict.update({"material_name": material_name})
                if "section" in schema_init_dict:
                    # Same as material_name above but with the section
                    section_name = schema_init_dict['section'].name
                    schema_init_dict.pop("section")
                    schema_init_dict.update({"section_name": section_name})
                    
                # Create the new object with their init values
                new_object = model_object_class(**schema_init_dict)
                
                # Add in all of the other attrs excluded from the init process
                for attr_name, attr_value in schema_object.__dict__.items():
                    if attr_name == "model":
                        attr_value = femodel3d
                    if schema_init_dict is None or attr_name not in schema_init_dict:
                        setattr(new_object, attr_name, attr_value)

                # For attr_values that reference nodes, they must reference the original
                # node in the model (an new-but-equal instance will not suffice because it will 
                # not have the correct .ID attribute).
                for attr_name, attr_value in new_object.__dict__.items():
                    if 'node' in attr_name:
                        node_name = attr_value.name
                        orig_node = femodel3d.nodes[node_name]
                        setattr(new_object, attr_name, orig_node)
                    
                model_objects.update({key_name: new_object})
            setattr(femodel3d, key, model_objects)
        return femodel3d