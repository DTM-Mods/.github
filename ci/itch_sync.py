"""Puts the newest full release of every DTM mod listed in ci/itch.json on itch.io (dtmmods.itch.io), with butler.

For each mod: the latest full GitHub release (never a pre-release) is compared with the version on its itch page
(butler status); when they differ, the release zip is uploaded as it is (same file name, not unpacked) with the
release version as the itch version. A mod whose itch page doesn't exist yet is skipped: create the page on itch.io
once (the project name from ci/itch.json) and the next run fills it.

Usage: python ci/itch_sync.py [--repo FS25_Name] [--dry-run]
Needs: gh (GH_TOKEN), butler on PATH or in $BUTLER, and BUTLER_API_KEY (an itch.io API key of the dtmmods account)."""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ORG = "DTM-Mods"
HERE = pathlib.Path(__file__).resolve().parent


def run(cmd, check=True):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and p.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd[:3])}: {(p.stderr or p.stdout).strip()}")
    return p


def latest_release(repo):
    """the latest full release (GitHub's 'latest' skips pre-releases and drafts), or None"""
    p = run(["gh", "api", f"repos/{ORG}/{repo}/releases/latest"], check=False)
    if p.returncode != 0:
        return None
    return json.loads(p.stdout)


def itch_version(butler, target, channel):
    """(exists, version): whether the itch page can be reached, and the version on the channel (None = no upload yet)"""
    p = run([butler, "status", target], check=False)
    if p.returncode != 0:
        lines = (p.stderr or p.stdout).strip().splitlines()
        return False, lines[-1] if lines else ""
    for line in p.stdout.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and cells[0] == channel:
            version = cells[-1]
            return True, version if version and version != "-" else None
    return True, None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(HERE / "itch.json"))
    ap.add_argument("--repo", default="", help="only this repository")
    ap.add_argument("--dry-run", action="store_true", help="check and report, upload nothing")
    a = ap.parse_args()

    config = json.loads(pathlib.Path(a.config).read_text(encoding="utf-8"))
    user, channel = config["user"], config["channel"]
    butler = os.environ.get("BUTLER") or "butler"
    if not os.environ.get("BUTLER_API_KEY"):
        print("BUTLER_API_KEY is not set: nothing to do (add the itch.io API key as the secret BUTLER_API_KEY of DTM-Mods/.github)")
        return 0

    rows, failed = [], 0
    for repo, mod in config["mods"].items():
        if a.repo and repo.lower() != a.repo.lower():
            continue
        target = f"{user}/{mod['project']}:{channel}"
        page = f"https://{user}.itch.io/{mod['project']}"
        rel = latest_release(repo)
        if rel is None:
            rows.append((repo, "-", "-", "skipped: no full release on GitHub"))
            continue
        version = rel["tag_name"].removeprefix("v")
        zips = [x["name"] for x in rel.get("assets", []) if x["name"].lower().endswith(".zip")]
        zip_name = mod.get("zip") or (zips[0] if len(zips) == 1 else None)
        if zip_name is None or zip_name not in zips:
            rows.append((repo, version, "-", f"FAILED: release {rel['tag_name']} has zips {zips}, set \"zip\" in itch.json"))
            failed += 1
            continue

        exists, current = itch_version(butler, target, channel)
        if not exists:
            rows.append((repo, version, "-", f"skipped: no itch page {page} ({current})"))
            continue
        if current == version:
            rows.append((repo, version, current, "up to date"))
            continue
        if a.dry_run:
            rows.append((repo, version, current or "-", f"would upload {zip_name} to {target}"))
            continue

        work = pathlib.Path(tempfile.mkdtemp(prefix="itch_"))
        try:
            # a folder holding only the zip, pushed without unpacking: players get the zip under its own name
            build = work / "build"
            build.mkdir()
            run(["gh", "release", "download", rel["tag_name"], "-R", f"{ORG}/{repo}", "-p", zip_name, "-D", str(build)])
            run([butler, "push", "--no-auto-unzip", "--if-changed", "--userversion", version, str(build), target])
            rows.append((repo, version, current or "-", f"uploaded {zip_name} to {page}"))
            print(f"{repo}: uploaded {zip_name} {version} to {target}")
        except RuntimeError as e:
            rows.append((repo, version, current or "-", f"FAILED: {e}"))
            failed += 1
        finally:
            shutil.rmtree(work, ignore_errors=True)

    lines = ["| Mod | GitHub release | itch.io | Result |", "|---|---|---|---|"]
    lines += [f"| {r} | {v} | {c} | {s} |" for r, v, c, s in rows]
    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("## itch.io\n\n" + report + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
