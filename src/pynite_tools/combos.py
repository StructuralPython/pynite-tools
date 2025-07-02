from copy import deepcopy
from typing import Optional
from Pynite import FEModel3D

def model_add_combos(load_combos: list[dict[str, dict[str, float]]], model: FEModel3D, as_copy: bool = False) -> Optional[FEModel3D]:
    """
    Bulk adds a list of load combination dictionaries into the 'model' all at once.

    'load_combos': a list of load combination elements, each in the following format:
        {
            "name": "load_combo_name",
            "factors": {
                "case_1_name": 1.0,
                "case_2_name": 1.0,
                ...
            }
        }
    'model': A Pynite.FEModel3D
    'as_copy': If True, will return a copy of the FEModel3D with the load combos applied.
        If False, returns None and modifies the FEModel3D in place. Default is False.
    """
    if as_copy:
        model = deepcopy(model)
    for load_combo in load_combos:
        model.add_load_combo(**load_combo)
    if as_copy:
        return model