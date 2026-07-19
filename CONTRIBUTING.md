# Contributing / Maintainer notes

## Workflow

All work happens on feature branches cut from `dev`, squash-merged into
`dev` via PR (one clean commit per feature), then `dev` is opened as a
release PR into `main` — nothing gets pushed to `main` directly.

**Merge strategy matters:** squash is only for feature → `dev` PRs. The
release PR (`dev` → `main`) must use a **merge commit** — by then every
commit on `dev` is already a curated one-per-feature commit, and squashing
again would collapse the release into one blob and permanently desync the
two branches' histories (the "N commits ahead of main" banner never resets).

```
git checkout -b feat/thing dev
# ... commit changes ...
gh pr create --base dev --head feat/thing   # squash-merge this
gh pr create --base main --head dev         # MERGE-COMMIT this (not squash)
git checkout main && git pull
gh release create vX.Y.Z --notes-file notes.md
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
