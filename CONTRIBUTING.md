# Contributing to DTM Mods

Thanks for helping out with our Farming Simulator 25 mods.

## Reporting a bug

Open an issue in the mod's repository and pick **Bug report**. Attach your `log.txt`
(in `Documents/My Games/FarmingSimulator2025`) and say which version of the mod you're on.
Quick questions are easier on the [DTM Discord](https://discord.gg/2GTU9hAa3Q).

## Pull requests

- Keep to **Lua 5.1**: the game doesn't understand newer Lua (no `goto`, `//`, `&`, `|`).
- Test your change in the game before you open the pull request, in multiplayer too if it touches
  anything that syncs between players.
- Every pull request is checked automatically (Lua syntax, XML, missing files, GIANTS limits).
  The check also builds the mod zip; you can download it from the run page to test it.

## How a release works (maintainers)

1. Raise `<version>` in `modDesc.xml` (four numbers, e.g. `1.2.1.0`) and describe the changes in
   `PATCH_NOTES.md` under a heading with that version, or in the modDesc changelog.
2. Commit and push.
3. Tag the commit with the same version and push the tag:
   ```
   git tag v1.2.1.0
   git push origin v1.2.1.0
   ```
4. The **Build** workflow checks the mod, builds `<repository name>.zip`, publishes the GitHub release
   with the zip and posts it to the DTM Discord.

The tag must match `modDesc.xml` exactly, or the release stops before anything is published.
The zip keeps the mod's real name: renaming it would make savegames treat it as a different mod.
