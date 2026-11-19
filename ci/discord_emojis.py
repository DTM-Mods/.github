"""Custom emojis of the DTM Mods Discord, for every post made from GitHub Actions or a PC.

A webhook message must write a custom emoji in full: <:name:id>, or <a:name:id> when it is
animated. The :name: shortcut only works when a person types it. EMOJIS below holds the full form
of each emoji the posts use; a post looks its emoji up by name. A name that isn't in EMOJIS gets
the plain Unicode emoji instead, so a post never breaks.

An emoji that is deleted and uploaded again gets a new id: update its line here (and in
dtm-server/discord-emojis.ps1). To get the full forms, send the emojis with a backslash in front in
any channel of the DTM Discord ( \\:mod_update: ) and copy what Discord shows ( <a:mod_update:123> ).

Custom emojis show in message text, embed descriptions and field values, NOT in embed titles,
footers or author names, so only put them in the first three.

    import discord_emojis as emo
    emo.line("update", "**AutoDrive 3.0.1.4** is out!")   ->  "<a:mod_update:123> **AutoDrive ...**"
    emo.get("warn")                                       ->  "<a:beacon_amber:456>"  (or the Unicode one)
    emo.shortcodes("Big news :party_horn:")               ->  "Big news <a:party_horn:789>"

    python discord_emojis.py          show what every kind of post gets
"""
import re

# The DTM Discord's custom emojis: name -> the full form Discord shows for \:name:
EMOJIS = {
    "dtm_server_live":  "<a:dtm_server_live:1573034658487214270>",
    "log_clean":        "<a:log_clean:1573039878118187120>",
    "loading_bar":      "<a:loading_bar:1573039415482257450>",
    "mod_update":       "<a:mod_update:1573059622045220944>",
    "flat_tire":        "<a:flat_tire:1573064088869798119>",
    "bankrupt_zero":    "<a:bankrupt_zero:1573062907241963620>",
    "beacon_amber":     "<a:beacon_amber:1573062972371243078>",
    "xml_error":        "<a:xml_error:1573059743612674068>",
    "lua_magic":        "<a:lua_magic:1573059805025804328>",
    "dtm_bug_wiggle":   "<a:dtm_bug_wiggle:1573034914499268640>",
    "mod_release":      "<a:mod_release:1573059561663758426>",
    "hype_siren":       "<a:hype_siren:1573038978007834754>",
    "dtm_release_drop": "<a:dtm_release_drop:1573034617420779520>",
    "dtm_test_bubble":  "<a:dtm_test_bubble:1573034703038976070>",
    "wip_build":        "<a:wip_build:1573058397253804165>",
    "dtm_fixed_anim":   "<a:dtm_fixed_anim:1573034408997425203>",
    "giants_gear":      "<a:giants_gear:1573064285121290362>",
    "blender_cube":     "<a:blender_cube:1573063037378764830>",
    "dtm_pulse":        "<a:dtm_pulse:1573063578842570873>",
    "dtm_logo":         "<:dtm_logo:1573035065607192706>",
    "dtm_fire_hype":    "<a:dtm_fire_hype:1573063449703882762>",
    "party_horn":       "<a:party_horn:1573039609095393341>",
    "crown_king":       "<a:crown_king:1573063382490423316>",
    "gg_glow":          "<a:gg_glow:1573064221577453768>",
}

# What a post (or a line of it) means -> the emoji names to try, in order, and the plain Unicode
# emoji used when none of them is in EMOJIS. The same table is in dtm-server/discord-emojis.ps1.
ROLES = {
    "online":     (("dtm_server_live", "log_clean"), "\U0001F7E2"),         # server online / healthy
    "restarting": (("loading_bar", "mod_update"), "\U0001F504"),            # server restarting
    "waiting":    (("mod_update", "loading_bar"), "⏳"),                # mod updates waiting for a restart
    "down":       (("flat_tire", "bankrupt_zero"), "\U0001F534"),           # server down, health FAIL
    "warn":       (("beacon_amber",), "⚠️"),                      # WARN lines
    "xml":        (("xml_error", "dtm_bug_wiggle"), "\U0001F4C4"),          # mod error in an XML file
    "lua":        (("lua_magic", "dtm_bug_wiggle"), "\U0001F319"),          # mod error in a Lua script
    "bug":        (("dtm_bug_wiggle",), "\U0001F41E"),                      # any other mod error, a bug report
    "clean":      (("log_clean",), "✅"),                               # no errors found
    "new_mod":    (("mod_release", "hype_siren"), "\U0001F195"),            # a new mod's first release
    "update":     (("mod_update", "dtm_release_drop"), "\U0001F504"),       # a mod update / patch
    "test":       (("dtm_test_bubble", "wip_build"), "\U0001F9EA"),         # a test build
    "fixed":      (("dtm_fixed_anim",), "\U0001F6E0️"),                # a bug fixed in a release
    "github":     (("giants_gear", "blender_cube"), "⚙️"),        # GitHub links, dev log
    "dtm":        (("dtm_pulse", "dtm_logo", "dtm_fire_hype"), "\U0001F69C"),  # DTM branding / header
    "party":      (("party_horn", "crown_king", "gg_glow"), "\U0001F389"),  # milestones, celebrations
}


def get(role):
    """The emoji for a kind of post (a key of ROLES): the server's custom one, else the Unicode one."""
    names, plain = ROLES[role]
    return next((EMOJIS[n] for n in names if n in EMOJIS), plain)


def line(role, text):
    """text with the emoji for role at its start."""
    return "%s %s" % (get(role), text)


def has_shortcodes(text):
    return bool(text) and re.search(r":[A-Za-z0-9_]{2,32}:", text) is not None


def shortcodes(text):
    """Turns :name: into the full form for every custom emoji in EMOJIS (people's own texts)."""
    if not has_shortcodes(text):
        return text
    return re.sub(r"(?<![<\w])(?<!<a):([A-Za-z0-9_]{2,32}):(?![\d>])",
                  lambda m: EMOJIS.get(m.group(1), m.group(0)), text)


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # a Windows console isn't UTF-8 by default
    except Exception:
        pass
    print("%d custom emojis in the table" % len(EMOJIS))
    for role, (names, _) in ROLES.items():
        print("%-10s %s   (%s)" % (role, get(role), ", ".join(n + ("" if n in EMOJIS else " -") for n in names)))
