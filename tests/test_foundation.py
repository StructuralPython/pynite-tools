"""
pynite_tools.foundation: beams on a Winkler foundation as closely spaced
support springs, and splitting distributed loads at the nodes along a member.
"""
import numpy as np
import pytest
from Pynite import FEModel3D

import pynite_tools as pt

EI = 2e8  # N m^2 (E with I = 1)
KF = 2.5e6  # N/m per m
LAMBDA = (KF / (4 * EI)) ** 0.25  # Hetényi's lambda, 1/m


def beam(nodes=(0.0, 6.0), supports=None) -> FEModel3D:
    """A beam along X, loaded in Y; 'supports' lists the nodes restrained in DY."""
    model = FEModel3D()
    supports = supports or ()
    for i, x in enumerate(nodes):
        model.add_node(f"N{i}", x, 0, 0)
        model.def_support(f"N{i}", i == 0, i in supports, True, True, True, False)
    model.add_material("m", EI, EI, 0.3, 0)
    model.add_section("s", 1, 1, 1, 1)
    model.add_member("B1", "N0", f"N{len(nodes) - 1}", "m", "s")
    model.add_load_combo("D", {"D": 1.0})
    return model


def deflection(model, x):
    return np.array([model.members["B1"].deflection("dy", xi, "D") for xi in np.atleast_1d(x)])


def total(foundation, model):
    x, p = foundation.reaction_array(model, "D")
    return float(np.dot(p, foundation.tributary))


# --- Foundations ------------------------------------------------------------------


def test_linear_foundation_matches_hetenyi():
    """An infinite beam under a point load: w = P lambda / 2k."""
    L = 16 / LAMBDA
    model = beam((0.0, L))
    model.add_member_pt_load("B1", "Fy", -100e3, L / 2, "D")
    pt.add_elastic_foundation(model, "B1", KF)
    model.analyze(check_statics=False)
    assert -deflection(model, L / 2)[0] == pytest.approx(100e3 * LAMBDA / (2 * KF), rel=2e-3)


def test_compression_only_lifts_off():
    linear, contact = beam(), beam()
    for model, direction in ((linear, None), (contact, "-")):
        model.add_member_pt_load("B1", "Fy", -100e3, 0.5, "D")
        foundation = pt.add_elastic_foundation(model, "B1", KF, direction=direction)
        model.analyze(check_statics=False)
        model.foundation = foundation
    x, p = contact.foundation.reaction_array(contact, "D")
    assert (p >= 0).all()  # Never pulls the beam down.
    assert p[-1] == 0.0  # The far end has lifted off...
    assert total(contact.foundation, contact) == pytest.approx(100e3, rel=1e-6)
    assert deflection(contact, 6.0)[0] > deflection(linear, 6.0)[0] > 0  # ...further than the linear beam's.
    _, p_linear = linear.foundation.reaction_array(linear, "D")
    assert (p_linear < 0).any()


def test_spring_stiffness_is_kf_times_tributary_length():
    model = beam()
    foundation = pt.add_elastic_foundation(model, "B1", KF, spacing=0.5)
    assert len(foundation.nodes) == 13
    assert foundation.tributary[0] == pytest.approx(0.25)
    assert foundation.tributary[1] == pytest.approx(0.5)
    assert sum(foundation.tributary) == pytest.approx(6.0)
    assert model.nodes[foundation.nodes[1]].spring_DY == [pytest.approx(KF * 0.5), None, True]


def test_default_spacing_follows_the_characteristic_length():
    model = beam()
    foundation = pt.add_elastic_foundation(model, "B1", KF)
    characteristic = (4 * EI / KF) ** 0.25
    assert np.diff(foundation.x).max() == pytest.approx(characteristic / 40, rel=0.05)


def test_nodes_along_the_member_are_used():
    model = beam((0.0, 2.3, 6.0))
    foundation = pt.add_elastic_foundation(model, "B1", KF, spacing=0.5)
    assert foundation.nodes[0] == "N0" and foundation.nodes[-1] == "N2"
    assert "N1" in foundation.nodes
    assert foundation.x[foundation.nodes.index("N1")] == pytest.approx(2.3)
    assert model.nodes["N1"].spring_DY[0] is not None


def test_a_supported_node_cannot_carry_the_foundation():
    model = beam(supports=(0,))
    with pytest.raises(ValueError, match="already has a support"):
        pt.add_elastic_foundation(model, "B1", KF)


def test_part_of_the_member():
    model = beam((0.0, 6.0), supports=(0,))
    model.add_member_pt_load("B1", "Fy", -50e3, 5.0, "D")
    foundation = pt.add_elastic_foundation(model, "B1", KF, x1=3.0, x2=6.0)
    assert foundation.x[0] == pytest.approx(3.0) and foundation.x[-1] == pytest.approx(6.0)
    model.analyze(check_statics=False)
    support = model.nodes["N0"].RxnFY["D"]
    assert support + total(foundation, model) == pytest.approx(50e3, rel=1e-6)


def test_reaction_array_interpolates():
    model = beam()
    model.add_member_dist_load("B1", "Fy", -10e3, -10e3, 0.0, 6.0, "D")
    foundation = pt.add_elastic_foundation(model, "B1", KF)
    model.analyze(check_statics=False)
    x, p = foundation.reaction_array(model, "D", x_array=[0.0, 1.5, 3.0])
    np.testing.assert_allclose(x, [0.0, 1.5, 3.0])
    np.testing.assert_allclose(p, 10e3, rtol=1e-4)  # A uniform load settles the beam evenly.


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"kf": 0.0}, "must be positive"),
        ({"kf": KF, "direction": "down"}, "'direction'"),
        ({"kf": KF, "axis": "DX"}, "'axis'"),
        ({"kf": KF, "x1": 4.0, "x2": 2.0}, "runs from 0"),
        ({"kf": KF, "spacing": -1.0}, "'spacing'"),
    ],
)
def test_invalid_foundations(kwargs, message):
    with pytest.raises(ValueError, match=message):
        pt.add_elastic_foundation(beam(), "B1", **kwargs)


def test_a_foundation_round_trips():
    model = beam((0.0, 2.5, 6.0))
    model.add_member_dist_load("B1", "Fy", -5e3, -30e3, 0.5, 5.5, "D")
    model.add_member_pt_load("B1", "Fy", -60e3, 1.0, "D")
    pt.add_elastic_foundation(model, "B1", KF, direction="-")
    loaded = pt.load_dict(pt.dump_dict(model))
    model.analyze(check_statics=False)
    loaded.analyze(check_statics=False)
    x = np.linspace(0, 6, 25)
    np.testing.assert_allclose(deflection(loaded, x), deflection(model, x), rtol=1e-9, atol=1e-12)


# --- Distributed loads -------------------------------------------------------------


def six_spans() -> FEModel3D:
    model = beam(tuple(float(x) for x in range(7)), supports=tuple(range(7)))
    model.add_member_dist_load("B1", "FY", -5e3, -30e3, 0.5, 5.5, "D")
    return model


def test_pynite_trapezoid_across_sub_members():
    """
    The bug split_dist_loads works around: if this starts passing exactly,
    Pynite has fixed it.
    """
    model = six_spans()
    model.analyze(check_statics=False)
    carried = sum(model.nodes[f"N{i}"].RxnFY["D"] for i in range(7))
    if carried == pytest.approx(87.5e3, rel=1e-9):
        pytest.skip("Pynite carries a trapezoid across sub-members correctly")
    assert carried != pytest.approx(87.5e3, rel=1e-3)


def test_split_dist_loads_carries_the_load():
    model = six_spans()
    pt.split_dist_loads(model)
    loads = model.members["B1"].DistLoads
    assert len(loads) == 6  # 0.5-1, 1-2, ..., 5-5.5
    assert loads[0][3:5] == (0.5, 1.0) and loads[-1][3:5] == (5.0, 5.5)
    assert loads[1][1:3] == (pytest.approx(-7.5e3), pytest.approx(-12.5e3))
    model.analyze(check_statics=False)
    carried = sum(model.nodes[f"N{i}"].RxnFY["D"] for i in range(7))
    assert carried == pytest.approx(87.5e3, rel=1e-9)


def test_split_dist_loads_keeps_loads_within_one_sub_member():
    model = beam((0.0, 3.0, 6.0))
    model.add_member_dist_load("B1", "Fy", -1e3, -2e3, 0.5, 2.5, "D", self_weight=True)
    before = list(model.members["B1"].DistLoads)
    pt.split_dist_loads(model, "B1")
    assert model.members["B1"].DistLoads == before
