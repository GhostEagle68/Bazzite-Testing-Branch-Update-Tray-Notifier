# Contributing / Maintainer notes

## Workflow

All work happens on `dev`, opened as a pull request into `main` — nothing
gets pushed to `main` directly. Once a PR is merged, `main` is what gets
tagged for a release:

```
git checkout dev
# ... commit changes ...
git push origin dev
gh pr create --base main --head dev --title "..." --body "..."
# after merging:
gh pr merge --squash
git checkout main && git pull
gh release create vX.Y.Z --generate-notes
```

## Releases

Each [release](https://github.com/GhostEagle68/bazzite-testing-notifier/releases)
is tagged from `main` (e.g. `v0.1.0`) with auto-generated release notes
summarizing what changed since the previous tag:

```
git checkout main
git pull
gh release create v0.1.0 --generate-notes
```

`--generate-notes` builds the changelog from merged PR titles/commits since
the last tag automatically, so there's no changelog file to hand-maintain —
just write clear commit/PR titles going in.
