"""
Beams on a Winkler (elastic) foundation, and a workaround for distributed loads
on physical members.

Pynite has no foundation element. `add_elastic_foundation` models one along a
member as closely spaced nodes, each with a vertical support spring of the
foundation modulus times the node's tributary length. A compression-only
foundation uses Pynite's one-way springs (direction '-'), which
`FEModel3D.analyze()` iterates, so the beam can lift off.

    import pynite_tools as pt

    foundation = pt.add_elastic_foundation(model, "F1", kf=2.5e6, direction="-")
    model.analyze()
    x, p = foundation.reaction_array(model, "Combo 1")   # force per length, up positive

`split_dist_loads` splits each member's distributed loads at the nodes along
it. Pynite 3.2.1 gives the wrong intensity to a sub-member that a trapezoidal
load runs right across (one with the load's start before it and its end after
it), so a physical member with three or more sub-members under one trapezoidal
load carries the wrong total. Split at the nodes, no sub-member has a load
that runs right across it. `add_elastic_foundation` calls it for its member.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np
from Pynite import FEModel3D

# Nodes about a 40th of the foundation's characteristic length (4 EI / kf) ** 0.25
# apart, and at least MIN_PIECES pieces along the foundation unless that would
# put them closer than an 80th of it. Lumped springs at that spacing are within
# about 0.3% of a continuous foundation, including where a compression-only
# foundation's contact ends (which can only end at a node). Much closer spacing
# makes the stiffness matrix ill-conditioned, and Pynite's stability check then
# reports a well-supported beam as unstable.
PIECES_PER_LENGTH = 40
FINEST_PIECES_PER_LENGTH = 80
MIN_PIECES = 16
MAX_PIECES = 1000

_REL_TOL = 1e-9

Direction = Optional[Literal["-", "+"]]
Axis = Literal["DY", "DZ"]


@dataclass(frozen=True)
class Foundation:
    """
    A foundation added by `add_elastic_foundation`: the member it supports,
    the nodes carrying its springs (in order along the member), their
    positions along the member and their tributary lengths.
    """

    member: str
    kf: float
    direction: Direction
    axis: Axis
    nodes: tuple[str, ...]
    x: tuple[float, ...]
    tributary: tuple[float, ...]

    def reaction_array(
        self, model: FEModel3D, combo_name: str = "Combo 1", x_array=None
    ) -> np.ndarray:
        """
        The foundation's reaction on the member, force per length, as
        [x, reaction] like Pynite's member result arrays: each spring's
        reaction over its tributary length (positive along the global axis,
        so up positive for 'DY'), at the foundation's nodes or interpolated
        to 'x_array'. Zero where the member has lifted off.
        """
        rxn = f"RxnF{self.axis[1]}"
        p = np.array(
            [getattr(model.nodes[n], rxn)[combo_name] / t for n, t in zip(self.nodes, self.tributary)]
        )
        x = np.array(self.x)
        if x_array is not None:
            x_array = np.asarray(x_array, dtype=float)
            return np.array([x_array, np.interp(x_array, x, p)])
        return np.array([x, p])


def add_elastic_foundation(
    model: FEModel3D,
    member_name: str,
    kf: float,
    x1: Optional[float] = None,
    x2: Optional[float] = None,
    direction: Direction = None,
    spacing: Optional[float] = None,
    axis: Axis = "DY",
    prefix: Optional[str] = None,
) -> Foundation:
    """
    Puts the physical member 'member_name' on a Winkler foundation of modulus
    'kf' (force per length, per length of member: a subgrade modulus times the
    member's width) from 'x1' to 'x2' along it (default: its whole length).

    'direction' is the way the springs resist, as in
    `FEModel3D.def_support_spring`: None for both ways (a linear foundation),
    '-' for negative displacements only (a compression-only foundation under
    the member, which it can lift off). 'axis' is the global direction the
    foundation acts in, 'DY' (default) or 'DZ'.

    Nodes are added about 'spacing' apart (default: a 40th of the
    characteristic length (4 E I / kf) ** 0.25, and at least 16 pieces unless
    they would be closer than an 80th of it). The
    member's own nodes and any others along it within the foundation are
    used as they are. A node that already has a support or a spring in
    'axis' cannot carry the foundation.

    Each node's spring is 'kf' times its tributary length (half the distance
    to each neighbour). The member's distributed loads are split at the
    nodes (see `split_dist_loads`). Returns a `Foundation`, whose
    `reaction_array` gives the foundation's reaction along the member.
    """
    if kf <= 0:
        raise ValueError(f"'kf' must be positive, got {kf}.")
    if direction not in (None, "-", "+"):
        raise ValueError(f"'direction' must be None, '-' or '+', got {direction!r}.")
    if axis not in ("DY", "DZ"):
        raise ValueError(f"'axis' must be 'DY' or 'DZ', got {axis!r}.")
    member = model.members[member_name]
    i_node, j_node = member.i_node, member.j_node
    start = np.array([i_node.X, i_node.Y, i_node.Z])
    vector = np.array([j_node.X, j_node.Y, j_node.Z]) - start
    length = float(np.linalg.norm(vector))
    unit = vector / length
    x1 = 0.0 if x1 is None else float(x1)
    x2 = length if x2 is None else float(x2)
    tol = _REL_TOL * length
    if not (-tol <= x1 < x2 <= length + tol):
        raise ValueError(f"The foundation runs from 0 to the member's length {length}; got {x1} to {x2}.")

    existing = _nodes_along(model, start, unit, length)
    if spacing is None:
        bending = member.material.E * (member.section.Iz if axis == "DY" else member.section.Iy)
        characteristic = (4.0 * bending / kf) ** 0.25
        pieces = math.ceil(PIECES_PER_LENGTH * (x2 - x1) / characteristic)
        fewest = min(MIN_PIECES, math.ceil(FINEST_PIECES_PER_LENGTH * (x2 - x1) / characteristic))
        pieces = min(max(pieces, fewest, 1), MAX_PIECES)
    else:
        if spacing <= 0:
            raise ValueError(f"'spacing' must be positive, got {spacing}.")
        pieces = max(math.ceil((x2 - x1) / spacing), 1)

    # Stations: an even grid, with the nodes already in the foundation in place
    # of the grid points nearest them.
    grid = np.linspace(x1, x2, pieces + 1).tolist()
    inside = {name: x for name, x in existing.items() if x1 - tol <= x <= x2 + tol}
    min_gap = 0.25 * (x2 - x1) / pieces
    stations = [(x, None) for x in grid if all(abs(x - xe) > min_gap for xe in inside.values())]
    stations += [(x, name) for name, x in inside.items()]
    stations.sort()

    prefix = prefix if prefix is not None else f"{member_name}_F"
    names, xs = [], []
    for k, (x, name) in enumerate(stations):
        if name is None:
            name = _unique(model, f"{prefix}{k}")
            X, Y, Z = start + unit * x
            model.add_node(name, float(X), float(Y), float(Z))
        names.append(name)
        xs.append(float(x))

    tributary = []
    for k, x in enumerate(xs):
        left = xs[k] - xs[k - 1] if k > 0 else 0.0
        right = xs[k + 1] - xs[k] if k < len(xs) - 1 else 0.0
        tributary.append(0.5 * (left + right))

    for name, t in zip(names, tributary):
        node = model.nodes[name]
        if getattr(node, f"support_{axis}") or getattr(node, f"spring_{axis}")[0] is not None:
            raise ValueError(
                f"Node '{name}' already has a support or a spring in {axis}, so it cannot "
                f"also carry the foundation; end the foundation before it."
            )
        model.def_support_spring(name, axis, kf * t, direction)

    split_dist_loads(model, member_name)
    model.solution = None
    return Foundation(member_name, float(kf), direction, axis, tuple(names), tuple(xs), tuple(tributary))


def split_dist_loads(model: FEModel3D, member_name: Optional[str] = None) -> None:
    """
    Splits the distributed loads of the physical member 'member_name' (or of
    every member) at the nodes along it, so that each piece of a load lies
    on one sub-member. The loads carried are unchanged; this works around
    Pynite 3.2.1's wrong intensity on a sub-member that a trapezoidal load
    runs right across (see the module docstring).
    """
    names = [member_name] if member_name is not None else list(model.members)
    for name in names:
        member = model.members[name]
        i_node, j_node = member.i_node, member.j_node
        start = np.array([i_node.X, i_node.Y, i_node.Z])
        vector = np.array([j_node.X, j_node.Y, j_node.Z]) - start
        length = float(np.linalg.norm(vector))
        cuts = sorted(_nodes_along(model, start, vector / length, length).values())
        tol = _REL_TOL * length
        split = []
        for load in member.DistLoads:
            direction, w1, w2, a, b, case, self_weight = load
            inner = [x for x in cuts if a + tol < x < b - tol]
            if not inner:
                split.append(load)
                continue
            w = lambda x: w1 + (w2 - w1) * (x - a) / (b - a)
            edges = [a] + inner + [b]
            for lo, hi in zip(edges, edges[1:]):
                split.append((direction, w(lo), w(hi), lo, hi, case, self_weight))
        member.DistLoads = split
    model.solution = None


def _nodes_along(model: FEModel3D, start: np.ndarray, unit: np.ndarray, length: float) -> dict[str, float]:
    """{node name: distance along the line} for the model's nodes on the segment from 'start'."""
    tol = 1e-6 * length
    out = {}
    for name, node in model.nodes.items():
        offset = np.array([node.X, node.Y, node.Z]) - start
        x = float(offset @ unit)
        if -tol <= x <= length + tol and np.linalg.norm(offset - x * unit) <= tol:
            out[name] = min(max(x, 0.0), length)
    return out


def _unique(model: FEModel3D, name: str) -> str:
    candidate, k = name, 1
    while candidate in model.nodes:
        candidate = f"{name}_{k}"
        k += 1
    return candidate
