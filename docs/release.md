# Release Process

This repository uses a tag-driven GitHub Actions release workflow.

## Standard release (GitHub artifacts only)

1. Ensure CI is green on the target commit.
2. Create and push a release tag:
   - `vX.Y.Z` or `release-X.Y.Z`
3. The `Release` workflow will:
   - build `sdist` and `wheel`,
   - run artifact import smoke tests,
   - create/update GitHub Release,
   - upload `dist/*.tar.gz` and `dist/*.whl`.

## Optional guarded PyPI publish

PyPI upload is disabled by default and requires explicit opt-in plus credentials.

Enable either of:

- Run `Release` via `workflow_dispatch` with `publish_to_pypi=true`, or
- Set repository variable `PUBLISH_PYPI=true` for tag-triggered runs.

And provide secret:

- `PYPI_API_TOKEN`

The workflow publishes with Twine only when guard conditions are met.

## Notes

- This project keeps enforcement CI-only (no pre-commit requirement).
- Release artifacts are always attached to GitHub Releases for auditability.

