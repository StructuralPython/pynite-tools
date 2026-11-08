"""
Round-trip tests for pynite_tools.serialize: every model is serialized, deserialized,
and both models are analyzed. Node displacements must match exactly.
"""
import json
import math

import pytest
from Pynite import FEModel3D

import pynite_tools as pt


def base_model() -> FEModel3D:
    model = FEModel3D()
    model.add_material('Steel', 29000, 11200, 0.3, 2.836e-4, fy=50)
    model.add_material('Conc', 3600, 1500, 0.17, 8.7e-5)
    model.add_section('S', 20, 100, 150, 250)
    model.add_load_combo('1.4D', {'D': 1.4}, combo_tags=['strength'])
    model.add_load_combo('D+L+W', {'D': 1.0, 'L': 1.0, 'W': 1.0}, combo_tags=['service'])
    return model


def frame_model() -> FEModel3D:
    model = base_model()
    model.add_steel_section('W', 10, 200, 50, 1, 30, 10, 'Steel')
    model.add_node('N1', 0, 0, 0)
    model.add_node('N2', 168, 0, 0)
    model.add_node('N3', 336, 0, 0)
    model.add_node('N4', 168, -100, 0)
    model.add_member('M1', 'N1', 'N3', 'Steel', 'W', rotation=10)
    model.add_member('M2', 'N2', 'N4', 'Steel', 'S')
    model.def_releases('M2', Rzi=True)
    model.add_spring('SP1', 'N4', 'N3', 50.0)
    model.def_support('N1', True, True, True, True, False, False)
    model.def_support('N3', True, True, True, False, False, False)
    model.def_support_spring('N4', 'DY', 100.0)
    model.def_node_disp('N1', 'DY', -0.01)
    model.add_node_load('N2', 'FX', 2.0, 'W')
    model.add_member_pt_load('M1', 'Fy', -5, 84, 'D')
    model.add_member_dist_load('M1', 'Fy', -0.1, -0.2, 0, 336, 'L')
    model.add_member_self_weight('FY', -1.0, 'D')
    return model


def plate_model() -> FEModel3D:
    model = base_model()
    model.add_node('P1', 0, 0, 0)
    model.add_node('P2', 50, 0, 0)
    model.add_node('P3', 50, 50, 0)
    model.add_node('P4', 0, 50, 0)
    model.add_node('P5', 100, 0, 0)
    model.add_node('P6', 100, 50, 0)
    model.add_quad('Q1', 'P1', 'P2', 'P3', 'P4', 1.0, 'Conc', kx_mod=0.8)
    model.add_plate('R1', 'P2', 'P5', 'P6', 'P3', 1.0, 'Steel', ky_mod=0.9)
    for node_name in ('P1', 'P4'):
        model.def_support(node_name, True, True, True, True, True, True)
    model.add_quad_surface_pressure('Q1', 0.01, 'D')
    model.add_plate_surface_pressure('R1', 0.02, 'L')
    return model


def rectangle_mesh_model() -> FEModel3D:
    model = base_model()
    model.add_rectangle_mesh('MSH1', 6, 48, 48, 1.0, 'Conc', start_node='A1', start_element='B1')
    model.meshes['MSH1'].add_rect_opening('O1', 12, 12, 12, 12)
    model.meshes['MSH1'].generate()
    for node in model.nodes.values():
        if node.Y == 0:
            model.def_support(node.name, True, True, True, True, True, True)
        if node.Y == 48:
            model.add_node_load(node.name, 'FX', 1.0, 'W')
    return model


def ungenerated_plate_mesh_model() -> FEModel3D:
    model = base_model()
    model.add_rectangle_mesh(
        'MSH2', 12, 48, 24, 1.0, 'Steel', element_type='Rect', plane='XZ', x_control=[6.0]
    )
    return model


def curved_mesh_model(kind: str) -> FEModel3D:
    model = base_model()
    if kind == 'annulus':
        model.add_annulus_mesh('AN', 6, 48, 12, 1, 'Conc', start_node='C1', start_element='D1')
    elif kind == 'frustrum':
        model.add_frustrum_mesh('FR', 6, 48, 24, 48, 1, 'Conc', start_node='E1', start_element='F1')
    elif kind == 'cylinder':
        model.add_cylinder_mesh('CY', 6, 24, 48, 1, 'Conc', start_node='G1', start_element='H1')
    mesh = next(iter(model.meshes.values()))
    if not mesh.is_generated:
        mesh.generate()
    for node in model.nodes.values():
        radius = math.hypot(node.X, node.Z)
        on_base = abs(radius - 48) < 1e-6 if kind == 'annulus' else abs(node.Y) < 1e-6
        if on_base:
            model.def_support(node.name, True, True, True, True, True, True)
        else:
            model.add_node_load(node.name, 'FY', -0.1, 'D')
    return model


def shear_wall_model(generate: bool) -> FEModel3D:
    model = base_model()
    model.add_shear_wall('SW1', 12, 240, 120, 8, 'Conc', plane='XY')
    wall = model.shear_walls['SW1']
    wall.add_opening('Door', 48, 0, 36, 84)
    wall.add_support(0)
    wall.add_story('Roof', 120)
    wall.add_shear('Roof', 50, 'W')
    wall.add_axial('Roof', -100, 'D')
    if generate:
        wall.generate()
    return model


def mat_foundation_model(generate: bool) -> FEModel3D:
    model = base_model()
    model.add_mat_foundation('MAT1', 24, 120, 120, 12, 'Conc', 0.1)
    model.mats['MAT1'].add_mat_pt_load([60, 60], 'FY', -50, 'D')
    if generate:
        model.mats['MAT1'].generate()
    return model


MODEL_BUILDERS = {
    'frame': frame_model,
    'plates': plate_model,
    'rectangle_mesh': rectangle_mesh_model,
    'ungenerated_plate_mesh': ungenerated_plate_mesh_model,
    'annulus_mesh': lambda: curved_mesh_model('annulus'),
    'frustrum_mesh': lambda: curved_mesh_model('frustrum'),
    'cylinder_mesh': lambda: curved_mesh_model('cylinder'),
    'shear_wall': lambda: shear_wall_model(generate=False),
    'shear_wall_generated': lambda: shear_wall_model(generate=True),
    'mat_foundation': lambda: mat_foundation_model(generate=False),
    'mat_foundation_generated': lambda: mat_foundation_model(generate=True),
}


def node_displacements(model: FEModel3D) -> dict:
    return {
        (node_name, direction, combo_name): getattr(node, direction)[combo_name]
        for node_name, node in model.nodes.items()
        for direction in ('DX', 'DY', 'DZ', 'RX', 'RY', 'RZ')
        for combo_name in model.load_combos
    }


def assert_same_results(model_a: FEModel3D, model_b: FEModel3D) -> None:
    model_a.analyze(check_statics=False)
    model_b.analyze(check_statics=False)
    results_a = node_displacements(model_a)
    results_b = node_displacements(model_b)
    assert results_a.keys() == results_b.keys()
    for key, value in results_a.items():
        assert results_b[key] == pytest.approx(value, rel=1e-9, abs=1e-12), key


@pytest.mark.parametrize("builder", MODEL_BUILDERS.values(), ids=MODEL_BUILDERS.keys())
def test_json_roundtrip(builder):
    model = builder()
    model_json = pt.dumps(model)
    rebuilt = pt.loads(model_json)
    # Serializing the rebuilt model gives the same data
    assert json.loads(pt.dumps(rebuilt)) == json.loads(model_json)
    assert_same_results(model, rebuilt)


@pytest.mark.parametrize("builder", MODEL_BUILDERS.values(), ids=MODEL_BUILDERS.keys())
def test_dict_roundtrip(builder):
    model = builder()
    model_dict = pt.dump_dict(model)
    # dump_dict output must be JSON serializable
    rebuilt = pt.load_dict(json.loads(json.dumps(model_dict)))
    assert_same_results(model, rebuilt)


def test_file_roundtrip(tmp_path):
    model = frame_model()
    filepath = tmp_path / "model.json"
    pt.to_json(model, filepath)
    assert_same_results(model, pt.from_json(filepath))


def test_steel_section_preserved():
    rebuilt = pt.loads(pt.dumps(frame_model()))
    section = rebuilt.sections['W']
    assert (section.Zy, section.Zz) == (30, 10)
    assert section.material is rebuilt.materials['Steel']


def test_member_references_model_objects():
    rebuilt = pt.loads(pt.dumps(frame_model()))
    member = rebuilt.members['M1']
    assert member.i_node is rebuilt.nodes['N1']
    assert member.material is rebuilt.materials['Steel']
    assert member.section is rebuilt.sections['W']
    assert rebuilt.members['M2'].Releases == frame_model().members['M2'].Releases
    assert rebuilt.members['M2'].Releases[5] is True  # Rzi
    assert rebuilt.springs['SP1'].load_combos is rebuilt.load_combos


def test_element_material_properties_preserved():
    rebuilt = pt.loads(pt.dumps(plate_model()))
    assert rebuilt.quads['Q1'].E == 3600
    assert rebuilt.plates['R1'].E == 29000
    assert rebuilt.quads['Q1'].kx_mod == 0.8
    assert rebuilt.plates['R1'].ky_mod == 0.9


def test_generated_mesh_is_relinked():
    rebuilt = pt.loads(pt.dumps(rectangle_mesh_model()))
    mesh = rebuilt.meshes['MSH1']
    assert type(mesh).__name__ == 'RectangleMesh'
    assert mesh.is_generated and not mesh.needs_update
    assert mesh.nodes and all(mesh.nodes[name] is rebuilt.nodes[name] for name in mesh.nodes)
    assert mesh.elements and all(mesh.elements[name] is rebuilt.quads[name] for name in mesh.elements)
    assert list(mesh.openings) == ['O1']


def test_ungenerated_mesh_stays_ungenerated():
    rebuilt = pt.loads(pt.dumps(ungenerated_plate_mesh_model()))
    mesh = rebuilt.meshes['MSH2']
    assert not mesh.is_generated
    assert not rebuilt.nodes and not rebuilt.plates
    assert rebuilt.meshes['MSH2'].x_control == [6.0]


def test_shear_wall_piers_match():
    model = shear_wall_model(generate=False)
    rebuilt = pt.loads(pt.dumps(model))
    model.analyze(check_statics=False)
    rebuilt.analyze(check_statics=False)
    piers, rebuilt_piers = model.shear_walls['SW1'].piers, rebuilt.shear_walls['SW1'].piers
    assert piers.keys() == rebuilt_piers.keys() and piers
    for pier_name in piers:
        assert rebuilt_piers[pier_name].sum_forces('D+L+W') == pytest.approx(
            piers[pier_name].sum_forces('D+L+W')
        )


def test_reads_legacy_format():
    """Files written by pynite-tools <= 0.7.0 embed nodes in elements and include sub_members."""
    legacy = pt.dump_dict(frame_model())
    for member in legacy['members'].values():
        member['sub_members'] = {}
    for section in legacy['sections'].values():
        for key in ('Zy', 'Zz', 'material_name'):
            section.pop(key)
    rebuilt = pt.load_dict(legacy)
    assert_same_results(frame_model(), rebuilt)
