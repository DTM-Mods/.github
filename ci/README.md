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

Files tracked by git, minus development folders (`source/`, `reference/`, `tools/`, `tests/`, `dev/`, `docs/`, `modhub/`,
`previews/`, ...), files the game doesn't load (`.md`, `.blend`, `.psd`, ...) and `.png` files that have
a `.dds` of the same name. A `.modignore` file in the repo root can leave out more
(`notes/*`, `scripts/Debug.lua`) or put something back (`!docs/needed.xml`).

Same commit, same zip: the timestamps inside are fixed, so a rebuild has the same SHA-256.

## GIANTS ModHub rules

Besides the basic checks, every build checks the GIANTS ModHub rules that GIANTS' TestRunner fails a mod for
and that can be checked without the game. These are errors:

- `descVersion` in modDesc.xml must be **116** (the current game version; TestRunner 0.9.24 accepts only 116)
- the mod icon must be a `.dds`, **DXT1** (BC1), without mipmaps
- every `.dds` must be compressed (DXT1, DXT5, BC4, BC5 or a DX10 header), not uncompressed RGBA
- only game files in the zip: no `.png`, `.txt`, ... (`.xml .lua .dds .i3d .shapes .anim .ogg .wav .gls .ogv .gdm .grle .cache`)
- no `pcall` / `xpcall` in the scripts (ModHub says they hide errors; check for nil instead)

Warnings: no "Changelog X:" in a description language for an update, a title translated to the same text as
English, Lua lines over 200 characters.

TestRunner itself checks more (textures copied from the base game, unused files, polygon counts, the
GIANTS Editor's own checks). It needs Windows with the game and the GIANTS Editor, so it runs on the DTM
server for every test build (dtm-server `deploy-mods.ps1`) and locally with `_tools\TestRunner_public.exe`.

Mods that never go to ModHub (the forks) set `modhub: false`.

## Releasing

Raise `<version>` in `modDesc.xml` and push to main. That's all: when the version has no tag yet, the build
tags the commit `v<version>` and publishes a **pre-release** (a test build):

- Discord #testing gets the post (with the @Tester ping)
- the DTM server puts the zip into `/testing` and runs GIANTS' TestRunner on it; the result goes to the staff channel

**To put it live:** open the release on GitHub > **Edit** > untick **Set as a pre-release** > **Update release**
(the GitHub app works too). Then:

- Discord #mod-releases gets the post (@Release Pings)
- dtmmods.com shows the new version within about 15 minutes
- the DTM server swaps the zip into `/FTPness` (the old one goes to `/archive`), if TestRunner passed and the
  mod is live already; players get it after the next server restart

Pushing a tag by hand (`git tag v1.2.1.0`, `git push origin v1.2.1.0`) still works and also makes a pre-release.

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
| `modhub` | AutoDrive, Courseplay, Better Contracts | `false` skips the GIANTS ModHub rules (mods that never go to ModHub) |
| `auto-release` | AutoDrive, Courseplay, Better Contracts | `false`: a new modDesc version doesn't release itself; push a tag by hand. Always off with `version-suffix`. |
| `prerelease` | nobody | `false`: releases go straight out as full releases (skipping the test build) |
| `test-tag` | everyone | Set by the Run workflow button (see above) |

## Other workflows in the mod repos

The same in every repo: `discord-release.yml` (posts releases), `discord-issues.yml` (posts issues).
The forks (AutoDrive, Better Contracts, Courseplay) also have `upstream-sync.yml`, and Courseplay has
`upstream-watch.yml`, which watches the upstream projects of all three forks.
