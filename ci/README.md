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

To try a release first: **Actions** > **Build** > **Run workflow**, enter the tag (`v1.2.1.0`). The run checks
the tag, builds the zip and writes the release page into its log, but publishes nothing.

## Settings

Every mod repo has the same `build.yml`; only the settings under `with:` differ. All are optional.

| Setting | Used by | What it does |
|---------|---------|--------------|
| `zip-name` | Box Truck, Brandt | The mod's real zip name when it differs from the repo name. Never change it for a released mod: savegames know the mod by it. |
| `max-files` | Courseplay, AutoDrive | `0` turns off the GIANTS ModHub 128-file limit |
| `test-command` | PRX9000, AutoDrive | Extra tests, run after the build |
| `build-command` | AutoDrive, Logistics Hub | The mod's own build tool instead of zipping the repo (the checks still run first). It must write `dist/<name>.zip`; it gets `$BUILD_VERSION`. |
| `zips` | Logistics Hub | Several zip names in one release (`FS25_LogisticsHub FS25_PalletDepot`) |
| `version-suffix` | AutoDrive | A build number after the modDesc version in tags: `-od\.[0-9]+` allows `v3.0.1.4-od.57` |
| `notes-command` | AutoDrive | Its own release-notes script (gets `$VERSION`) |
| `install-note` | Logistics Hub, AutoDrive | Text under the notes instead of the standard install line; `none` leaves it out (AutoDrive's notes explain installing) |
| `test-tag` | everyone | Set by the Run workflow button (see above) |

## Other workflows in the mod repos

The same in every repo: `discord-release.yml` (posts releases), `discord-issues.yml` (posts issues).
The forks (AutoDrive, Better Contracts, Courseplay) also have `upstream-sync.yml`, and Courseplay has
`upstream-watch.yml`, which watches the upstream projects of all three forks.
