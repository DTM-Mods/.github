"""Checks this repository (DTM-Mods/.github) itself. Run by .github/workflows/check.yml on every push.

    python ci/check_repo.py            the checks that need no network
    python ci/check_repo.py --online   also asks itch.io whether every page in itch.json exists

What it checks:
  - every Python file in ci/ compiles, every workflow and issue form is valid YAML (when PyYAML is installed)
  - itch.json, kingmods.json and modhub.json parse, and only name mods that are in the org profile
  - our forks are in none of kingmods.json / modhub.json (the originals are there)
  - every mod in the org profile has an icon in assets/icons, 256x256, and every icon has a mod
"""
import json
import pathlib
import py_compile
import re
import struct
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
FORKS = {"FS25_AutoDrive", "FS25_BetterContracts", "FS25_Courseplay"}
ICON_SIZE = (256, 256)
errors, warnings = [], []


def png_size(path):
    head = path.read_bytes()[:24]
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def main():
    online = "--online" in sys.argv

    for py in sorted((ROOT / "ci").glob("*.py")):
        try:
            py_compile.compile(str(py), doraise=True, cfile=None)
        except py_compile.PyCompileError as e:
            errors.append(f"{py.relative_to(ROOT)}: {e.msg.strip()}")

    try:
        import yaml
    except ImportError:
        yaml = None
        warnings.append("PyYAML isn't installed: the YAML files weren't checked")
    if yaml:
        for folder in (".github", "workflow-templates"):
            for yml in sorted((ROOT / folder).rglob("*.yml")):
                try:
                    yaml.safe_load(yml.read_text(encoding="utf-8"))
                except yaml.YAMLError as e:
                    errors.append(f"{yml.relative_to(ROOT)}: not valid YAML: {str(e).splitlines()[0]}")

    profile = (ROOT / "profile" / "README.md").read_text(encoding="utf-8")
    listed = set(re.findall(r"github\.com/DTM-Mods/(FS25_[A-Za-z0-9_]+)", profile))
    if not listed:
        errors.append("profile/README.md: no mods found")

    lists = {}
    for name in ("itch", "kingmods", "modhub"):
        path = ROOT / "ci" / f"{name}.json"
        try:
            lists[name] = json.loads(path.read_text(encoding="utf-8"))["mods"]
        except (OSError, ValueError, KeyError) as e:
            errors.append(f"ci/{name}.json: {e!r}")
            continue
        for repo in lists[name]:
            if repo not in listed:
                errors.append(f"ci/{name}.json: {repo} isn't a mod in profile/README.md (renamed or misspelled?)")
            if repo in FORKS and name != "itch":
                errors.append(f"ci/{name}.json: {repo} is a fork of another team's mod; it never goes there")
    for repo, mod in lists.get("itch", {}).items():
        if not re.fullmatch(r"[a-z0-9-]+", mod.get("project", "")):
            errors.append(f"ci/itch.json: {repo} needs \"project\": the page's address on itch.io")
    for repo, mod in lists.get("kingmods", {}).items():
        if not isinstance(mod.get("id"), int) or f"/mods/{mod.get('id')}/" not in mod.get("url", ""):
            errors.append(f"ci/kingmods.json: {repo} needs \"id\" and a \"url\" with that id")

    icons = {p.stem: p for p in (ROOT / "assets" / "icons").glob("*.png")}
    for repo in sorted(listed - set(icons)):
        errors.append(f"assets/icons/{repo}.png is missing (the README tables and the Discord posts use it)")
    for repo in sorted(set(icons) - listed):
        warnings.append(f"assets/icons/{repo}.png: no mod of that name in profile/README.md")
    for repo, path in sorted(icons.items()):
        size = png_size(path)
        if size != ICON_SIZE:
            errors.append(f"assets/icons/{repo}.png is {size and 'x'.join(map(str, size)) or 'not a PNG'}, "
                          f"not {ICON_SIZE[0]}x{ICON_SIZE[1]}")

    if online:
        user = json.loads((ROOT / "ci" / "itch.json").read_text(encoding="utf-8")).get("user", "dtmmods")
        for repo, mod in lists.get("itch", {}).items():
            url = f"https://{user}.itch.io/{mod.get('project', '')}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (dtm-ci)"})
                urllib.request.urlopen(req, timeout=30).close()
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    errors.append(f"ci/itch.json: {repo}: {url} doesn't exist (create the page, or move the line "
                                  f"to _to_create); the upload fails on it every hour")
                else:
                    warnings.append(f"ci/itch.json: {repo}: {url} answered {e.code}, not checked")
            except OSError as e:
                warnings.append(f"ci/itch.json: {repo}: {url} not reachable ({e}), not checked")

    for w in warnings:
        print(f"::warning::{w}" if "--github" in sys.argv else f"warning: {w}")
    for e in errors:
        print(f"::error::{e}" if "--github" in sys.argv else f"ERROR: {e}")
    print(f"{len(listed)} mods in the profile, {len(icons)} icons, "
          + ", ".join(f"{len(v)} in {k}.json" for k, v in lists.items())
          + f": {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
