# Project Guidelines

## Python Code Guidelines
* Always place imports at the top of the file, never inside functions (unless absolutely necessary to avoid circular imports)
* Follow PEP 8 import ordering: standard library, third-party packages, then local imports

## Tests Guidelines
* in pytest, dont use classes, always use test functions
* in parameterize, use a list of parameter names and an each case in a list, Example
```python
@pytest.parameterize(["param1", "param2"], [[1, 2], [3, 4]])
```
* In tests, before creating new models to test certain behavior, look in tests.models to see if a model already exists that matches your needs