<p align="center">
  <a href="https://github.com/DTM-Mods"><img src="https://raw.githubusercontent.com/DTM-Mods/.github/main/assets/dtm-header.jpg" alt="DTM Mods by PropaineX & Fennell" width="100%"></a>
</p>

<h1 align="center">DTM-Mods/.github</h1>

<p align="center">
  <a href="https://github.com/DTM-Mods/.github/actions/workflows/check.yml"><img src="https://github.com/DTM-Mods/.github/actions/workflows/check.yml/badge.svg" alt="Check"></a>
  <a href="https://github.com/DTM-Mods"><img src="https://img.shields.io/badge/DTM-Mods-143326" alt="DTM Mods"></a>
</p>

The shared files of the [DTM Mods](https://github.com/DTM-Mods) organization. Nothing here is a mod: this
repository holds the organization's front page, the build that every mod repository uses, and the pictures the
READMEs and Discord posts link to.

Looking for the mods? They are on the [organization page](https://github.com/DTM-Mods) and on
[dtmmods.com](https://dtmmods.com).

## What is in here

| Folder or file | What it is |
|----------------|------------|
| [`profile/README.md`](profile/README.md) | The organization's front page: every mod with its icon and latest release |
| [`.github/workflows/fs25-mod.yml`](.github/workflows/fs25-mod.yml) | The shared build. Every mod's `build.yml` calls it: checks, zip, releases |
| [`.github/workflows/check.yml`](.github/workflows/check.yml) | Checks this repository itself on every push (see below) |
| [`.github/workflows/weekly-downloads.yml`](.github/workflows/weekly-downloads.yml) | Posts the release download counts to the staff channel every Monday |
| [`ci/`](ci/) | The build's scripts and the lists of where each mod is published. [`ci/README.md`](ci/README.md) explains all of it |
| [`workflow-templates/`](workflow-templates/) | The `build.yml` a new mod repository starts from (Actions > New workflow > "DTM FS25 mod") |
| [`assets/`](assets/) | Pictures: the README section banners, mod icons (`icons/`), README screenshots (`screens/`), the logo (`brand/`) |
| `.github/ISSUE_TEMPLATE/`, `.github/DISCUSSION_TEMPLATE/` | The bug report, translation and idea forms of every repository |
| `CONTRIBUTING.md`, `SUPPORT.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `.github/FUNDING.yml` | Apply to every repository that has none of its own |

## Changing something here reaches every mod

Every mod repository runs the build and its scripts from `main` of this repository, and the READMEs and Discord posts
load the pictures in `assets/` straight from `main`. A change is live for all of them the moment it is pushed.

So this repository checks itself ([`check.yml`](.github/workflows/check.yml)) on every push and once a week:

- the Python files compile and the workflows and forms are valid YAML
- the lists in `ci/` only name mods from the organization page, and every itch.io page in `itch.json` exists
- every mod on the organization page has a 256x256 icon in `assets/icons/`
- the pushed `ci/fs25_mod.py` checks and builds four real mods (a script mod, a placeable, a vehicle and a fork)

Run the first three before pushing with `python ci/check_repo.py`. When the check turns red, fix or revert before
the next mod is pushed.

## Adding a mod

1. Push its icon to `assets/icons/<repository>.png` (256x256) **before** its first version reaches `main`:
   Discord fetches the picture once, when the release post goes out.
2. Add its row to [`profile/README.md`](profile/README.md).
3. In the new repository: **Actions** > **New workflow** > **DTM FS25 mod**. The rest is in
   [`ci/README.md`](ci/README.md).
4. When it has a page on itch.io or KingMods, add it to [`ci/itch.json`](ci/itch.json) or
   [`ci/kingmods.json`](ci/kingmods.json); on GIANTS' ModHub, to [`ci/modhub.json`](ci/modhub.json).

## License

MIT, see [LICENSE](LICENSE). The DTM Mods name and logo are ours.

---

<p align="center">
  <a href="https://github.com/DTM-Mods"><img src="https://raw.githubusercontent.com/DTM-Mods/.github/main/assets/dtm-intro.gif" alt="DTM Mods by PropaineX & Fennell" width="420"></a><br>
  <sub>Part of <a href="https://github.com/DTM-Mods">DTM Mods</a> (Designed To Manage) by PropaineX & Fennell</sub><br><br>
  <a href="https://ko-fi.com/dtmmods"><img src="https://img.shields.io/badge/Ko--fi-support%20DTM%20Mods-1F4D3A?logo=kofi&logoColor=F4F1E8" alt="Support DTM Mods on Ko-fi"></a>
  <a href="https://www.paypal.com/donate/?business=dtmmods%40gmail.com&amp;no_recurring=0&amp;item_name=DTM+Mods&amp;currency_code=USD"><img src="https://img.shields.io/badge/PayPal-donate-1F4D3A?logo=paypal&logoColor=F4F1E8" alt="Donate to DTM Mods with PayPal"></a><br>
  <a href="https://www.youtube.com/@DTMMods"><img src="https://img.shields.io/badge/YouTube-videos-1F4D3A?logo=youtube&logoColor=F4F1E8" alt="DTM Mods on YouTube"></a>
  <a href="https://dtmmods.itch.io"><img src="https://img.shields.io/badge/itch.io-our%20mods-1F4D3A?logo=itchdotio&logoColor=F4F1E8" alt="DTM Mods on itch.io"></a>
  <a href="https://www.kingmods.net/en/profile/dtmmods"><img src="https://img.shields.io/badge/KingMods-our%20mods-1F4D3A" alt="DTM Mods on KingMods"></a>
</p>
