# Releasing CookiX

Releases are automated through GitHub Actions; a maintainer only pushes a tag.
Two one-time setup steps are required first (they need account-level access that
cannot live in the repo).

## One-time maintainer setup

### 1. PyPI Trusted Publishing (no API token)

The `Release` workflow (`.github/workflows/release.yml`) publishes via OIDC, so
no PyPI token is stored anywhere. Configure the trusted publisher once:

1. Create the `cookix` project on https://pypi.org (or use TestPyPI first).
2. Project → **Settings → Publishing → Add a trusted publisher**:
   - Owner: `CookiXDB`  ·  Repository: `CookiX`
   - Workflow filename: `release.yml`
   - Environment: `pypi`
3. In the GitHub repo, create an **Environment** named `pypi` (Settings →
   Environments) — optionally with required reviewers for a manual approval gate.

### 2. GitHub Container Registry (image publish)

The `Docker` workflow pushes to `ghcr.io/CookiXDB/CookiX` on tags using the
built-in `GITHUB_TOKEN` (no extra secret). Ensure **Settings → Actions → General
→ Workflow permissions** allows read/write packages.

## Cutting a release

1. Update `CHANGELOG.md` (move `Unreleased` → the new version).
2. Bump the version in **both** `pyproject.toml` and `src/cookix/__init__.py`.
3. Commit, then tag and push:

   ```bash
   git commit -am "Release vX.Y.Z"
   git tag -a vX.Y.Z -m "CookiX X.Y.Z"
   git push origin master --tags
   ```

On the tag, CI will: build + `twine check` + clean-venv-verify the wheel, publish
it to PyPI (Trusted Publishing), and build + smoke-test + scan + push the Docker
image to GHCR. No manual upload step.

## Versioning

See [API_STABILITY.md](API_STABILITY.md) for the SemVer policy and what counts as
the public Python / wire / on-disk API.
