from collections import Counter
import math
from typing import Optional, Union, Any
import numpy as np
import deepmerge
import pathlib
import json
from Pynite import FEModel3D


ACTION_METHODS = {
    "Fy": "shear",
    "Fz": "shear",
    "My": "moment",
    "Mz": "moment",
    "axial": "axial",
    "torque": "torque",
    "dy": "deflection",
    "dz": "deflection",
    "dx": "deflection",
}

NODE_REACTIONS = ['FX', 'FY', 'FZ', 'MX', 'MY', 'MZ']
NODE_DISPLACEMENTS = ['DX', 'DY', 'DZ', 'RX', 'RY', 'RZ']

REACTIONS = ['RxnFX', 'RxnFY', 'RxnFZ', 'RxnMX', 'RxnMY', 'RxnMZ']


def extract_node_reactions(
    model: FEModel3D, 
    load_combinations: Optional[list[str]] = None,
    results_key: Optional[str] = "node_reactions",
) -> dict[str, dict]:
    """
    Returns all node reactions from 'model'.

    'model': A solved Pynite.FEModel3D
    'load_combinations': return results only for these combinations.
        When None, returns all combinations. Default is None.
    'results_key': Optional str value used to nest your results
        more descriptively in the tree. Useful when merging
        multiple results trees. Setting to None will make
        your result tree one level shallower.
    """
    if load_combinations is None:
        load_combinations = extract_load_combinations(model)

    reaction_results = {}
    # Go through all the nodes...
    for node_name, node in model.nodes.items():
        reaction_results.setdefault(node_name, {})
        # ...and go through all reaction directions...
        inner_acc = reaction_results[node_name]
        if results_key is not None:
            reaction_results[node_name].setdefault(results_key, {})
            inner_acc = reaction_results[node_name][results_key]
        for reaction_dir in NODE_REACTIONS:
            reaction_name = f"Rxn{reaction_dir}"
            # Get the reactions...
            reactions = getattr(node, reaction_name)
            # ...and if the reactions are not all basically 0.0...
            if not (
                all([math.isclose(reaction, 0, abs_tol=1e-8) for reaction in reactions.values()])
            ):
                # Then collect them in our analysis results dictionary
                inner_acc[reaction_dir] = {
                    lc: round_to_close_integer(reaction) 
                    for lc, reaction in reactions.items()
                    if lc in load_combinations
                }
        # But if any of the nodes in the analysis results dict are empty...
        if inner_acc == {}:
            # ...then drop 'em!
            reaction_results.pop(node_name)
    return reaction_results


def extract_node_displacements(
    model: FEModel3D, 
    load_combinations: Optional[list[str]] = None,
    results_key: Optional[str] = "node_displacements",
):
    """
    Returns all node displacements from 'model'.

    'model': A solved Pynite.FEModel3D
    'load_combinations': return results only for these combinations.
        When None, returns all combinations. Default is None.
    'results_key': Optional str value used to nest your results
        more descriptively in the tree. Useful when merging
        multiple results trees. Setting to None will make
        your result tree one level shallower.
    """
    if load_combinations is None:
        load_combinations = extract_load_combinations(model)
    node_displacements = {}
    # Go through all the nodes...
    for node_name, node in model.nodes.items():
        node_displacements[node_name] = {}

        inner_acc = node_displacements[node_name]
        if results_key is not None:
            node_displacements[node_name].setdefault(results_key, {})
            inner_acc = node_displacements[node_name][results_key]
        # ...and go through all deflection directions...
        for defl_dir in NODE_DISPLACEMENTS:
            # Get the deflections...
            deflections = getattr(node, defl_dir)
            # ...and if the deflections are not all basically 0.0...
            if not (
                all([math.isclose(deflection, 0, abs_tol=1e-8) for deflection in deflections.values()])
            ):
                # Then collect them in our analysis results dictionary
                inner_acc[defl_dir] = {
                    lc: float(defl) 
                    for lc, defl in deflections.items()
                    if lc in load_combinations
                }

        # But if any of the nodes in the analysis results dict are empty...
        if inner_acc == {}:
            # ...then drop 'em!
            node_displacements.pop(node_name)

    return node_displacements


def extract_member_arrays(
    model: FEModel3D, 
    n_points: int = 1000,
    as_lists: bool = False,
    results_key: Optional[str] = "action_arrays",
    load_combinations: Optional[list[str]] = None,
    actions: Optional[list[str]] = None
) -> dict[str, dict]:
    """
    Returns all member action arrays from 'model'. Each array is of
    shape (2, n_points) where the 0th array is the "x_array" providing
    stations along the member and the 1th array is the "y_array"
    providing the analysis results.

    'model': A solved Pynite.FEModel3D
    'n_points': The number of points to use to discretize the array.
        default is 1000.
    'as_lists': If True, then the native numpy arrays returned from
        Pynite will be converted to lists. Useful when serializing
        to JSON.
    'results_key': Optional str value used to nest your results
        more descriptively in the tree. Useful when merging
        multiple results trees. Setting to None will make
        your result tree one level shallower.
    'load_combinations': return results only for these combinations.
        When None, returns all combinations. Default is None.
    'actions': return results only for these actions. When None,
        returns all actions. Default is None.
    """
    if load_combinations is None:
        load_combinations = extract_load_combinations(model)
    if actions is None:
        actions = list(ACTION_METHODS.keys())
    forces = {}
    for member_name, member in model.members.items():
        forces[member_name] = {}
        inner_acc = forces[member_name]
        if results_key is not None:
            forces[member_name].setdefault(results_key, {})
            inner_acc = forces[member_name][results_key]
        for force_direction, method_type in ACTION_METHODS.items():
            if force_direction not in actions: continue
            inner_acc.setdefault(force_direction, {})
            array_method = getattr(member, f"{method_type}_array")
            accumulator = inner_acc[force_direction]
            parent_accumulator = inner_acc
            path = force_direction

            for load_combo_name in load_combinations:
                accumulator.setdefault(load_combo_name, {})
                # hacky fix: AxialDeflection method is receiving None for a .P1, I think (Pynite error to be fixed)
                try:
                    if method_type not in ("axial", "torque"):
                        result_arrays = array_method(force_direction, combo_name=load_combo_name, n_points=n_points)
                    else:
                        result_arrays = array_method(combo_name=load_combo_name, n_points=n_points)
                except TypeError:
                    parent_accumulator[path] = None
                    continue

                if (
                    (result_arrays.dtype == "object") # An array with None (or full of None_s)
                    or
                    np.allclose(result_arrays[1], np.zeros(len(result_arrays[1])), atol=1e-8)
                ):
                    accumulator.pop(load_combo_name)
                    pass
                else:
                    if as_lists:
                        accumulator[load_combo_name] = result_arrays.tolist()
                    else:
                        accumulator[load_combo_name] = result_arrays
            if not parent_accumulator[path]:
                parent_accumulator.pop(path)
    return forces


def extract_member_envelopes(
        model: FEModel3D, 
        results_key: Optional[str] = "action_envelopes",
        load_combinations: Optional[list[str]] = None,
        actions: Optional[list[str]] = None
    ) -> dict[str, dict]:
    """
    Returns member action envelopes for all members in the 'model'.
    Each action ("Fx", "Fy", "Fz", "Mx", "My", "Mz") is enveloped
    for min/max/absmax values. If an action does not have any 
    analysis results, then its key is excluded from the result
    tree.
    'model': A solved Pynite.FEModel3D
    'results_key': Optional str value used to nest your results
        more descriptively in the tree. Useful when merging
        multiple results trees. Setting to None will make
        your result tree one level shallower.
    'load_combinations': return results only for these combinations.
        When None, returns all combinations. Default is None.
    'actions': return results only for these actions. When None,
        returns all actions. Default is None.
    """
    if load_combinations is None:
        load_combinations = extract_load_combinations(model)
    if actions is None:
        actions = list(ACTION_METHODS.keys())
    forces = {}
    for member_name, member in model.members.items():
        forces[member_name] = {}
        inner_acc = forces[member_name]
        if results_key is not None:
            forces[member_name].setdefault(results_key, {})
            inner_acc = forces[member_name][results_key]
        for force_direction, method_type in ACTION_METHODS.items():
            if force_direction not in actions: continue
            inner_acc[force_direction] = {}
            max_method = getattr(member, f"max_{method_type}")
            min_method = getattr(member, f"min_{method_type}")
            accumulator = inner_acc[force_direction]
            parent_accumulator = inner_acc
            path = force_direction

            for load_combo_name in load_combinations:
                accumulator[load_combo_name] = {}
                
                if method_type not in ("axial", "torque"):
                    max_value = float(max_method(force_direction, load_combo_name))
                    min_value = float(min_method(force_direction, load_combo_name))
                else:
                    max_value = float(max_method(load_combo_name))
                    min_value = float(min_method(load_combo_name)) 
                abs_max_value = max([abs(min_value), abs(max_value)])
                if math.isclose(max_value, 0, abs_tol=1e-8):
                    max_value = 0.
                if math.isclose(min_value, 0, abs_tol=1e-8):
                    min_value = 0.

                if min_value == max_value == 0.:
                    accumulator.pop(load_combo_name)
                    pass
                else:
                    accumulator[load_combo_name].update({f"max": round_to_close_integer(max_value)})
                    accumulator[load_combo_name].update({f"min": round_to_close_integer(min_value)})
                    accumulator[load_combo_name].update({f"absmax": round_to_close_integer(abs_max_value)})
            if not parent_accumulator[path]:
                parent_accumulator.pop(path)
    return forces
        

def extract_member_actions_by_location(
    model: FEModel3D, 
    force_extraction_locations: Optional[dict[str, list[float]]] = None,
    force_extraction_ratios: Optional[dict[str, list[float]]] = None,
    by_span: bool = False,
    results_key: Optional[str] = "action_locations",
    load_combinations: Optional[list[str]] = None,
    actions: Optional[list[str]] = None,
) -> dict[str, dict]:
    """
    Returns member actions  for all members in the 'model' at the
    locations provided. If an action does not have any 
    analysis results, then its key is excluded from the result
    tree.

    'model': A solved Pynite.FEModel3D
    'force_extraction_locations': a dict in the following format:

        {"member01": [0, 2200, 4300], "member02": [3423, 1500]}

        Where:
        - "member01" is a member name
        - The values are a list of locations on the member from which to
            extract results from.

    'force_extraction_ratios': a list or a dict in the following format:

            {
                "member01": [0.25, 0.5, 0.75], 
                "member02": [0.333, 0.666],
                ...    
            }

            -or-

            [0.25, 0.5, 0.75]

        Where:
        - "member01" is a member name
        - The values are a list of ratios on the member from which to
            extract results from. The location is calculated by 

            ratio * member.L() # length

            Whether the member is the PhysMember3D (main member)
            or a Member3D (sub member, i.e. an individual span).
        - If a dictionary is supplied, then only those specified members
            will have extracted results. If a list is supplied, then
            the extraction ratio locations will apply to all members.

    'load_combinations': return results only for these combinations.
        When None, returns all combinations. Default is None.
    'by_span': When True, will assume that the locations provided
        apply to each span for each member, instead of as 
        locations specified on the total length of the member.
    'results_key': Optional str value used to nest your results
        more descriptively in the tree. Useful when merging
        multiple results trees. Setting to None will make
        your result tree one level shallower.
    'load_combinations': return results only for these combinations.
        When None, returns all combinations. Default is None.
    'actions': return results only for these actions. When None,
        returns all actions. Default is None.
    """
    if load_combinations is None:
        load_combinations = extract_load_combinations(model)
    if force_extraction_locations is None:
        force_extraction_locations = {}
    if force_extraction_ratios is None:
        force_extraction_ratios = {}
    
    force_locations = {}
    for member_name, member in model.members.items():
        force_locations.setdefault(member_name, {})
        inner_acc = force_locations[member_name]
        parent_acc = force_locations
        path = member_name
        if results_key is not None:
            force_locations[member_name].setdefault(results_key, {})
            inner_acc = force_locations[member_name][results_key]
            parent_acc = force_locations[member_name]
            path = results_key
        if (
            member_name not in force_extraction_locations
            and isinstance(force_extraction_ratios, dict)
            and member_name not in force_extraction_ratios
        ):
            continue

        if by_span:
            inner_acc.setdefault("by_span", [])
            for sub_member in member.sub_members.values():
                inner_acc['by_span'].append(
                    collect_forces_at_location(
                        sub_member,
                        member_name,
                        force_extraction_locations, 
                        force_extraction_ratios, 
                        load_combinations,
                        actions
                    )
                )
        else:
            
            parent_acc[path] = collect_forces_at_location(
                member,
                member_name,
                force_extraction_locations,
                force_extraction_ratios,
                load_combinations,
                actions
            )
    return force_locations


def collect_forces_at_location(
    submember: "Pynite.Member3D",
    member_name: str,
    force_extraction_locations: dict, 
    force_extraction_ratios: dict | list,
    load_combinations: list[str],
    actions: Optional[list[str]] = None
) -> dict:
    acc = {}
    for loc in force_extraction_locations.get(member_name,{}):
        acc.update({loc: extract_forces_at_location(submember, loc, load_combinations)})

    if isinstance(force_extraction_ratios, list):
        ratios_to_extract = force_extraction_ratios
    elif isinstance(force_extraction_ratios, dict):
        ratios_to_extract = force_extraction_ratios.get(member_name)
    else:
        raise ValueError("force_extraction_ratios must be either a dict or list")
    
    for ratio in ratios_to_extract:
        length = submember.L()
        loc = length * ratio
        acc.update({ratio: extract_forces_at_location(submember, loc, load_combinations, actions)})
    return acc


def extract_forces_at_location(member: "Pynite.Member3D", location: float, load_combinations: list[str], actions: Optional[list[str]] = None):
    loc = location
    acc = {}
    if actions is None:
        actions = list(ACTION_METHODS.keys())
    for force_direction, method_type in ACTION_METHODS.items():
        if force_direction not in actions: continue
        acc.setdefault(force_direction, {})
        force_method = getattr(member, method_type)
        for load_combo_name in load_combinations:
            if method_type not in ("axial", "torque"):
                force_value = round_to_close_integer(force_method(force_direction, loc, load_combo_name))
            else:
                force_value = round_to_close_integer(force_method(loc, load_combo_name))
            acc[force_direction].update({load_combo_name: force_value})
        if all([force_value == 0.0 for force_value in acc[force_direction].values()]):
            acc.pop(force_direction)
    return acc


def extract_span_envelopes(
    model: FEModel3D,
    include_span_to_delta: bool = True,
    results_key: Optional[str] = "frame_span_envelopes",
    load_combinations: Optional[list[str]] = None,
    actions: Optional[list[str]] = None
) -> dict:
    """
    Returns a dict of the following shape which represents the results extract from each span of
    each member in 'model':

        {
            "member": {
                "result_key": {
                    "Action": { # Where Action is one of My, Mz, Fy, Fz, axial, torque, dx, dy 
                        "LC1": { 
                            "max": [
                                {"value": Yi, "loc_rel": xi, "span_length": li, "loc_abs": Xi, "span": Li},
                                ...
                            ],
                            "min": [
                                {"value": Yi, "loc_rel": xi, "span_length": li, "loc_abs": Xi, "span": Li},
                                ...
                            ]
                        },

                    },
                },
            },
        }
    'load_combinations': If provided, will only extract these load combinations (extract all if None)
    'actions': If provided, will only extract these actions (extract all if None)
        possible actions: {'Fy', 'Fz', 'My', 'Mz', 'axial', 'torque', 'dy', 'dx'}
    """
    if actions is None:
        actions = list(ACTION_METHODS.keys())
    max_min = ['max', 'min']
    if load_combinations is None:
        load_combinations = extract_load_combinations(model)
    n_points = 1000
    member_spans = extract_spans(model)
    span_envelopes = {}
    for member_name, sub_members in member_spans.items():
        member_length = model.members[member_name].L()
        span_envelopes.setdefault(member_name, {})
        inner_acc = span_envelopes[member_name]
        node_counts = get_node_counts(model, member_name)
        if results_key is not None:
            span_envelopes[member_name].setdefault(results_key, {})
            inner_acc = span_envelopes[member_name][results_key]
        for force_direction, method_type in ACTION_METHODS.items():
            if force_direction not in actions: continue
            inner_acc.setdefault(force_direction, {})
            for lc in load_combinations:
                inner_acc[force_direction].setdefault(lc, {})
                method_name = f"{method_type}_array"
                for envelope in max_min:
                    envelope_key = f"span_envelope_{envelope}"
                    inner_acc[force_direction][lc].setdefault(envelope_key, [])
                    length_counter = 0
                    for sub_member in sub_members:
                        method = getattr(sub_member, method_name)
                        if method_type not in ('axial', 'torque'):
                            result_arrays = method(force_direction, n_points=n_points, combo_name=lc)
                        else:
                            result_arrays = method(n_points=n_points, combo_name=lc)
                        locator_func = getattr(np, f'arg{envelope}')
                        envelope_func = getattr(np, envelope)
                        envelope_val = envelope_func(result_arrays[1])
                        envelope_idx = locator_func(result_arrays[1])
                        x_val_local = result_arrays[0][envelope_idx]
                        x_val_global = x_val_local + length_counter
                        x_length = result_arrays[0][-1]
                        length_counter += x_length
                        is_cantilevered = member_is_cantilevered(sub_member, node_counts)
                        delta = float(round_to_close_integer(envelope_val))
                        span_length = float(round_to_close_integer(sub_member.L()))
                        if delta == 0:
                            ratio = float('inf')
                        else:
                            ratio = abs(span_length / delta)
                        span_envelope = {
                            "delta": delta,
                            "loc_rel": x_val_local,
                            "span_length": span_length,
                            "loc_abs": x_val_global,
                            "length": member_length,
                            "is_cantilever": is_cantilevered
                        }
                        if include_span_to_delta:
                            span_envelope.update({"span-to-delta": ratio})
                        inner_acc[force_direction][lc][envelope_key].append(span_envelope)
    return span_envelopes


def extract_spans(model: FEModel3D) -> dict[str, list["Pynite.Member3D"]]:
    """
    Extracts the sub-members for all of the members in the 'model'
    """
    member_spans = {}
    for member_name, member in model.members.items():
        member_spans.setdefault(member_name, [])
        for name, span_member in model.members[member_name].sub_members.items():
            member_spans[member_name].append(span_member)
    return member_spans


def extract_load_combinations(model: FEModel3D) -> list[str]:
    """
    Returns a list of the load combination names used in the model
    """
    return list(model.load_combos.keys())


def member_is_cantilevered(member: "Pynite.Member3D", node_counts: Counter) -> bool:
    """
    Returns True if a member is cantilevered. False otherwise.
    """
    has_two_supports = member_has_two_supports(member)
    if has_two_supports:
        return False
    else:
        i_node = member.i_node
        j_node = member.j_node
        return (
            (node_counts[i_node.name] == 1) and not (node_has_supports(i_node))
            or
            ((node_counts[j_node.name] == 1) and not (node_has_supports(j_node)))
        )


def member_has_two_supports(member: "Pynite.Member3D") -> bool:
    """
    Returns True if 'member' two supports.
    False if it has less than two supports.
    """
    return all([
        node_has_supports(member.i_node),
        node_has_supports(member.j_node),
    ])


def member_has_reactions_each_end(member: "Pynite.Member3D") -> bool:
    """
    Returns True if the 'member' has at least one reaction one both
    ends.
    False, otherwise.
    """
    reactions_i_tally = []
    reactions_j_tally = []
    for reaction_type in REACTIONS:
        i_node = member.i_node
        j_node = member.j_node
        reactions_i = getattr(i_node, reaction_type)
        reactions_j = getattr(j_node, reaction_type)
        reactions_i_tally.append(any([round_to_close_integer(reaction) for reaction in reactions_i.values()]))
        reactions_j_tally.append(any([round_to_close_integer(reaction) for reaction in reactions_j.values()]))
    return any([reactions_i_tally]) and any([reactions_j_tally])

def node_has_supports(node: "Pynite.Node") -> bool:
    """
    Returns True if 'node' has any supports defined on it.
    False if it is a "free" node.
    """
    return any([
        node.support_DX,
        node.support_DY,
        node.support_DZ,
        node.support_RX,
        node.support_RY,
        node.support_RZ
    ])


def get_node_counts(model: FEModel3D, member_name: str) -> Counter:
    """
    Counts the number of times that a node is connected within 'member_name'
    for the purpose of identifying potentially cantilevered sub_members.
    """
    node_counts = Counter()
    for _, sub_member in model.members[member_name].sub_members.items():
        node_counts.update([sub_member.i_node.name])
        node_counts.update([sub_member.j_node.name])
    return node_counts


def round_to_close_integer(x: float, eps = 1e-7) -> float | int:
    """
    Rounds to the nearest int if it is REALLY close
    """
    if abs(abs(round(x)) - abs(x)) < eps:
        return round(x)
    else:
        return x
    

def merge_result_trees(result_trees: list[dict[str, dict]]) -> dict[str, dict]:
    """
    Merges all of the tress (dictionaries) in 'result_trees'. 

    This is different than a typical dictionary merge (e.g. a | b)
    which will merge dictionaries with different keys but will over-
    write values if two keys are the same.

    Instead, it crawls each branch of the tree and merges the data
    within each branch, no matter how deep the branches go.
    """
    acc = {}
    for result_tree in result_trees:
        acc = deepmerge.always_merger.merge(acc, result_tree)
    return acc