"""
pynite-tools: A series of functions that enhance the capabilities of PyniteFEA.

Modules included:

- reports: Functions for bulk exporting structured analysis results
- serialize: Functions for serializing/deserializing FEModel3D objects
- combos: Functions for bulk importing load combinations
- foundation: Beams on an elastic (Winkler) foundation, and splitting distributed loads at nodes
"""

__version__ = "0.10.0"

from .reports import (
    extract_node_reactions,
    extract_node_displacements,
    extract_member_arrays,
    extract_member_envelopes,
    extract_member_actions_by_location,
    extract_span_envelopes,
    extract_load_combinations,
    merge_result_trees
)

from .serialize import (
    to_json,
    from_json,
    dump,
    dumps,
    dump_dict,
    load,
    loads,
    load_dict,
)

from .combos import (
    model_add_combos,
)

from .foundation import (
    Foundation,
    add_elastic_foundation,
    split_dist_loads,
)

from .visualize import (
    plot_model,
    Renderer
)