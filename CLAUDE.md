# Websites

Website projects should be presumed (unless otherwise specified) to target
eventual AWS deployment.

They should be prototyped with docker-compose.

Websites should be architected with clear APIs, accessed by static resources.
This separates concerns and improves testability.

When feasible, website projects should be self-documenting (e.g. FastAPI's
"/docs" endpoint).

# Python projects

Prefer `uv` for setting up virtualenvs and running commands. Try to stick to
a pretty recent Python version, 3.12 or 3.13 (currently).

Python projects should use pydantic models and immutable data (tuple,
frozenset, frozendict, pydantic model with frozen option) to improve clarity
and reliability.

Variable and class names should be descriptive and meaningful.

Fields in pydantic models should have meaningful description strings.

Feel free to liberally document code using Markdown-formatted multi-line
strings at the top level. These are easy to search and query, and also to
format into nice documentation.

## Docstring Formatting

Docstrings should use a Markdown-friendly format with blank lines to improve
readability when rendered. This diverges slightly from strict Google-style
docstrings for better Markdown rendering.

**Pattern to follow:**

1. Start with a brief description (one or more sentences)
2. Add a blank line after the description
3. Add "Attributes:" section header
4. Add a blank line after "Attributes:"
5. List attributes with proper indentation
6. Add a blank line after the attributes list
7. Add "Example:" section header (if applicable)
8. Add a blank line after "Example:"
9. Include example code block

**Example:**

```python
class MyClass(BaseModel):
    """
    Brief description of the class.

    Additional context or explanation can go here.

    Attributes:

        field1: Description of field1
        field2: Description of field2
        field3: Description of field3

    Example:

        >>> instance = MyClass(
        ...     field1="value1",
        ...     field2="value2"
        ... )
    """
```

The blank lines between sections help Markdown renderers (Sphinx, MkDocs,
GitHub) create proper spacing and improve readability. This pattern should be
applied consistently across all docstrings in the codebase.

## Pytest

Pytest should be used to verify functionality.

Tests should be created as early as feasible. It is a good idea to write tests
ahead of the code they are testing.

Tests should be well documented, well architected, and clear.

Test suite should be run frequently during development to provide guidance.

To the extent possible, tests should be written that do not inhibit refactoring.

