#!/usr/bin/env python3
"""Checks and builds a Farming Simulator 25 mod repository. Used by the DTM Mods CI.

    python fs25_mod.py check   [--root DIR]                 checks only
    python fs25_mod.py build   [--root DIR] [--out DIST] [--name ZIPNAME] [--tag vX.Y.Z.W]
    python fs25_mod.py files   [--root DIR] [--ext .lua]    lists the files that go into the zip
    python fs25_mod.py version [--root DIR]                 prints <version> from modDesc.xml
    python fs25_mod.py notes   VERSION [--root DIR]         release notes for VERSION (may be empty)
    python fs25_mod.py lua     [--root DIR] [--luac luac5.1] Lua 5.1 syntax check of the shipped scripts

What goes into the zip
  Files tracked by git (untracked and ignored files never ship), minus:
  - top-level development folders: .github, source, reference, tools, tests, docs, previews, modhub, ...
  - files the game doesn't load: anything that isn't .xml .lua .i3d .shapes .anim .dds .png .ogg
    .wav .gls .gdm .grle .txt (README.md, notes, LICENSE without .txt, ...)
  - a .png when a .dds of the same name exists (the game loads the .dds anyway)
  - anything listed in a .modignore file in the repo root (one glob per line, # comments,
    a line starting with ! puts a file back in, e.g. !source/keep.xml)

Checks (errors fail the build, warnings are only reported)
  - modDesc.xml exists, parses, has <version> and <descVersion>
  - every shipped .xml and .i3d parses
  - files referenced from the shipped XML/i3d files exist in the zip (case must match too:
    the game is case sensitive on the server)
  - GIANTS ModHub limits: at most 128 files in the zip, every .lua at most 0.5 MB
  - GIANTS' FS25 ModHub guidelines, unless --no-modhub: shop images and brand icons without mipmaps,
    no fantasy brands, GIANTS' description templates, a description in every language the mod
    speaks, the zip name, modhub/screenshots/ (3+, 1600x900)
  - GIANTS ModHub (TestRunner) rules, unless --no-modhub: descVersion 116, version 1.0.0.0 or higher, an
    English and a German description, the icon a 512x512 DXT1 .dds without mipmaps, every .dds
    compressed, only game files in the zip (no .png/.txt), no pcall/xpcall in Lua;
    warnings for a missing changelog, titles translated to the English text and Lua lines over 200 characters
  - a release tag vX must match <version> in modDesc.xml

Lua: the game runs GIANTS' Lua 5.1, which also knows the `continue` statement. The 'lua' command
checks every shipped script with luac5.1 after turning `continue` into an empty `do end` (same line
numbers), so newer syntax (goto, //, &, |) is caught but GIANTS' own extension isn't flagged.
Without luac5.1 on the PATH it uses the lupa Python package (Lua 5.1 embedded in Python,
`pip install lupa`), which has the same parser.

Only the Python standard library is used, except lupa for the Lua check when luac5.1 is missing.
"""
import argparse
import fnmatch
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import PurePosixPath

GAME_EXTS = {".xml", ".lua", ".i3d", ".shapes", ".anim", ".dds", ".png", ".ogg", ".wav", ".gls",
             ".gdm", ".grle", ".txt"}
DEV_DIRS = {".github", ".vscode", ".idea", "source", "sources", "reference", "references", "tools",
            "tests", "test", "docs", "doc", "previews", "preview", "screenshots", "chat_history",
            "releases", "release", "build", "dist", "dev", "node_modules", "bracket_information", ".dtm-ci",
            "modhub"}
MAX_FILES = 128
MAX_LUA = 512 * 1024
MODHUB = True         # the GIANTS ModHub (TestRunner) rules; --no-modhub for mods that never go to ModHub
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

    unused = unused_lua(root, files)
    for f in unused[:5]:
        warn(f"{f} isn't mentioned by modDesc.xml or any other file, so it's probably never loaded "
             "(add it to .modignore if it shouldn't ship)")
    if len(unused) > 5:
        warn(f"{len(unused) - 5} more Lua files look unused: " + ", ".join(unused[5:]))

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

    if MODHUB:
        check_modhub(root, files, md)


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
        # "name" is a label (an i3d names itself "x_work.i3d", nodes are called "a.dds"), never a file to load
        values = [(v, True) for k, v in el.attrib.items() if k != "name"]
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


# ---------------------------------------------------------------- GIANTS ModHub (TestRunner) rules
# What GIANTS' TestRunner (the check ModHub runs on every upload) fails a mod for, as far as it can be
# checked without the game: found by running TestRunner 0.9.23 on our mods in November 2026.
# descVersion: the game build of 2026-10-27 has ModDesc version 116 (its log says so) and TestRunner 0.9.24
# accepts only 116 (0.9.23 only 115).
MODHUB_DESC_VERSION = 116
# files ModHub accepts in a zip (TestRunner "ObsoleteFiles": source files like .png must be exported to .dds)
MODHUB_EXTS = {".xml", ".lua", ".dds", ".i3d", ".shapes", ".anim", ".ogg", ".wav", ".gls", ".ogv",
               ".gdm", ".grle", ".cache"}
# DDS compressions TestRunner accepts (DX10 covers the BCn formats in a DX10 header)
DDS_OK = {b"DXT1", b"DXT5", b"ATI1", b"ATI2", b"BC4U", b"BC5U", b"BC5S", b"DX10"}


def dds_info(path):
    """(fourcc, mipmaps) of a .dds, or None if it isn't one. fourcc is b'' for uncompressed."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(128)
    except OSError:
        return None
    if len(head) < 128 or head[:4] != b"DDS ":
        return None
    mips = int.from_bytes(head[28:32], "little")
    pf_flags = int.from_bytes(head[80:84], "little")
    fourcc = head[84:88] if pf_flags & 0x4 else b""
    return fourcc, mips


def dds_size(path):
    """(width, height) of a .dds."""
    with open(path, "rb") as fh:
        head = fh.read(20)
    return int.from_bytes(head[16:20], "little"), int.from_bytes(head[12:16], "little")


def check_dds_image(root, dds, what, size, formats, format_name):
    """A ModHub picture (shop image, brand icon): size, compression, no mipmaps."""
    info = dds_info(os.path.join(root, dds))
    if info is None:
        return
    fourcc, mips = info
    if fourcc not in formats:
        err(f"the {what} {dds} is {fourcc.decode('ascii', 'replace') or 'uncompressed'}; ModHub wants {format_name}")
    if mips > 1:
        err(f"the {what} {dds} has {mips} mipmaps; GIANTS' ModHub guidelines want none")
    w, h = dds_size(os.path.join(root, dds))
    if (w, h) != size:
        err(f"the {what} {dds} is {w}x{h}; ModHub wants {size[0]}x{size[1]}")


# ---------------------------------------------------------------- GIANTS' FS25 ModHub guidelines
# "ModHub Guidelines - Farming Simulator 25" (forum.giants-software.com/viewtopic.php?p=1628568, updated
# 19.03.26), the data check before any in-game test. What can be checked from the files is checked here.
ZIP_NAME = None       # the zip's name without .zip (--name, MOD_NAME in CI)
# description template labels (section 5): (English labels, German labels); a label is a regex
TEMPLATE = {
    "vehicle": ([r"Category:", r"Price:"], [r"Shopkategorie:|Kategorie:", r"Preis:"]),
    "placeable": ([r"Category:", r"Price:", r"Monthly upkeep:"],
                  [r"Kategorie:|Shopkategorie:|Category:", r"Preis:", r"Monatliche Unterhaltskosten:"]),
    "script": ([r"Hotkeys:"], [r"Tastenkombinationen:"]),
}
SCREENSHOT_SIZE = (1600, 900)


def mod_languages(root, md, files):
    """Languages the mod's own texts (l10n) come in."""
    langs = set()
    l10n = md.find("l10n")
    if l10n is None:
        return langs
    prefix = (l10n.get("filenamePrefix") or "").replace("\\", "/")
    if prefix:
        for f in files:
            m = re.fullmatch(re.escape(prefix) + r"_(\w\w)\.xml", f)
            if m:
                langs.add(m.group(1))
    for text in l10n.iter("text"):
        langs.update(c.tag for c in text)
    return langs


def check_guidelines(root, files, md):
    name = ZIP_NAME
    if name:
        if not re.fullmatch(r"FS25_[A-Za-z0-9_]+", name):
            err(f"zip name {name}.zip: ModHub wants FS25_ at the start and only English letters, digits and _")
        elif re.search(r"(?i)_v?\d+_\d+|_v\d", name):
            err(f"zip name {name}.zip looks like it has a version number in it; ModHub refuses that")
    if md is None:
        return

    # store items: what kind of mod, fantasy brands
    own_brands = {(b.get("name") or "").strip().upper(): b for b in md.iter("brand")}
    kinds = set()
    for e in md.iter("storeItem"):
        item = (e.get("xmlFilename") or "").strip().replace("\\", "/")
        if item not in files:
            continue
        try:
            x = ET.parse(os.path.join(root, item)).getroot()
        except ET.ParseError:
            continue
        kinds.add("placeable" if x.tag == "placeable" else "vehicle")
        brand = (x.findtext("storeData/brand") or "").strip().upper()
        if brand and brand in own_brands:
            err(f"{item}: brand {brand} is a brand of the mod's own; GIANTS' guidelines don't allow fantasy "
                "brands: use LIZARD (or the real brand if the game has it)")
    for b in own_brands.values():
        img = (b.get("image") or "").strip().replace("\\", "/")
        dds = img[:-4] + ".dds" if img.lower().endswith(".png") else img
        if dds in files:
            check_dds_image(root, dds, "brand icon", (512, 256), (b"DXT5", b"DX10"), "BC3 (DXT5) or BC7")
    if not kinds:
        kinds.add("script")

    # descriptions: in every language the mod speaks, and GIANTS' template for its kind
    desc = md.find("description")
    if desc is None:
        return
    have = {d.tag for d in desc if (d.text or "").strip()}
    missing = sorted(mod_languages(root, md, files) - have)
    if missing:
        err(f"the mod has texts in {', '.join(missing)} but no description in them; GIANTS' guidelines want the "
            "description in every language the mod supports")
    has_actions = any(True for _ in md.iter("action"))
    for kind in sorted(kinds):
        if kind == "script" and not has_actions:
            continue
        for lang, labels in zip(("en", "de"), TEMPLATE[kind]):
            text = desc.findtext(lang) or ""
            for label in labels:
                if not re.search(r"(?m)^\W*(?:" + label + ")", text):
                    err(f"modDesc.xml description/{lang} has no '{label.split('|')[0]}' line; GIANTS' "
                        f"description template for {kind} mods asks for it (see the CI README)")

    # ModHub screenshots: modhub/screenshots/, unedited in-game shots
    shots_dir = os.path.join(root, "modhub", "screenshots")
    shots = sorted(f for f in os.listdir(shots_dir) if f.lower().endswith((".jpg", ".jpeg", ".png"))) \
        if os.path.isdir(shots_dir) else []
    if not shots:
        warn("no ModHub screenshots in modhub/screenshots/ (at least 3, 1600x900, unedited in-game shots, "
             "the first without UI)")
        return
    if len(shots) < 3:
        err(f"modhub/screenshots/ has {len(shots)} screenshot(s); ModHub wants at least 3")
    try:
        from PIL import Image
    except ImportError:
        return
    for s in shots:
        with Image.open(os.path.join(shots_dir, s)) as im:
            if im.size != SCREENSHOT_SIZE:
                err(f"modhub/screenshots/{s} is {im.size[0]}x{im.size[1]}; ModHub screenshots are 1600x900")


def lua_code_only(src):
    """The Lua source with comments and string contents blanked out (line numbers kept)."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if src.startswith("--", i):
            m = re.match(r"--\[(=*)\[", src[i:])
            if m:
                end = src.find("]" + m.group(1) + "]", i)
                end = n if end < 0 else end + len(m.group(1)) + 2
            else:
                end = src.find("\n", i)
                end = n if end < 0 else end
            out.append(re.sub(r"[^\n]", " ", src[i:end]))
            i = end
        elif c in "\"'":
            j = i + 1
            while j < n and src[j] != c and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            out.append(c + " " * (min(j, n) - i - 1) + (c if j < n else ""))
            i = j + 1
        elif c == "[" and re.match(r"\[(=*)\[", src[i:]):
            m = re.match(r"\[(=*)\[", src[i:])
            end = src.find("]" + m.group(1) + "]", i)
            end = n if end < 0 else end + len(m.group(1)) + 2
            out.append(re.sub(r"[^\n]", " ", src[i:end]))
            i = end
        else:
            out.append(c)
            i += 1
    return "".join(out)


PCALL_RE = re.compile(r"(?<![\w.:])(x?pcall)\b")


def check_modhub(root, files, md):
    """GIANTS ModHub / TestRunner rules. Errors: TestRunner fails the mod for these."""
    if md is not None:
        dv = md.get("descVersion")
        if dv is not None and dv.strip() != str(MODHUB_DESC_VERSION):
            err(f"modDesc.xml descVersion is {dv}; GIANTS ModHub (TestRunner) only accepts {MODHUB_DESC_VERSION}")
        version = moddesc_version(md)
        if version and not re.match(r"[1-9]\d*\.\d+\.\d+\.\d+", version):
            err(f"version {version}: ModHub wants a.b.c.d with a at least 1 (1.0.0.0 and up)")
        desc = md.find("description")
        if desc is not None and re.fullmatch(r"1\.0\.0\.0", version or ""):
            with_log = [d.tag for d in desc if "changelog" in (d.text or "").lower()]
            if with_log:
                err(f"modDesc.xml description/{', '.join(with_log)} has a changelog, but the version is 1.0.0.0: "
                    "ModHub (TestRunner) refuses a changelog in the first version (keep it in PATCH_NOTES.md)")
        for lang in ("en", "de"):
            if desc is None or not (desc.findtext(lang) or "").strip():
                err(f"modDesc.xml has no <description><{lang}>; ModHub requires an English and a German description")
        if desc is not None and version and not re.fullmatch(r"1(\.0)*", version):
            for lang in desc:
                if "changelog" not in (lang.text or "").lower():
                    warn(f"modDesc.xml description/{lang.tag} has no changelog; ModHub's TestRunner may ask for "
                         f"one for an update (add 'Changelog {version}:' with the changes)")
        title = md.find("title")
        if title is not None:
            en = (title.findtext("en") or "").strip()
            same = [t.tag for t in title if t.tag != "en" and (t.text or "").strip() == en]
            if en and same:
                warn(f"modDesc.xml <title> repeats the English title for {', '.join(same)}; "
                     "ModHub calls that obsolete (only translate a title that changes)")
        icon = (md.findtext("iconFilename") or "").strip()
        if icon:
            dds = icon[:-4] + ".dds" if icon.lower().endswith(".png") else icon
            if icon.lower().endswith(".png"):
                err(f"modDesc.xml <iconFilename> is {icon}; ModHub wants the icon as a .dds "
                    f"(DXT1, no mipmaps): {dds}")
            info = dds_info(os.path.join(root, dds)) if dds in files else None
            if info is not None:
                fourcc, mips = info
                if fourcc != b"DXT1":
                    err(f"the mod icon {dds} is {fourcc.decode('ascii', 'replace') or 'uncompressed'}; "
                        "ModHub wants DXT1 (BC1)")
                if mips > 1:
                    err(f"the mod icon {dds} has {mips} mipmaps; ModHub wants none")
                with open(os.path.join(root, dds), "rb") as fh:
                    head = fh.read(20)
                h, w = int.from_bytes(head[12:16], "little"), int.from_bytes(head[16:20], "little")
                if (w, h) != (512, 512):
                    err(f"the mod icon {dds} is {w}x{h}; ModHub wants 512x512")

    # shop images (storeData/image): not the mod icon file; GIANTS' FS25 guidelines: store_*.dds, 512x512,
    # BC3 (DXT5) or BC7 (DX10 header), without mipmaps
    icon_file = None
    if md is not None and (md.findtext("iconFilename") or "").strip():
        i = md.findtext("iconFilename").strip()
        icon_file = (i[:-4] + ".dds" if i.lower().endswith(".png") else i).lower()
    seen = set()
    for f in files:
        if ext_of(f) != ".xml":
            continue
        try:
            tree = ET.parse(os.path.join(root, f)).getroot()
        except ET.ParseError:
            continue
        for img in tree.iter("image"):
            ref = (img.text or "").strip().replace("\\", "/")
            if not ref or is_external(ref) or not REF_RE.match(ref):
                continue
            ref = re.sub(r"(?i)^\$moddir\$/?", "", ref)
            dds = ref[:-4] + ".dds" if ref.lower().endswith(".png") else ref
            if icon_file and dds.lower() == icon_file:
                err(f"{f}: the shop image {ref} is the mod icon too; ModHub wants a separate store_*.dds")
            if dds in seen or dds not in files:
                continue
            seen.add(dds)
            check_dds_image(root, dds, "shop image", (512, 512), (b"DXT5", b"DX10"), "BC3 (DXT5) or BC7")

    check_guidelines(root, files, md)

    for f in files:
        e = ext_of(f)
        if e not in MODHUB_EXTS:
            err(f"{f}: ModHub doesn't accept {e} files in a mod "
                + ("(export it as .dds)" if e in (".png", ".tga", ".jpg") else "(leave it out of the zip)"))
        elif e == ".dds":
            info = dds_info(os.path.join(root, f))
            if info is None:
                err(f"{f} isn't a valid .dds file")
            elif info[0] not in DDS_OK:
                err(f"{f} is {info[0].decode('ascii', 'replace') or 'uncompressed'}; ModHub only takes "
                    "compressed textures (DXT1, DXT5, BC4, BC5 or a DX10 header)")
        elif e == ".lua":
            src = open(os.path.join(root, f), "rb").read().decode("utf-8", errors="replace")
            code = lua_code_only(src)
            for m in PCALL_RE.finditer(code):
                line = code.count("\n", 0, m.start()) + 1
                msg = (f"{f}:{line}: {m.group(1)} isn't allowed on ModHub (it hides errors from the log); "
                       "check for nil instead")
                if os.environ.get("GITHUB_ACTIONS"):
                    errors.append(msg)
                    print(f"::error file={f},line={line}::{msg}")
                else:
                    err(msg)
            long_lines = [i + 1 for i, l in enumerate(src.splitlines()) if len(l) > 200]
            if long_lines:
                warn(f"{f}: {len(long_lines)} line(s) longer than 200 characters (TestRunner warns), "
                     f"first at line {long_lines[0]}")


# ---------------------------------------------------------------- Lua
CONTINUE_RE = re.compile(r"(?<![\w.:'\"])continue(?![\w])")


def check_lua(root, files, luac):
    import tempfile
    lua_files = [f for f in files if ext_of(f) == ".lua"]
    compile_with_lupa = None
    if shutil.which(luac) is None:
        try:
            from lupa import lua51
        except ImportError:
            err(f"{luac} isn't installed and the lupa Python package isn't either (pip install lupa)")
            return
        # loadstring only compiles: the same Lua 5.1 parser as luac -p, nothing runs
        compile_with_lupa = lua51.LuaRuntime().eval(
            "function(src, name) local f, e = loadstring(src, name) return e end")
        print(f"{luac} isn't installed, checking with the lupa package's Lua 5.1 instead.")

    def report(f, msg):
        m = re.search(r":(\d+):\s*(.*)$", msg)
        if m and os.environ.get("GITHUB_ACTIONS"):
            errors.append(msg)
            print(f"::error file={f},line={m.group(1)}::{f}:{m.group(1)}: {m.group(2)}")
        else:
            err(f"{f}: {m.group(1) + ': ' + m.group(2) if m else msg}")

    with tempfile.TemporaryDirectory() as tmp:
        for f in lua_files:
            src = open(os.path.join(root, f), "rb").read().decode("utf-8", errors="replace")
            src = CONTINUE_RE.sub("do end", src)   # GIANTS Lua has `continue`, Lua 5.1 doesn't
            if compile_with_lupa is not None:
                e = compile_with_lupa(src, "@" + f)
                if e:
                    report(f, str(e).strip().splitlines()[0])
                continue
            path = os.path.join(tmp, "x.lua")
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(src)
            r = subprocess.run([luac, "-p", path], capture_output=True, text=True)
            if r.returncode != 0:
                out = (r.stderr or r.stdout).strip()
                report(f, out.splitlines()[0] if out else "syntax error")
    if not errors:
        print(f"All {len(lua_files)} Lua files parse as GIANTS Lua 5.1.")


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
    """Notes for VERSION from PATCH_NOTES.md / RELEASE_NOTES.md / CHANGELOG.md / README.md (a heading
    with the version in it), else from the English modDesc description ("Changelog X:" block).
    Empty if nothing is found. A section also ends at a '---' rule or an HTML block (README footer,
    section banners)."""
    v = re.escape(version)
    for name in ("PATCH_NOTES.md", "RELEASE_NOTES.md", "CHANGELOG.md", "README.md"):
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
                    if (h and len(h.group(1)) <= level) or nxt.strip() == "---" or nxt.startswith(("<p ", "<!--", "<details")):
                        break
                    body.append(nxt)
                text = "\n".join(body).strip()
                if text:
                    return text
    md = read_moddesc(root)
    desc = (md.findtext("description/en") or "") if md is not None else ""
    m = re.search(r"Changelog\s+v?" + v + r"\s*:?\s*\n(.*?)(?:\n\s*\n|\Z)", desc, re.S | re.I)
    if m:
        return m.group(1).strip()
    # "1.1.0.1 - what changed" lines (one per change), as in Logistics Hub's changelog
    lines = re.findall(r"^\s*" + v + r"\s+[-–:]\s+(.+?)\s*$", desc, re.M)
    if lines:
        return "\n".join("- " + l for l in lines)
    return ""


# ---------------------------------------------------------------- main
def summary(lines):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["check", "build", "files", "version", "notes", "lua"])
    ap.add_argument("--luac", default="luac5.1")
    ap.add_argument("version_arg", nargs="?", help="version for 'notes'")
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="dist")
    ap.add_argument("--name", help="zip name without .zip (default: the repository folder name)")
    ap.add_argument("--tag", help="release tag; must be v<version from modDesc.xml>")
    ap.add_argument("--ext", help="with 'files': only this extension, e.g. .lua")
    ap.add_argument("--max-files", type=int, default=128, help="GIANTS ModHub file limit, 0 = no limit")
    ap.add_argument("--no-modhub", action="store_true",
                    help="skip the GIANTS ModHub (TestRunner) rules: for mods that never go to ModHub")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    global MAX_FILES, MODHUB
    MAX_FILES = a.max_files
    MODHUB = not a.no_modhub
    global ZIP_NAME
    ZIP_NAME = a.name or os.environ.get("MOD_NAME") or os.path.basename(root)

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
    if a.command == "lua":
        check_lua(root, files, a.luac)
        return 1 if errors else 0

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
