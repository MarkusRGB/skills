#!/usr/bin/env python3
"""
Update WM2026_Highlights.ics with live results from ESPN API.

Two passes:
1. Group stage (UIDs wm2026-001..013, wm2026-k23..k27-*): match by team
   names appearing in SUMMARY, add ✅ score once a game is completed.
2. Knockout stage (wm2026-r32-*, wm2026-r16-*, wm2026-qf-*, wm2026-sf-*,
   wm2026-3rd, wm2026-final): the original calendar used placeholder
   dates/teams that don't line up with the real bracket. Real knockout
   fixtures are fetched from ESPN and applied *positionally* (both lists
   sorted chronologically, zipped 1:1) since round sizes always match
   (16 / 8 / 4 / 2 / 1 / 1). This replaces DTSTART/DTEND/SUMMARY/
   DESCRIPTION/LOCATION with the real date, time, teams and venue.

Runs automatically via GitHub Actions every 30 minutes.
"""
import re
import json
import urllib.request
from datetime import datetime, timezone, timedelta

ICS_FILE = "WM2026_Highlights.ics"

TEAM_NAMES = {
    "Austria": "Österreich", "Germany": "Deutschland", "Netherlands": "Niederlande",
    "France": "Frankreich", "Spain": "Spanien", "Brazil": "Brasilien",
    "Argentina": "Argentinien", "Croatia": "Kroatien", "Switzerland": "Schweiz",
    "Morocco": "Marokko", "Algeria": "Algerien", "Jordan": "Jordanien",
    "Ivory Coast": "Elfenbeinküste", "Curaçao": "Curaçao", "Sweden": "Schweden",
    "Tunisia": "Tunesien", "Türkiye": "Türkei", "Turkey": "Türkei",
    "Colombia": "Kolumbien", "DR Congo": "DR Kongo", "Congo DR": "DR Kongo",
    "Uzbekistan": "Usbekistan", "Scotland": "Schottland",
    "Bosnia & Herzegovina": "Bosnien-Herzegowina", "Bosnia-Herzegovina": "Bosnien-Herzegowina",
    "Qatar": "Katar", "Canada": "Kanada", "Czech Republic": "Tschechien",
    "Czechia": "Tschechien", "Mexico": "Mexiko", "South Africa": "Südafrika",
    "South Korea": "Südkorea", "Korea Republic": "Südkorea", "Norway": "Norwegen",
    "Iraq": "Irak", "Cape Verde": "Kap Verde", "Saudi Arabia": "Saudi-Arabien",
    "Belgium": "Belgien", "Egypt": "Ägypten", "Ecuador": "Ecuador",
    "New Zealand": "Neuseeland", "Australia": "Australien", "Paraguay": "Paraguay",
    "United States": "USA", "USA": "USA", "Panama": "Panama", "Ghana": "Ghana",
    "Uruguay": "Uruguay", "Senegal": "Senegal", "England": "England",
    "Portugal": "Portugal", "Japan": "Japan", "Haiti": "Haiti",
}

FLAGS = {
    "Österreich": "🇦🇹", "Deutschland": "🇩🇪", "Niederlande": "🇳🇱",
    "Frankreich": "🇫🇷", "Spanien": "🇪🇸", "Brasilien": "🇧🇷",
    "Argentinien": "🇦🇷", "Kroatien": "🇭🇷", "Schweiz": "🇨🇭",
    "Marokko": "🇲🇦", "Algerien": "🇩🇿", "Jordanien": "🇯🇴",
    "Elfenbeinküste": "🇨🇮", "Curaçao": "🇨🇼", "Schweden": "🇸🇪",
    "Tunesien": "🇹🇳", "Türkei": "🇹🇷", "Kolumbien": "🇨🇴",
    "DR Kongo": "🇨🇩", "Usbekistan": "🇺🇿", "Schottland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "Bosnien-Herzegowina": "🇧🇦", "Katar": "🇶🇦", "Kanada": "🇨🇦",
    "Tschechien": "🇨🇿", "Mexiko": "🇲🇽", "Südafrika": "🇿🇦",
    "Südkorea": "🇰🇷", "Norwegen": "🇳🇴", "Irak": "🇮🇶",
    "Kap Verde": "🇨🇻", "Saudi-Arabien": "🇸🇦", "Belgien": "🇧🇪",
    "Ägypten": "🇪🇬", "Ecuador": "🇪🇨", "Neuseeland": "🇳🇿",
    "Australien": "🇦🇺", "Paraguay": "🇵🇾", "USA": "🇺🇸",
    "Panama": "🇵🇦", "Ghana": "🇬🇭", "Uruguay": "🇺🇾",
    "Senegal": "🇸🇳", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Portugal": "🇵🇹",
    "Japan": "🇯🇵", "Haiti": "🇭🇹",
}

ROUND_LABELS = {
    "r32": "⚽ Sechzehntelfinale",
    "r16": "🔥 Achtelfinale",
    "qf": "🏅 VIERTELFINALE",
    "sf": "🔴 HALBFINALE",
    "3rd": "🥉 SPIEL UM PLATZ 3",
    "final": "🏆 WM 2026 FINALE",
}

# Knockout UIDs in bracket order (matches chronological ESPN order 1:1)
KO_UIDS = (
    [f"wm2026-r32-{i:02d}@radlgruber" for i in range(1, 17)]
    + [f"wm2026-r16-{i:02d}@radlgruber" for i in range(1, 9)]
    + [f"wm2026-qf-{i:02d}@radlgruber" for i in range(1, 5)]
    + [f"wm2026-sf-{i:02d}@radlgruber" for i in range(1, 3)]
    + ["wm2026-3rd@radlgruber"]
    + ["wm2026-final@radlgruber"]
)


def de_name(espn_name):
    return TEAM_NAMES.get(espn_name, espn_name)


def flag(name):
    return FLAGS.get(name, "⚽")


def fetch_matches_for_date(date_str):
    url = (
        f"https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/"
        f"scoreboard?dates={date_str}&limit=50"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
    except Exception as e:
        print(f"  ESPN API error for {date_str}: {e}")
        return []

    matches = []
    for event in data.get("events", []):
        comp = event.get("competitions", [{}])[0]
        state = comp.get("status", {}).get("type", {}).get("state", "")
        competitors = comp.get("competitors", [])
        if len(competitors) != 2:
            continue
        c0, c1 = competitors[0], competitors[1]
        venue = comp.get("venue", {})
        matches.append({
            "state": state,
            "team0": c0.get("team", {}).get("displayName", ""),
            "score0": c0.get("score", ""),
            "team1": c1.get("team", {}).get("displayName", ""),
            "score1": c1.get("score", ""),
            "date": event.get("date", ""),
            "venue_name": venue.get("fullName", ""),
            "venue_city": venue.get("address", {}).get("city", ""),
        })
    return matches


def fetch_range(start, end):
    out = []
    current = start
    while current <= end:
        date_str = current.strftime("%Y%m%d")
        print(f"  Fetching {date_str}...")
        out.extend(fetch_matches_for_date(date_str))
        current += timedelta(days=1)
    return out


def teams_in_summary(espn0, espn1, summary):
    s = summary.lower()
    de0, de1 = de_name(espn0).lower(), de_name(espn1).lower()
    found0 = de0 in s or espn0.lower() in s
    found1 = de1 in s or espn1.lower() in s
    return found0 and found1


def update_group_stage(content, group_matches):
    completed = [m for m in group_matches if m["state"] == "post"]
    changes = 0

    def process(block):
        nonlocal changes
        summary_match = re.search(r"^SUMMARY:(.+)$", block, re.MULTILINE)
        if not summary_match:
            return block
        summary = summary_match.group(1)
        if re.search(r"✅\s*\d+:\d+", summary):
            return block

        desc_match = re.search(r"^DESCRIPTION:(.+)$", block, re.MULTILINE)
        desc = desc_match.group(1) if desc_match else ""

        for m in completed:
            if teams_in_summary(m["team0"], m["team1"], summary):
                t0, t1 = de_name(m["team0"]), de_name(m["team1"])
                s0, s1 = m["score0"], m["score1"]
                new_summary = re.sub(r"\s*[⭐]\s*(HEUTE!?)?", "", summary).rstrip()
                new_summary = f"{new_summary} ✅ {s0}:{s1}"
                block = block.replace(f"SUMMARY:{summary}", f"SUMMARY:{new_summary}", 1)

                if desc and "ERGEBNIS:" not in desc:
                    result_str = f"ERGEBNIS: {t0} {s0}-{s1} {t1} ✅"
                    new_desc = re.sub(r"(\\nAnpfiff:[^\\]+)", f"\\n{result_str}", desc, count=1)
                    if new_desc == desc:
                        new_desc = desc + f"\\n{result_str}"
                    block = block.replace(f"DESCRIPTION:{desc}", f"DESCRIPTION:{new_desc}", 1)

                print(f"  ✅ {t0} {s0}-{s1} {t1}")
                changes += 1
                break
        return block

    parts = re.split(r"(BEGIN:VEVENT\n[\s\S]*?END:VEVENT\n)", content)
    new_parts = [process(p) if p.startswith("BEGIN:VEVENT") else p for p in parts]
    return "".join(new_parts), changes


def fmt_dt(iso_date):
    dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
    return dt.strftime("%Y%m%dT%H%M%SZ")


def fmt_local(iso_date):
    dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
    local = dt + timedelta(hours=2)  # MESZ
    return local.strftime("%H:%M")


def build_ko_summary(round_key, match, team0_known, team1_known):
    label = ROUND_LABELS[round_key]
    if team0_known and team1_known:
        t0, t1 = de_name(match["team0"]), de_name(match["team1"])
        f0, f1 = flag(t0), flag(t1)
        suffix = ""
        if match["state"] == "post":
            suffix = f" ✅ {match['score0']}:{match['score1']}"
        return f"{label} – {f0} {t0} vs. {f1} {t1}{suffix}"
    else:
        city = match["venue_city"].split(",")[0] if match["venue_city"] else ""
        return f"{label}" + (f" – {city}" if city else "")


def update_knockout_stage(content, ko_matches):
    """Positionally replace each knockout VEVENT with real ESPN fixture data."""
    if len(ko_matches) != len(KO_UIDS):
        print(f"  ⚠ Knockout count mismatch: expected {len(KO_UIDS)}, got {len(ko_matches)} — skipping rebuild.")
        return content, 0

    changes = 0
    for uid, match in zip(KO_UIDS, ko_matches):
        round_key = uid.split("-")[1] if "r32" in uid or "r16" in uid or "qf" in uid or "sf" in uid else (
            "3rd" if "3rd" in uid else "final"
        )

        block_pattern = re.compile(
            rf"(BEGIN:VEVENT\nUID:{re.escape(uid)}\n)([\s\S]*?)(END:VEVENT\n)"
        )
        block_match = block_pattern.search(content)
        if not block_match:
            continue

        body = block_match.group(2)

        team0_known = "Round of" not in match["team0"] and "Winner" not in match["team0"] and "Loser" not in match["team0"]
        team1_known = "Round of" not in match["team1"] and "Winner" not in match["team1"] and "Loser" not in match["team1"]

        new_summary = build_ko_summary(round_key, match, team0_known, team1_known)
        dtstart = fmt_dt(match["date"])
        dt_obj = datetime.strptime(dtstart, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        dtend = (dt_obj + timedelta(hours=2)).strftime("%Y%m%dT%H%M%SZ")
        local_time = fmt_local(match["date"])

        venue = match["venue_name"] or "TBD"
        city = match["venue_city"] or ""
        location = f"{venue}, {city}" if city else venue

        if team0_known and team1_known:
            t0, t1 = de_name(match["team0"]), de_name(match["team1"])
            matchup = f"{t0} vs. {t1}"
            if match["state"] == "post":
                matchup += f" — ERGEBNIS {match['score0']}:{match['score1']} ✅"
        else:
            matchup = "Paarung noch nicht final"

        new_desc = f"{matchup}\\nAnpfiff: {local_time} Uhr MESZ\\nStadion: {location}"

        new_body = re.sub(r"^SUMMARY:.+$", f"SUMMARY:{new_summary}", body, count=1, flags=re.MULTILINE)
        new_body = re.sub(r"^DTSTART:.+$", f"DTSTART:{dtstart}", new_body, count=1, flags=re.MULTILINE)
        new_body = re.sub(r"^DTEND:.+$", f"DTEND:{dtend}", new_body, count=1, flags=re.MULTILINE)
        new_body = re.sub(r"^DESCRIPTION:.+$", f"DESCRIPTION:{new_desc}", new_body, count=1, flags=re.MULTILINE)
        new_body = re.sub(r"^LOCATION:.+$", f"LOCATION:{location}", new_body, count=1, flags=re.MULTILINE)

        if new_body != body:
            content = content.replace(body, new_body, 1)
            changes += 1
            print(f"  📅 {uid}: {new_summary}")

    return content, changes


if __name__ == "__main__":
    print("Lade WM 2026 Spieldaten von ESPN...\n")

    print("Gruppenphase:")
    group_matches = fetch_range(
        datetime(2026, 6, 12, tzinfo=timezone.utc),
        min(datetime.now(timezone.utc), datetime(2026, 6, 27, tzinfo=timezone.utc)),
    )

    print("\nK.o.-Runde:")
    ko_matches_raw = fetch_range(
        datetime(2026, 6, 28, tzinfo=timezone.utc),
        datetime(2026, 7, 19, tzinfo=timezone.utc),
    )
    ko_matches = sorted(ko_matches_raw, key=lambda m: m["date"])

    with open(ICS_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    content, c1 = update_group_stage(content, group_matches)
    content, c2 = update_knockout_stage(content, ko_matches)

    with open(ICS_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\nFertig: {c1} Gruppenspiel-Updates, {c2} K.o.-Runde-Updates.")
