# Contributing to DTM Mods

Thanks for helping out with our Farming Simulator 25 mods.

## Reporting a bug

Open an issue in the mod's repository and pick **Bug report**. Attach your `log.txt`
(in `Documents/My Games/FarmingSimulator2025`) and say which version of the mod you're on.
Quick questions are easier on the [DTM Discord](https://discord.gg/2GTU9hAa3Q).

## Pull requests

- Keep to **Lua 5.1**: the game doesn't understand newer Lua (no `goto`, `//`, `&`, `|`).
- No `pcall` / `xpcall`: GIANTS' ModHub check refuses them. Check for `nil` instead.
- Test your change in the game before you open the pull request, in multiplayer too if it touches
  anything that syncs between players.
- Every pull request is checked automatically: Lua syntax, XML, missing files, GIANTS' ModHub rules, and the
  mod's own offline tests where it has some (`tests/`). The check also builds the mod zip.
- The repository's owner is asked to review it (see `.github/CODEOWNERS` in the repository).
- Don't raise `<version>` in `modDesc.xml` in a pull request: a new version releases itself (see below), so
  the maintainers do that when they merge.

## How a release works (maintainers)

1. Raise `<version>` in `modDesc.xml` (four numbers, e.g. `1.2.1.0`) and describe the changes in
   `PATCH_NOTES.md` under a heading with that version, and as a `Changelog 1.2.1.0:` block in every
   language of the modDesc description.
2. Commit and push to `main`. That is all: the **Build** workflow sees a version without a tag, tags the
   commit `v1.2.1.0` and publishes it as a **pre-release**, a test build. Discord #testing gets the post, and
   the DTM server puts the zip into `/testing` and runs GIANTS' TestRunner on it.
3. To put it live, open the release on GitHub, **Edit**, untick **Set as a pre-release**, **Update release**.
   Discord #mod-releases gets the post, dtmmods.com shows the new version, and the server swaps the zip in
   for everyone.

The forks (AutoDrive, Courseplay, Better Contracts) don't release by themselves: their tags are pushed by hand.

The zip keeps the mod's real name: renaming it would make savegames treat it as a different mod.
The details are in [`ci/README.md`](ci/README.md).

## Changing the shared build (this repository)

`main` of DTM-Mods/.github only takes a commit that passed its own check, because every mod builds with it.
Push with `.\ci\push_checked.ps1` or open a pull request; see the [README](README.md).
