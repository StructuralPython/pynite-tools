import pytest
from Pynite import FEModel3D

import pynite_tools as pt


@pytest.fixture
def torsion_beam() -> FEModel3D:
    """A two-span beam with gravity and torsional loads."""
    model = FEModel3D()
    model.add_node('N1', 0, 0, 0)
    model.add_node('N2', 120, 0, 0)
    model.add_node('N3', 240, 0, 0)
    model.add_material('Steel', 29000, 11200, 0.3, 2.836e-4)
    model.add_section('S', 20, 100, 150, 250)
    model.add_member('M1', 'N1', 'N3', 'Steel', 'S')
    model.def_support('N1', True, True, True, True, False, False)
    model.def_support('N2', False, True, True, False, False, False)
    model.def_support('N3', False, True, True, True, False, False)
    model.add_member_pt_load('M1', 'Fy', -5, 60, 'D')
    model.add_member_pt_load('M1', 'Mx', 10, 60, 'D')
    model.add_member_pt_load('M1', 'Fy', -8, 180, 'L')
    model.add_load_combo('1.4D', {'D': 1.4})
    model.add_load_combo('1.2D+1.6L', {'D': 1.2, 'L': 1.6})
    model.analyze(check_statics=False)
    return model


def test_extract_span_envelopes_all_actions(torsion_beam):
    # Previously raised TypeError because Member3D.torque_array returns None values
    envelopes = pt.extract_span_envelopes(torsion_beam, n_points=50)
    spans = envelopes['M1']['frame_span_envelopes']
    assert set(spans) == {'Fy', 'Fz', 'My', 'Mz', 'axial', 'torque', 'dy', 'dz', 'dx'}
    assert len(spans['torque']) == 2


def test_extract_span_envelopes_torque_values(torsion_beam):
    envelopes = pt.extract_span_envelopes(torsion_beam, actions=['torque'], n_points=50)
    torque_spans = envelopes['M1']['frame_span_envelopes']['torque']
    sub_members = list(torsion_beam.members['M1'].sub_members.values())
    for idx, sub_member in enumerate(sub_members):
        for combo_name in torsion_beam.load_combos:
            assert torque_spans[idx]['delta_max'][combo_name] == pytest.approx(
                sub_member.max_torque(combo_name)
            )
            assert torque_spans[idx]['delta_min'][combo_name] == pytest.approx(
                sub_member.min_torque(combo_name)
            )
    # The applied torque is non-trivial, so this is a meaningful comparison
    assert any(abs(span['delta_abs_max']) > 0 for span in torque_spans.values())


def test_submember_torque_array_has_no_none(torsion_beam):
    sub_member = next(iter(torsion_beam.members['M1'].sub_members.values()))
    result = pt.reports.submember_torque_array(sub_member, n_points=10, combo_name='1.4D')
    assert result.shape == (2, 10)
    assert result.dtype == float
