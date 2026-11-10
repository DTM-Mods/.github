#!/usr/bin/env python3
"""Checks and builds a Farming Simulator 25 mod repository. Used by the DTM Mods CI.

    python fs25_mod.py check   [--root DIR]                 checks only
    python fs25_mod.py build   [--root DIR] [--out DIST] [--name ZIPNAME] [--tag vX.Y.Z.W]
    python fs25_mod.py files   [--root DIR] [--ext .lua]    lists the files that go into the zip
    python fs25_mod.py version [--root DIR]                 prints <version> from modDesc.xml
    python fs25_mod.py notes   VERSION [--root DIR]         release notes for VERSION (may be empty)

What goes into the zip
  Files tracked by git (untracked and ignored files never ship), minus:
  - top-level development folders: .github, source, reference, tools, tests, docs, previews, ...
  - files the game doesn't load: anything that isn't .xml .lua .i3d .shapes .anim .dds .png .ogg
    .wav .gdm .grle .txt (README.md, notes, LICENSE without .txt, ...)
  - a .png when a .dds of the same name exists (the game loads the .dds anyway)
  - anything listed in a .modignore file in the repo root (one glob per line, # comments,
    a line starting with ! puts a file back in, e.g. !source/keep.xml)

Checks (errors fail the build, warnings are only reported)
  - modDesc.xml exists, parses, has <version> and <descVersion>
  - every shipped .xml and .i3d parses
  - files referenced from the shipped XML/i3d files exist in the zip (case must match too:
    the game is case sensitive on the server)
  - GIANTS ModHub limits: at most 128 files in the zip, every .lua at most 0.5 MB
  - a release tag vX must match <version> in modDesc.xml

Only the Python standard library is used. Lua syntax is checked separately with luac5.1.
"""
import argparse
import fnmatch
import hashlib
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import PurePosixPath

GAME_EXTS = {".xml", ".lua", ".i3d", ".shapes", ".anim", ".dds", ".png", ".ogg", ".wav",
             ".gdm", ".grle", ".txt"}
DEV_DIRS = {".github", ".vscode", ".idea", "source", "sources", "reference", "references", "tools",
            "tests", "test", "docs", "doc", "previews", "preview", "screenshots", "chat_history",
            "releases", "release", "build", "dist", "node_modules", "bracket_information", ".dtm-ci"}
MAX_FILES = 128
MAX_LUA = 512 * 1024
# a value that looks like a file inside the mod
REF_RE = re.compile(r"^[^<>|*?\"\s][^<>|*?\"]*\.(xml|lua|i3d|shapes|anim|dds|png|ogg|wav|gdm|grle|txt)$", re.I)

errors, warnings = [], []


def err(msg):
    errors.append(msg)
    print(f"::error::{msg}" if os.environ.get("GITHUB_ACTIONS") else f"ERROR: {msg}")


def warn(msg):
    warnings.append(msg)
    print(f"::warning::{msg}" if os.environ.get("GITHUB_ACTIONS") else f"warning: {msg}")


# ---------------------------------------------------------------- selecting files
def tracked_files(root):
    try:
        out = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True, check=True).stdout
        return sorted(p for p in out.decode("utf-8").split("\0") if p)
    except (OSError, subprocess.CalledProcessError):
        files = []
        for d, dirs, names in os.walk(root):
            dirs[:] = [x for x in dirs if x != ".git"]
            files += [os.path.relpath(os.path.join(d, n), root).replace("\\", "/") for n in names]
        return sorted(files)


def read_modignore(root):
    path = os.path.join(root, ".modignore")
    if not os.path.exists(path):
        return [], []
    excl, incl = [], []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        (incl if line.startswith("!") else excl).append(line.lstrip("!").strip("/"))
    return excl, incl


def matches(path, patterns):
    for p in patterns:
        if fnmatch.fnmatchcase(path, p) or fnmatch.fnmatchcase(path, p + "/*") or path.startswith(p + "/"):
            return True
    return False


def ext_of(path):
    name = path.lower()
    for e in (".i3d.shapes", ".i3d.anim"):
        if name.endswith(e):
            return "." + e.rsplit(".", 1)[1]
    return os.path.splitext(name)[1]


def shipped_files(root):
    excl, incl = read_modignore(root)
    keep, skipped = [], []
    for f in tracked_files(root):
        if not os.path.isfile(os.path.join(root, f)):
            continue          # deleted in the working tree
        top = f.split("/", 1)[0].lower() if "/" in f else ""
        forced = matches(f, incl)
        reason = None
        if top in DEV_DIRS:
            reason = "development folder"
        elif ext_of(f) not in GAME_EXTS:
            reason = "not a game file type"
        elif matches(f, excl):
            reason = ".modignore"
        if reason and not forced:
            skipped.append((f, reason))
        else:
            keep.append(f)

    # The game always loads X.dds when X.png is asked for, so a .png next to its .dds is a
    # leftover source image.
    keep_set = set(keep)
    for f in list(keep):
        if f.lower().endswith(".png") and (f[:-4] + ".dds") in keep_set and not matches(f, incl):
            keep.remove(f)
            skipped.append((f, "a .dds of the same name ships instead"))

    return keep, sorted(skipped)


def unused_lua(root, keep):
    """Lua files no other shipped file mentions: probably never loaded (debug or old scripts).
    Only reported; leaving out a script the mod does need would break it."""
    found = []
    texts = {}
    for f in keep:
        if ext_of(f) in (".xml", ".lua"):
            try:
                texts[f] = open(os.path.join(root, f), encoding="utf-8", errors="replace").read()
            except OSError:
                texts[f] = ""
    for f in [x for x in keep if ext_of(x) == ".lua"]:
        name = os.path.basename(f)
        quoted_stem = re.compile(r"[\"'/]" + re.escape(name[:-4]) + r"[\"'.]")   # source(dir .. "x" .. ".lua")
        used = any(name in t or (ext_of(other) == ".lua" and quoted_stem.search(t))
                   for other, t in texts.items() if other != f)
        if not used:
            found.append(f)
    return found


# ---------------------------------------------------------------- modDesc
def read_moddesc(root):
    path = os.path.join(root, "modDesc.xml")
    if not os.path.exists(path):
        err("modDesc.xml is missing in the repository root")
        return None
    try:
        return ET.parse(path).getroot()
    except ET.ParseError as e:
        err(f"modDesc.xml doesn't parse: {e}")
        return None


def moddesc_version(md):
    v = (md.findtext("version") or "").strip() if md is not None else ""
    return v


# ---------------------------------------------------------------- checks
def check(root, files):
    md = read_moddesc(root)
    if md is not None:
        version = moddesc_version(md)
        if not version:
            err("modDesc.xml has no <version>")
        elif not re.fullmatch(r"\d+(\.\d+){3}", version):
            warn(f"version '{version}' isn't the usual X.Y.Z.W form")
        if md.get("descVersion") is None:
            err("modDesc.xml has no descVersion attribute")
        if not (md.findtext("title/en") or "").strip():
            warn("modDesc.xml has no English <title>")

    for f in unused_lua(root, files):
        warn(f"{f} isn't mentioned by modDesc.xml or any other file, so it's probably never loaded "
             "(add it to .modignore if it shouldn't ship)")

    if MAX_FILES and len(files) > MAX_FILES:
        err(f"{len(files)} files would go into the zip; GIANTS ModHub allows at most {MAX_FILES} "
            "(set max-files: 0 in the workflow if this mod never goes to ModHub)")

    shipped = set(files)
    lower = {}
    for f in files:
        lower.setdefault(f.lower(), f)

    for f in files:
        full = os.path.join(root, f)
        e = ext_of(f)
        if e == ".lua" and os.path.getsize(full) > MAX_LUA:
            err(f"{f} is {os.path.getsize(full) / 1024:.0f} KB; GIANTS allows at most 512 KB per Lua file")
        if e in (".xml", ".i3d"):
            try:
                tree = ET.parse(full)
            except ET.ParseError as ex:
                err(f"{f} doesn't parse: {ex}")
                continue
            check_refs(f, tree.getroot(), shipped, lower)
            if f == "modDesc.xml":
                check_l10n(tree.getroot(), shipped, lower)


def resolve(ref, base_dir, shipped, lower):
    """Returns (found_path, wrong_case_path)."""
    ref = ref.replace("\\", "/").strip()
    low = ref.lower()
    if low.startswith("$moddir$"):
        cands = [ref[len("$moddir$"):].lstrip("/")]
    else:
        cands = [str(PurePosixPath(base_dir, ref)) if base_dir else ref, ref.lstrip("/")]
    norm = []
    for c in cands:
        parts, outside = [], False
        for p in c.split("/"):
            if p in ("", "."):
                continue
            if p == "..":
                if not parts:
                    outside = True        # points outside the mod
                    break
                parts.pop()
            else:
                parts.append(p)
        if not outside:
            norm.append("/".join(parts))
    if not norm:
        return "outside", None            # base game or another mod, not ours to check
    # the game loads a .dds when a .png is asked for
    alts = []
    for c in norm:
        alts.append(c)
        if c.lower().endswith(".png"):
            alts.append(c[:-4] + ".dds")
    for c in alts:
        if c in shipped:
            return c, None
    for c in alts:
        if c.lower() in lower:
            return None, lower[c.lower()]
    return None, None


def is_external(ref):
    low = ref.replace("\\", "/").lower()
    return (low.startswith("$") and not low.startswith("$moddir$")) or low.startswith(("data/", "datas/", "http"))


# modDesc.xml elements whose files the game loads at start; missing ones always break the mod
MODDESC_LOADS = {"iconFilename", "sourceFile", "specialization", "type", "storeItem", "filename"}


def check_refs(f, root_el, shipped, lower):
    """Missing textures/files in .i3d models and files modDesc.xml loads are errors. Other XML
    files often name base-game or DLC files ("placeables/fences/..."), or vehicles by file name
    in config lists, so a missing one there is only a warning."""
    base = str(PurePosixPath(f).parent)
    base = "" if base == "." else base
    strict_file = f.lower().endswith(".i3d") or f == "modDesc.xml"
    seen = set()
    for el in root_el.iter():
        values = [(v, True) for v in el.attrib.values()]
        if el.text and len(el.text) < 260 and not list(el):
            values.append((el.text, False))
        for v, _ in values:
            v = v.strip()
            if not v or not REF_RE.match(v) or is_external(v) or v in seen:
                continue
            seen.add(v)
            found, wrong_case = resolve(v, base, shipped, lower)
            if found:
                continue
            if wrong_case:
                err(f"{f} refers to '{v}' but the file is '{wrong_case}' (case must match on the server)")
                continue
            strict = strict_file and (f != "modDesc.xml" or el.tag in MODDESC_LOADS)
            if "/" not in v.replace("\\", "/") and not strict_file:
                continue              # a bare name in a config list, not a path
            msg = f"{f} refers to '{v}', which isn't in the zip"
            (err if strict else warn)(msg)


def check_l10n(md, shipped, lower):
    l10n = md.find("l10n")
    if l10n is None:
        return
    prefix = l10n.get("filenamePrefix")
    if prefix:
        en = f"{prefix}_en.xml"
        if en not in shipped:
            err(f"modDesc.xml <l10n filenamePrefix=\"{prefix}\"> but {en} isn't in the zip")


# ---------------------------------------------------------------- build
def build(root, files, out_dir, name):
    os.makedirs(out_dir, exist_ok=True)
    zip_path = os.path.join(out_dir, name + ".zip")
    # Same commit -> same zip, byte for byte: fixed timestamps and sorted entries.
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH") or commit_time(root) or time.time())
    stamp = time.gmtime(max(epoch, 315532800))[:6]
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(files):
            info = zipfile.ZipInfo(f, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(os.path.join(root, f), "rb") as fh:
                z.writestr(info, fh.read(), compresslevel=9)
    digest = hashlib.sha256(open(zip_path, "rb").read()).hexdigest()
    with open(zip_path + ".sha256", "w", encoding="ascii", newline="\n") as fh:
        fh.write(f"{digest}  {name}.zip\n")
    return zip_path, digest


def commit_time(root):
    try:
        out = subprocess.run(["git", "-C", root, "log", "-1", "--format=%ct"], capture_output=True, check=True)
        return int(out.stdout.strip() or 0)
    except (OSError, subprocess.CalledProcessError, ValueError):
        return 0


# ---------------------------------------------------------------- release notes
def release_notes(root, version):
    """Notes for VERSION from PATCH_NOTES.md / RELEASE_NOTES.md / CHANGELOG.md, else from the
    English modDesc description ("Changelog X:" block). Empty if nothing is found."""
    v = re.escape(version)
    for name in ("PATCH_NOTES.md", "RELEASE_NOTES.md", "CHANGELOG.md"):
        path = os.path.join(root, name)
        if not os.path.exists(path):
            continue
        lines = open(path, encoding="utf-8").read().splitlines()
        for i, line in enumerate(lines):
            m = re.match(r"^(#+)\s.*" + v + r"\b", line)
            if m:
                level = len(m.group(1))
                body = []
                for nxt in lines[i + 1:]:
                    h = re.match(r"^(#+)\s", nxt)
                    if h and len(h.group(1)) <= level:
                        break
                    body.append(nxt)
                text = "\n".join(body).strip()
                if text:
                    return text
    md = read_moddesc(root)
    desc = (md.findtext("description/en") or "") if md is not None else ""
    m = re.search(r"Changelog\s+" + v + r"\s*:?\s*\n(.*?)(?:\n\s*\n|\Z)", desc, re.S | re.I)
    if m:
        return m.group(1).strip()
    return ""


# ---------------------------------------------------------------- main
def summary(lines):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["check", "build", "files", "version", "notes"])
    ap.add_argument("version_arg", nargs="?", help="version for 'notes'")
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="dist")
    ap.add_argument("--name", help="zip name without .zip (default: the repository folder name)")
    ap.add_argument("--tag", help="release tag; must be v<version from modDesc.xml>")
    ap.add_argument("--ext", help="with 'files': only this extension, e.g. .lua")
    ap.add_argument("--max-files", type=int, default=128, help="GIANTS ModHub file limit, 0 = no limit")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    global MAX_FILES
    MAX_FILES = a.max_files

    if a.command == "version":
        print(moddesc_version(read_moddesc(root)))
        return 1 if errors else 0
    if a.command == "notes":
        if not a.version_arg:
            ap.error("notes needs a version")
        print(release_notes(root, a.version_arg))
        return 0

    files, skipped = shipped_files(root)
    if a.command == "files":
        for f in files:
            if not a.ext or ext_of(f) == a.ext.lower():
                print(f)
        return 0

    print(f"{len(files)} files go into the zip, {len(skipped)} left out")
    check(root, files)
    version = moddesc_version(read_moddesc(root))
    if a.tag and a.tag != f"v{version}":
        err(f"tag {a.tag} doesn't match modDesc.xml <version> {version}; the tag must be v{version}")

    name = a.name or os.environ.get("MOD_NAME") or os.path.basename(root)
    lines = [f"## {name} {version}", "",
             f"- Files in the zip: **{len(files)}**" + (f" of {MAX_FILES} allowed" if MAX_FILES else ""),
             f"- Left out: {len(skipped)} (development files, see the log)"]
    zip_path = None
    if a.command == "build" and not errors:
        zip_path, digest = build(root, files, a.out, name)
        size = os.path.getsize(zip_path) / 1024 / 1024
        print(f"Built {zip_path} ({size:.1f} MB), SHA-256 {digest}")
        lines += [f"- Zip: `{name}.zip`, {size:.1f} MB", f"- SHA-256: `{digest}`"]
    if skipped:
        print("Left out of the zip:")
        for f, why in skipped:
            print(f"  {f}  ({why})")
    if warnings:
        lines += ["", "### Warnings", ""] + [f"- {w}" for w in warnings]
    if errors:
        lines += ["", "### Errors", ""] + [f"- {e}" for e in errors]
    summary(lines)
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
