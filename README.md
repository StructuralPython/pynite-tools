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
- `PyniteFEA` >= 1.1.0
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


