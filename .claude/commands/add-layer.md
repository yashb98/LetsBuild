# /add-layer — Scaffold a New Pipeline Layer

When implementing a new pipeline layer, use this command to generate the correct boilerplate.

## Usage
```
/add-layer <layer_number> <layer_name>
```

## Steps

1. Create the module directory: `letsbuild/<layer_name>/`
2. Create `__init__.py` with layer docstring
3. Create the main layer file with:
   - Async `execute(state: PipelineState) -> PipelineState` function
   - Proper imports from `letsbuild/models/`
   - Structured error handling
   - Logging with `structlog`
4. Create the test directory: `tests/<layer_name>/`
5. Create `tests/<layer_name>/conftest.py` with layer-specific fixtures
6. Create `tests/<layer_name>/test_<layer_name>.py` with stub tests
7. Register the layer in `letsbuild/pipeline/controller.py`
8. Print checklist of what to implement next
