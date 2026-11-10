# DTM Mods CI

Shared checks and releases for every FS25 mod repository in DTM-Mods.

| File | What it is |
|------|------------|
| `../.github/workflows/fs25-mod.yml` | The reusable workflow. Each mod repo calls it from its own `.github/workflows/build.yml` |
| `fs25_mod.py` | Checks the mod and builds the zip (run `python fs25_mod.py --help`) |
| `../workflow-templates/fs25-mod.yml` | The `build.yml` a new mod repo starts from: Actions tab > New workflow > "DTM FS25 mod" |

## Adding a new mod repository

1. In the new repo: **Actions** > **New workflow** > **DTM FS25 mod** > **Configure** > commit.
2. Copy `.github/workflows/discord-release.yml` from another mod repo and add the
   `DISCORD_RELEASES_WEBHOOK` secret (Settings > Secrets and variables > Actions), so releases are posted.

## What goes into the zip

Files tracked by git, minus development folders (`source/`, `reference/`, `tools/`, `tests/`, `docs/`,
`previews/`, ...), files the game doesn't load (`.md`, `.blend`, `.psd`, ...) and `.png` files that have
a `.dds` of the same name. A `.modignore` file in the repo root can leave out more
(`notes/*`, `scripts/Debug.lua`) or put something back (`!docs/needed.xml`).

Same commit, same zip: the timestamps inside are fixed, so a rebuild has the same SHA-256.

## Releasing

Raise `<version>` in `modDesc.xml`, push, then push a tag with the same version:

    git tag v1.2.1.0
    git push origin v1.2.1.0

The release notes come from the section for that version in `PATCH_NOTES.md`, `RELEASE_NOTES.md` or
`CHANGELOG.md`, or from a "Changelog 1.2.1.0:" block in the English modDesc description. Without either,
GitHub lists the commits since the last release.

AutoDrive Overdrive and Logistics Hub keep their own build workflows (custom bundling and two zip names).
