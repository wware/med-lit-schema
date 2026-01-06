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
   uv run python -c "from med_lit_schema.entity import Disease; print('OK')"
   ```

3. **Test on TestPyPI First** (Recommended)

   **Get TestPyPI API Token:**
   1. Create account at https://test.pypi.org/account/register/ (separate from PyPI)
   2. Log in to https://test.pypi.org/manage/account/
   3. Go to "API tokens" section
   4. Click "Add API token"
   5. Give it a name (e.g., "med-lit-schema-upload")
   6. Set scope to "Entire account" (or specific project)
   7. Copy the token (you'll only see it once!)

   **Upload to TestPyPI:**
   ```bash
   # Upload to TestPyPI (will prompt for username and token)
   uv run twine upload --repository testpypi dist/*
   # Username: __token__
   # Password: <paste your API token here>

   # Test installation from TestPyPI
   # Note: Use --extra-index-url so dependencies come from regular PyPI
   pip install --extra-index-url https://test.pypi.org/simple/ med-lit-schema

   # Or with uv:
   uv add med-lit-schema --extra-index-url https://test.pypi.org/simple/
   ```

   **Note:** TestPyPI requires a separate account from PyPI. You can use the same username/email, but you need to register separately.

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

**Get Twine:**
```bash
uv add twine
```

**Get PyPI API Token:**
1. Create account at https://pypi.org/account/register/ (if you don't have one)
2. Log in to https://pypi.org/manage/account/
3. Go to "API tokens" section
4. Click "Add API token"
5. Give it a name (e.g., "med-lit-schema-production")
6. Set scope to "Entire account" (or specific project: `med-lit-schema`)
7. Copy the token (you'll only see it once!)

**Upload to PyPI:**
```bash
# Build the package
uv build
# Upload to PyPI (will prompt for username and token)
uv run twine upload dist/*
# Username: __token__
# Password: <paste your PyPI API token here>
```

**Using API Token:**
- Username should always be: `__token__`
- Password is your API token (starts with `pypi-`)
- You can also set these as environment variables:
  ```bash
  export TWINE_USERNAME=__token__
  export TWINE_PASSWORD=pypi-your-token-here
  uv run twine upload dist/*
  ```

## Post-Publication

1. **Verify Installation**
   ```bash
   cd ../some-other-project
   # For TestPyPI (use --extra-index-url so dependencies come from regular PyPI):
   uv add med-lit-schema --extra-index-url https://test.pypi.org/simple/
   # For production PyPI:
   # uv add med-lit-schema
   uv run python -c "from med_lit_schema.entity import Disease; print('Success')"
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
