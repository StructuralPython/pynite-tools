# Pynite Tools

> Super-charge your Pynite workflows

PyniteFEA is excellent and it is generally design-ready. The functions in this package give Pynite powers it does not currently have (such as bulk results export and exporting analysis-ready models to JSON).

These are opinionated tools that are not intended to be part of the core PyniteFEA package but instead enhance the eco-system around Pynite for production-level engineering work.

Modules included:

- `visualize`: Plot your `FEModel3D` using plotly (previously in the `pynite_plotly` package)
- `reports`: Quickly export node and member results in structured dictionaries (previously in the `pynite_reporting` package)
- `serialize`: Export and import `FEModel3D` objects to JSON
- `combos`: Convenience function for bulk-adding load combinations to `FEModel3D` objects


## Installation

```
pip install pynite-tools
```

## Dependencies

- Python >= 3.11
- `PyniteFEA` >= 2.1.0 (tested through 3.2.1)
- `numpy` >= 2.0.0
- `deepmerge` >= 2.0.0
- `pydantic` >= 2.0.0


## Examples: `visualize`

```python
from Pynite import FEModel3D
import pynite_tools.visualize as pv

model = FEModel3D(...) # Build your model

# pv.plot_model is the "express" function
pv.plot_model(model, combo_name="LC1")

# pv.Renderer is a class that gives you detailed control of the plot
model_renderer = pv.Renderer(model, combo_name="LC1")

## For example...
model_renderer.annotation_size = 5
model_renderer.window_width = 1200
model_renderer.window_height = 1000

## Now render the model
model_renderer.render_model()
```


## Examples: `reports`

```python
from Pynite import FEModel3D
import pynite_tools.reporting as pr

model = FEModel3D(...) # Build your model here

# Selected load combinations in your model
lcs = [
    # 'LC1', 
    'LC2',
    'LC3',
    # 'LC4', 
    # 'LC5',
]

# All the below functions optionally take a list of load combos
# so you can select which combos to extract

## Additionally, each function accepts a results_key parameter.
## This optional parameter is set to a default str value, unique for each function.
## When you set the results_key=None, then your results tree will be one level shallower.

# Return reactions for all supports, all load combos
reactions = pr.extract_node_reactions(
    model,
    # load_combinations=lcs,
    # results_key=None
)

# Returns all node deflections for all load combos
node_displacements = pr.extract_node_displacements(
    model,
    # load_combinations=lcs,
    # results_key=None
)

# Return force arrays for all members, all load combos
force_arrays = pr.extract_member_arrays(
    model,
    # n_points=1000,
    # as_lists=False,
    # load_combinations=lcs,
    # results_key=None
)

# Return force min/max/absmax envelope for all members, all load combos
# Values will not necessarily be at concurrent locations
forces_minmax = pr.extract_member_envelopes(
    model,
    # load_combinations=lcs,
    # results_key=None
)

# Return force min/max envelope for each span in all members, all load combos
forces_minmax_spans = pr.extract_span_envelopes(
    model,
    # load_combinations=lcs,
    # results_key=None
)

# Return forces for all load combos at specific locations along the global member length
forces_at_locations = pr.extract_member_actions_by_location(
    model, 
    force_extraction_locations={"Member01": [0, 2000, 3600]},
    # load_combinations=lcs,
    # results_key=None
)

# Return forces for all load combos at 1/4 points for *each span* of the given members
forces_at_location_ratios = pr.extract_member_actions_by_location(
    model, 
    force_extraction_ratios={"Member05": [0.25, 0.5, 0.75]}, 
    by_span=True,
    # load_combinations=lcs,
    # results_key=None
    )

# Merge result trees into a single tree for serializing to JSON
merged_tree = pr.merge_result_trees([force_arrays, forces_minmax, forces_at_locations])
```

## Examples: `serialize`

```python
import pynite_tools.serialize as ps
from Pynite import FEModel3D

model = FEModel3D(...) # Build your model

# Dumping/serializing functions

## ps.dump
with open('model.json', 'w') as file:
    ps.dump(model, file)

## ps.dumps
json_str = ps.dumps(model)

## ps.dump_dict
json_dict = ps.dump_dict(model)

## ps.to_json (same as ps.dump but in one line)
ps.to_json(model, "model.json")


# Loading/de-serializing functions

## ps.load
with open('model.json', 'r') as file:
    remodel = ps.load(file)

## ps.loads
remodel = ps.loads(json_str)

## ps.load_dict
remodel = ps.load_dict(json_dict)

## ps.from_json (same as ps.load but in one line)
remodel = ps.from_json("model.json")

### Analyze your model!
remodel.analyze(check_statics=True)

### Confirm you get the same results from your original model!
model.analyze(check_statics=True)
```

### What gets serialized

The JSON contains the model's *input* data: nodes (supports, support springs, enforced
displacements, nodal loads), materials, sections (including steel sections), physical members
(releases, rotation, tension/compression-only, point and distributed loads), springs, quads,
plates (with surface pressures), load combinations, and meshes, shear walls and mat foundations.

Meshes (`RectangleMesh`, `AnnulusMesh`, `FrustrumMesh`, `CylinderMesh`), shear walls and mat
foundations are stored as the definition used to create them, so a model that has not been
generated yet will be generated by Pynite on `analyze()`, exactly like the original. If they were
already generated, their nodes and elements are re-linked to the de-serialized model.

It also carries a `metadata` block naming the library the model is for, that library's version
and the package and version that wrote it:

```json
"metadata": {
  "library": "Pynite",
  "library_version": "3.2.1",
  "generator": "pynite-tools",
  "generator_version": "0.10.0"
}
```

pycba-tools writes the same block (with `"pycba"` and `"pycba-tools"`). The block is optional
when loading, so older files still load, but a model whose `library` isn't `"Pynite"` is refused.

Analysis results are not serialized: re-run the analysis after loading.

## Examples: `combos`

```python
import json
from Pynite import FEModel3D
import pynite_tools.combos as pc

model = FEModel3D(...)

# Load up some load combinations on disk
with open("load_combo_library/current_combos.json", 'r') as file:
    load_combos = json.load(file)

# Add combos by modifying the model in place
pc.model_add_combos(load_combos, model)

# Add combos by returning a copy of the modified model
model = pc.model_add_combos(load_combos, model, as_copy=True)
```



## Examples: `foundation`

Pynite has no foundation element. `add_elastic_foundation` puts a member on a Winkler foundation
of modulus `kf` (force per length, per length of member: a subgrade modulus times the member's
width) as closely spaced nodes, each with a vertical spring of `kf` times its tributary length.

```python
from Pynite import FEModel3D
import pynite_tools as pt

model = FEModel3D(...)   # a member "F1" along X, loaded in Y

foundation = pt.add_elastic_foundation(
    model, "F1",
    kf=2.5e6,          # 5 MPa/m under a 0.5 m wide footing, in N/m/m
    direction="-",     # compression only: the member can lift off (None: both ways)
    # x1=..., x2=...   # part of the member (default: all of it)
    # spacing=...      # default: a 40th of the characteristic length (4 E I / kf) ** 0.25
)
model.analyze()        # iterates the compression-only springs

x, p = foundation.reaction_array(model, "Combo 1")   # force per length, up positive
```

- The member's own nodes, and any others along it within the foundation, are used as they
  are. A node with a support or a spring in the foundation's direction can't also carry it.
- The springs are ordinary Pynite support springs, so the model serializes and loads with them.
- At the default spacing, deflections are within about 0.3% of a continuous foundation (checked
  against pycba-tools' foundation elements), including where a compression-only foundation's
  contact ends. Much closer spacing makes the stiffness matrix ill-conditioned, and Pynite's
  stability check may then report a well-supported beam as unstable.
- Unequal stiffnesses in tension and compression can't be modelled: Pynite allows one spring per
  direction at a node. pycba-tools' `kf_tension` can.

### `split_dist_loads`

In Pynite 3.2.1 a trapezoidal distributed load gives the wrong intensity to a sub-member it runs
right across (one with the load's start before it and its end after it). A physical member with
three or more sub-members under one trapezoidal load then carries the wrong total: 93.0 kN
instead of 87.5 kN on a six-span beam. `split_dist_loads(model, member_name=None)` splits each
distributed load at the nodes along its member, so no piece runs right across a sub-member.
`add_elastic_foundation` does this for its member.

```python
pt.split_dist_loads(model)        # every member, before model.analyze()
```
