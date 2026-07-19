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
is tagged from `main` (e.g. `v0.1.0`). **Don't use `--generate-notes` alone**:
it only lists PRs merged into `main`, and since feature PRs target `dev`, the
result is a single "release PR" bullet (this is what made v1.1.0's notes look
empty at first). Instead, write the notes from the feature PRs that landed on
`dev` since the last release:

```
git checkout main
git pull
# list what went into this release:
gh pr list --base dev --state merged --limit 20
gh release create vX.Y.Z --notes-file notes.md   # bullets per feature PR, with #NN refs
```

Group bullets under headings (e.g. "New features" / "Fixes" / "Other"), link
each to its PR number, and end with a Full Changelog compare link
(`.../compare/vPREV...vX.Y.Z`). There's still no changelog file to
hand-maintain — clear PR titles remain the source material.
