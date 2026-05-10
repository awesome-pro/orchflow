# Publishing

Orchflow uses GitHub Actions and PyPI Trusted Publishing. Trusted Publishing
uses GitHub's OIDC identity instead of long-lived PyPI API tokens.

References:

- PyPI Trusted Publishers: <https://docs.pypi.org/trusted-publishers/>
- PyPI GitHub publisher setup: <https://docs.pypi.org/trusted-publishers/adding-a-publisher/>
- GitHub tag triggers: <https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/triggering-a-workflow>

## Current Release Model

- TestPyPI publishing is manual through `publish-testpypi.yml`.
- Real PyPI publishing is tag-based through `publish-pypi.yml`.
- Real PyPI publishes only when a tag like `v0.1.1` is pushed.
- The PyPI workflow checks that the tag matches `pyproject.toml`.

Example:

```toml
version = "0.1.1"
```

must be released with:

```bash
git tag v0.1.1
git push origin v0.1.1
```

## GitHub Environments

Create these in GitHub:

`Settings -> Environments -> New environment`

- `testpypi`
- `pypi`

For `pypi`, add required reviewers if available. That gives production releases
one extra approval gate after the tag is pushed.

## TestPyPI Setup

On <https://test.pypi.org/manage/account/publishing/>, add a trusted publisher:

- Project name: `orchflow`
- Owner: `awesome-pro`
- Repository: `orchflow`
- Workflow name: `publish-testpypi.yml`
- Environment name: `testpypi`

Run:

`GitHub -> Actions -> Publish to TestPyPI -> Run workflow`

Install check:

```bash
python -m venv /tmp/orchflow-testpypi
source /tmp/orchflow-testpypi/bin/activate
python -m pip install --upgrade pip
python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  orchflow
python -c "from orchflow import Flow, step; print('testpypi ok')"
```

## Real PyPI Setup

On <https://pypi.org/manage/project/orchflow/settings/publishing/>, configure:

- Project name: `orchflow`
- Owner: `awesome-pro`
- Repository: `orchflow`
- Workflow name: `publish-pypi.yml`
- Environment name: `pypi`

If the current PyPI publisher says `Environment name: (Any)`, it will work, but
`pypi` is better because it ties the PyPI trust rule to the production GitHub
environment.

## Release Steps

1. Make code/doc changes.
2. Update `version` in `pyproject.toml`.
3. Update `__version__` in `src/orchflow/__init__.py`.
4. Run local checks:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run pyright
uv build
```

5. Commit and push to `main`.
6. Confirm CI is green on `main`.
7. Optionally run `Publish to TestPyPI`.
8. Create and push the matching tag:

```bash
git tag v0.1.1
git push origin v0.1.1
```

9. Watch `Actions -> Publish to PyPI`.
10. The workflow creates a GitHub Release from the tag after PyPI publish
    succeeds.
11. Verify the release:

```bash
python -m venv /tmp/orchflow-pypi
source /tmp/orchflow-pypi/bin/activate
python -m pip install --upgrade pip
python -m pip install orchflow==0.1.1
python -c "import orchflow; print(orchflow.__version__)"
```

## Important Rules

- PyPI does not allow overwriting an existing version.
- The Git tag does not define the package version; `pyproject.toml` does.
- Tags should match the version exactly: `0.1.1` -> `v0.1.1`.
- Do not delete and recreate public PyPI releases except in extreme cases.
