# DTM Mods CI

Shared checks and releases for every FS25 mod repository in DTM-Mods.

| File | What it is |
|------|------------|
| `../.github/workflows/fs25-mod.yml` | The reusable workflow. Each mod repo calls it from its own `.github/workflows/build.yml` |
| `fs25_mod.py` | Checks the mod and builds the zip (run `python fs25_mod.py --help`) |
| `check_repo.py` | Checks this repository itself: scripts, YAML, the lists below, the icons. `../.github/workflows/check.yml` runs it on every push, and builds four real mods with the pushed `fs25_mod.py` |
| `push_checked.ps1` | How to push to `main` here: `main` only takes a commit that passed the check, so this pushes to the branch `next`, waits for the check and then moves `main` up |
| `itch.json`, `kingmods.json`, `modhub.json` | Where each mod is published besides GitHub (see the sections below) |
| `discord_emojis.py` | The DTM Discord's custom emojis for every post (releases, test builds, issues, upstream, downloads), with the emoji table. The workflows download it from `main` (see below) |
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

## GIANTS' FS25 ModHub guidelines

Every DTM mod follows GIANTS' [ModHub Guidelines - Farming Simulator 25](https://forum.giants-software.com/viewtopic.php?p=1628568)
(updated 19.03.26). ModHub's data check rejects a mod on these before anyone plays it. The CI enforces what can be
checked from the files (errors):

- **Shop images** (`store_*.dds`): 512x512, BC3 (DXT5) or BC7, **without mipmaps**. **Brand icons** (`brand_*.dds`):
  512x256, BC3/BC7, without mipmaps. **Mod icon** (`icon_*.dds`): 512x512, BC1 (DXT1), without mipmaps.
- **No fantasy brands**: a brand defined by the mod itself can't sell its items; use `LIZARD` or the real brand.
- **Zip name**: `FS25_` + English letters, digits, `_`; no version number. A modder tag only as up to 3
  characters right after `FS25_` (`FS25_DTMSearchables`).
- **Description templates** (section 5), as lines at the start of the description, in English and German:
  - vehicles/equipment: `Category:` `Price:` (and `Power:` `Required power:` `Max. speed:` `Working width:`
    `Working speed:` `Capacity:` where they apply); German `Shopkategorie:` `Preis:` `Leistung:`
    `Benötigte Leistung:` `Höchstgeschwindigkeit:` `Arbeitsbreite:` `Arbeitsgeschwindigkeit:` `Kapazität:`
  - placeables/productions: `Category:` `Price:` `Monthly upkeep:` (`Production recipe:` `Configurations:`);
    German `Kategorie:` `Preis:` `Monatliche Unterhaltskosten:` (`Produktionsrezepte:` `Konfigurationen:`)
  - script mods with keys: `Description:` `Hotkeys:` (keyboard/mouse and controller) `GitHub:`; German
    `Beschreibung:` `Tastenkombinationen:` `GitHub:`
  - a pack repeats the block per item, the item's title above its `Category:` line.
- **A description in every language the mod supports** (every language of its l10n texts).
- **ModHub screenshots** in `modhub/screenshots/` (not shipped): at least 3, **1600x900**; a warning if there are none.

Checked by hand (the CI can't see these):

- **No modder references** anywhere but the zip's 3-character tag and `<author>`: no DTM, DTM Mods, dtmmods.com,
  PropaineX, Fennell in titles, descriptions, in-game texts, textures, icons or screenshots. (ModHub rejected
  Digital DTM for this; it is now Better Digital Display.)
- **Icons and screenshots are unedited game images**: "zero tolerance towards AI created imagery or modified in
  any other way outside of the game". No caption bars, frames, logos or added text on screenshots; the first one
  without UI; machinery shown at work within the first three; ideally a clean base-game setting.
- **The mod icon follows GIANTS' standard**: GIANTS' ModHub background (`_tools/modhub/modIcon_background.png`,
  from GIANTS' FS Icon Generator 25) with the model's render on it, or for a script mod a simple picture and the
  English title. `_brand/tools/make_icons.py --modhub` / `--modhub-render` make them; GIANTS' FS Icon Generator 25
  (gdn.giants-software.com) renders vehicles and placeables in its Mod Icon mode.
- **Dependencies**: a mod or DLC the mod needs is in `<dependencies>` and named in the ModHub submission comment.
- **Updates on ModHub**: a meaningful changelog; minor updates at least 4 weeks apart; uploaded as
  `<live zip name>_update.zip`.

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
- for [dtmmods.itch.io](https://dtmmods.itch.io): run `python dtm_itch.py --upload` in `_tools` (see below)

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

## itch.io

The mods on [dtmmods.itch.io](https://dtmmods.itch.io) are uploaded through the itch.io website by
`_tools/dtm_itch.py` (in DTM-Mods/dtm-tools; `Upload to itch.bat`), not by CI: itch's upload tool, butler, repacks a
`.zip` into an archive of its own, so players wouldn't get `FS25_Name.zip`, and itch has no other upload API.
[`ci/itch.json`](itch.json) lists the mods and their itch pages; the script uploads each mod's newest **full** release
that isn't on itch yet (never pre-releases). A new mod on itch: create its page on itch.io (Classification: Game mods,
Kind: Downloadable) and add a line to `ci/itch.json` with the page's address.

Only list a mod under `mods` once its page exists: the upload runs every hour (`_tools/dtm_sync_sites.py`) and fails
on every listed mod that has no page. Mods still waiting for a page are under `_to_create`, with the address the page
should get; `check.yml` fails when a page under `mods` doesn't exist.

## KingMods

Our mods on [KingMods](https://www.kingmods.net/en/profile/dtmmods) are listed in [`kingmods.json`](kingmods.json)
(page id and address per repository). KingMods has no API: a new page is made by hand on kingmods.net, then gets a
line here. The server's `dtm-stats.ps1` (dtm-server) reads each page once a day for its download count and the
version it offers; the admins' stats page shows both, and marks pages that offer an older version than the latest
release. Most KingMods Download buttons lead to our GitHub zips, so its count partly overlaps GitHub's and is never
added to the totals.

## Other workflows in the mod repos

The same in every repo: `discord-release.yml` (posts releases), `discord-issues.yml` (posts issues).
The forks (AutoDrive, Better Contracts, Courseplay) also have `upstream-sync.yml`, and Courseplay has
`upstream-watch.yml`, which watches the upstream projects of all three forks.

Every Discord post puts one of the server's custom emojis at the start of a line (`E("update")` in the
workflows). [`discord_emojis.py`](discord_emojis.py) maps each kind of post to emoji names, and holds the
full form (`<a:name:id>`) of each emoji, because a webhook can't use the `:name:` shortcut. A name not in
the table gets a plain Unicode emoji. When an emoji is uploaded again it gets a new id: send it with a
backslash in front in the DTM Discord (`\:mod_update:`), copy what Discord shows and update its line.
The server's scripts use the same table in `dtm-server/discord-emojis.ps1`: change both.
`python ci/discord_emojis.py` shows what each kind of post gets.
