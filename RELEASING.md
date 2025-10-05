# Releasing

This project uses semantic version tags (`vX.Y.Z`). Pushing a tag triggers the release workflow which:
1. Builds sdist & wheel (`python -m build`).
2. Extracts the matching section from `CHANGELOG.md`.
3. Creates a GitHub Release with notes and attaches artifacts.

## Prerequisites
- Ensure `CHANGELOG.md` has a section `## [X.Y.Z] - YYYY-MM-DD` for the version.
- CI on main is green.
- No uncommitted changes.

## Steps
```bash
# 1. Update CHANGELOG: move Unreleased entries under new version header with date.
# 2. Commit the changelog update.
git add CHANGELOG.md
git commit -m "chore(release): prepare v0.1.0"

# 3. Tag & push
git tag v0.1.0
git push origin v0.1.0
```
The GitHub Action will handle release note creation. If the changelog section isn't found, update the section naming and re-tag (delete & force push if needed).

## After Release
- Open a new `## [Unreleased]` section at top of `CHANGELOG.md` if the workflow removed or modified it.
- (Optional) Publish to PyPI or container registry once distribution strategy is finalized.

## Future Enhancements
- Automated version bump PR via a release bot.
- SBOM generation & signature.
- PyPI publish with OIDC trusted publishing.
