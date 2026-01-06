# PyPI Publication Preparation

This document summarizes the changes made to prepare the package for PyPI publication.

## Changes Made

### 1. Package Name and Structure
- **Package name**: Changed from `med-graph-schema` to `med-lit-schema` (matches GitHub repo)
- **Python package**: Changed from `schema` to `med_lit_schema`
- **Version**: Set to `0.1.0` (first release)

### 2. Updated All Import References
- All markdown files now use `from med_lit_schema.*` instead of `from schema.*`
- All test files updated to use `med_lit_schema`
- All Python docstrings updated
- File path references in documentation updated

### 3. PyPI Metadata Added
- Added license (MIT)
- Added author information
- Added keywords for discoverability
- Added classifiers (Python versions, topics, development status)
- Added project URLs (homepage, repository, issues)

### 4. Files Created
- `LICENSE` - MIT License file
- `MANIFEST.in` - Includes documentation and license in distribution

### 5. Updated `.gitignore`
- Added build artifacts (`dist/`, `build/`, `*.egg-info/`)

## Before Publishing to PyPI

### Required Actions

1. **Update Author Email**
   - Edit `pyproject.toml` line 9
   - Change `wware@example.com` to your actual email address

2. **Test Installation Locally**
   ```bash
   # Build the package
   uv build
   
   # Test installation from local wheel
   pip install dist/med_lit_schema-0.1.0-py3-none-any.whl
   
   # Verify imports work
   python -c "from med_lit_schema.entity import Disease; print('OK')"
   ```

3. **Test on TestPyPI First** (Recommended)
   ```bash
   # Install twine if needed
   pip install twine
   
   # Upload to TestPyPI
   twine upload --repository testpypi dist/*
   
   # Test installation from TestPyPI
   pip install --index-url https://test.pypi.org/simple/ med-lit-schema
   ```

4. **Verify Package Contents**
   - Check that all necessary files are included
   - Verify documentation files are present
   - Ensure LICENSE is included

### Optional but Recommended

1. **Add Long Description**
   - Consider adding a longer description in `pyproject.toml`
   - Or use `readme = "README.md"` (already done)

2. **Version Management**
   - Consider using a version management tool (e.g., `bump2version`)
   - Or manually update version in `pyproject.toml` for each release

3. **CI/CD for Publishing**
   - Consider adding GitHub Actions workflow for automated publishing
   - Example: Publish to PyPI on tag push

4. **Documentation**
   - Consider publishing documentation to Read the Docs or similar
   - Update README with installation instructions:
     ```bash
     pip install med-lit-schema
     ```

## Publishing to PyPI

Once ready:

```bash
# Build the package
uv build

# Upload to PyPI (requires PyPI account and API token)
twine upload dist/*

# Or use uv publish (if available)
uv publish
```

## Post-Publication

1. **Verify Installation**
   ```bash
   pip install med-lit-schema
   python -c "from med_lit_schema.entity import Disease; print('Success!')"
   ```

2. **Update README**
   - Add installation instructions
   - Update any remaining references

3. **Create Release on GitHub**
   - Tag the release: `git tag v0.1.0`
   - Push tag: `git push origin v0.1.0`
   - Create GitHub release with release notes

## Package Structure

The package will be installed as:
```
med_lit_schema/
  ├── base.py
  ├── entity.py
  ├── entity_sqlmodel.py
  ├── relationship.py
  ├── relationship_sqlmodel.py
  ├── mapper.py
  ├── evidence_sqlmodel.py
  ├── paper_sqlmodel.py
  ├── setup_database.py
  └── verify_db_setup.py
```

Users will import like:
```python
from med_lit_schema.entity import Disease, Gene, Drug
from med_lit_schema.relationship import Treats
from med_lit_schema.base import PredicateType
```

## Version Number

Current version: `0.1.0`

This is appropriate for a first release. Future versions should follow semantic versioning:
- `0.1.x` - Bug fixes
- `0.2.x` - New features (backward compatible)
- `1.0.0` - First stable release
- `1.x.x` - Major version increments for breaking changes
