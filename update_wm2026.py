#!/usr/bin/env python3
"""
Update WM2026_Highlights.ics with live results AND team names from ESPN API.
- Completed matches: adds score + ✅ to SUMMARY
- Scheduled matches: fills in real team names once known (replaces "Sieger Gruppe X")
Runs automatically via GitHub Actions every 30 minutes.
"""
import re
import json
import urllib.request
from datetime import datetime, timezone, timedelta

ICS_FILE = "WM2026_Highlights.ics"

# ESPN team names -> German/display names used in the .ics
TEAM_NAMES = {
    "Austria": "Österreich",
    "Germany": "Deutschland",
    "Netherlands": "Niederlande",
    "France": "Frankreich",
    "Spain": "Spanien",
    "Brazil": "Brasilien",
    "Argentina": "Argentinien",
    "Croatia": "Kroatien",
    "Switzerland": "Schweiz",
    "Morocco": "Marokko",
    "Algeria": "Algerien",
    "Jordan": "Jordanien",
    "Ivory Coast": "Elfenbeinküste",
    "Curaçao": "Curaçao",
    "Sweden": "Schweden",
    "Tunisia": "Tunesien",
    "Türkiye": "Türkei",
    "Turkey": "Türkei",
    "Colombia": "Kolumbien",
    "DR Congo": "DR Kongo",
    "Congo": "DR Kongo",
    "Uzbekistan": "Usbekistan",
    "Scotland": "Schottland",
    "Bosnia & Herzegovina": "Bosnien-Herzegowina",
    "Bosnia-Herzegovina": "Bosnien-Herzegowina",
    "Qatar": "Katar",
    "Canada": "Kanada",
    "Czech Republic": "Tschechien",
    "Czechia": "Tschechien",
    "Mexico": "Mexiko",
    "South Africa": "Südafrika",
    "South Korea": "Südkorea",
    "Korea Republic": "Südkorea",
    "Norway": "Norwegen",
    "Iraq": "Irak",
    "Cape Verde": "Kap Verde",
    "Saudi Arabia": "Saudi-Arabien",
    "Belgium": "Belgien",
    "Egypt": "Ägypten",
    "Ecuador": "Ecuador",
    "New Zealand": "Neuseeland",
    "Australia": "Australien",
    "Paraguay": "Paraguay",
    "United States": "USA",
    "USA": "USA",
    "Panama": "Panama",
    "Ghana": "Ghana",
    "Uruguay": "Uruguay",
    "Senegal": "Senegal",
    "England": "England",
    "Portugal": "Portugal",
    "Japan": "Japan",
    "Haiti": "Haiti",
    "Senegal": "Senegal",
    "Albania": "Albanien",
    "Serbia": "Serbien",
    "Ukraine": "Ukraine",
    "Hungary": "Ungarn",
    "Romania": "Rumänien",
    "Poland": "Polen",
    "Denmark": "Dänemark",
    "Finland": "Finnland",
    "Sweden": "Schweden",
}

# Country flag emojis for German team names
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


def de_name(espn_name):
    """Convert ESPN team name to German display name."""
    return TEAM_NAMES.get(espn_name, espn_name)


def flag(de_name_str):
    """Get flag emoji for a German team name."""
    return FLAGS.get(de_name_str, "⚽")


def fetch_matches_for_date(date_str):
    """Fetch all WC 2026 matches (any status) for a given date (YYYYMMDD)."""
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
        name0 = c0.get("team", {}).get("displayName", "")
        name1 = c1.get("team", {}).get("displayName", "")
        score0 = c0.get("score", "")
        score1 = c1.get("score", "")
        date_utc = event.get("date", "")

        matches.append({
            "state": state,          # "pre", "in", "post"
            "team0": name0, "score0": score0,
            "team1": name1, "score1": score1,
            "date": date_utc,
        })

    return matches


def fetch_all_matches():
    """Fetch all matches from tournament start through today + 14 days ahead."""
    all_matches = []
    start = datetime(2026, 6, 12, tzinfo=timezone.utc)
    today = datetime.now(timezone.utc)
    end = min(today + timedelta(days=14), datetime(2026, 7, 20, tzinfo=timezone.utc))

    current = start
    while current <= end:
        date_str = current.strftime("%Y%m%d")
        print(f"  Fetching {date_str}...")
        day_matches = fetch_matches_for_date(date_str)
        all_matches.extend(day_matches)
        current += timedelta(days=1)

    return all_matches


def teams_match_summary(espn_name0, espn_name1, summary):
    """Check if both ESPN team names appear in the SUMMARY (in either order)."""
    de0 = de_name(espn_name0).lower()
    de1 = de_name(espn_name1).lower()
    s = summary.lower()
    # Also check original ESPN names
    e0 = espn_name0.lower()
    e1 = espn_name1.lower()

    found0 = de0 in s or e0 in s
    found1 = de1 in s or e1 in s
    return found0 and found1


def update_ics(matches):
    """Update the .ics file. Returns True if changed."""
    with open(ICS_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    completed = [m for m in matches if m["state"] == "post"]
    scheduled = [m for m in matches if m["state"] in ("pre", "in")]

    changes = 0

    def process_vevent(block):
        nonlocal changes

        summary_match = re.search(r"^SUMMARY:(.+)$", block, re.MULTILINE)
        desc_match = re.search(r"^DESCRIPTION:(.+)$", block, re.MULTILINE)
        if not summary_match:
            return block

        summary = summary_match.group(1)
        desc = desc_match.group(1) if desc_match else ""

        # ── 1. Update completed matches with scores ───────────────────────
        if not re.search(r"✅\s*\d+:\d+", summary):
            for m in completed:
                if teams_match_summary(m["team0"], m["team1"], summary):
                    t0 = de_name(m["team0"])
                    t1 = de_name(m["team1"])
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

        # ── 2. Fill in team names for knockout matches ────────────────────
        # These have generic summaries like "⚽ Sechzehntelfinale – Match 78"
        # and descriptions with "Sieger Gruppe X vs. Zweiter Gruppe Y"
        is_generic = re.search(r"(Sechzehntelfinale|Achtelfinale|Viertelfinale|Halbfinale|Spiel um Platz|FINALE)\s*[–-]", summary)
        already_has_teams = re.search(r"(🇦🇹|🇩🇪|🇫🇷|🇧🇷|🇦🇷|🏴󠁧󠁢󠁥󠁮󠁧󠁿|🏴󠁧󠁢󠁳󠁣󠁴󠁿|\w{3,}\s+vs\.?\s+\w{3,})", summary)

        if is_generic and not already_has_teams and not re.search(r"✅\s*\d+:\d+", summary):
            # Try to match a scheduled/completed match by date proximity
            # Extract DTSTART to match by time
            dtstart_match = re.search(r"^DTSTART:(\d{8}T\d{6}Z)$", block, re.MULTILINE)
            if dtstart_match:
                event_dt = datetime.strptime(dtstart_match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)

                for m in matches:
                    if not m["date"]:
                        continue
                    try:
                        match_dt = datetime.fromisoformat(m["date"].replace("Z", "+00:00"))
                    except Exception:
                        continue
                    # Match within 30 minutes of each other
                    if abs((match_dt - event_dt).total_seconds()) < 1800:
                        t0 = de_name(m["team0"])
                        t1 = de_name(m["team1"])
                        f0 = flag(t0)
                        f1 = flag(t1)

                        # Replace generic summary with real teams
                        # Keep the round label (e.g. "⚽ Sechzehntelfinale –")
                        round_match = re.match(r"^([^–-]+[–-])", summary)
                        if round_match:
                            prefix = round_match.group(1).strip()
                            new_summary = f"{prefix} {f0} {t0} vs. {f1} {t1}"
                        else:
                            new_summary = f"{summary} | {f0} {t0} vs. {f1} {t1}"

                        block = block.replace(f"SUMMARY:{summary}", f"SUMMARY:{new_summary}", 1)

                        if desc:
                            # Update description too
                            new_desc = re.sub(
                                r"(Sieger Match \d+|Zweiter Gruppe [A-Z]|Sieger Gruppe [A-Z]|Bester Dritter[^\\]*)",
                                "",
                                desc,
                            )
                            teams_line = f"{f0} {t0} vs. {f1} {t1}"
                            new_desc = re.sub(r"(Gruppe [A-Z][^\\]*\\n)", f"\\1{teams_line}\\n", new_desc, count=1)
                            if teams_line not in new_desc:
                                new_desc = f"{teams_line}\\n" + new_desc
                            block = block.replace(f"DESCRIPTION:{desc}", f"DESCRIPTION:{new_desc}", 1)

                        print(f"  📅 Zugeordnet: {t0} vs. {t1}")
                        changes += 1
                        break

        return block

    parts = re.split(r"(BEGIN:VEVENT\n[\s\S]*?END:VEVENT\n)", content)
    new_parts = [process_vevent(p) if p.startswith("BEGIN:VEVENT") else p for p in parts]
    new_content = "".join(new_parts)

    if new_content != content:
        with open(ICS_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"\nKalender gespeichert ({changes} Änderungen).")
        return True
    else:
        print("\nKeine Änderungen.")
        return False


if __name__ == "__main__":
    print("Lade WM 2026 Spieldaten von ESPN...")
    matches = fetch_all_matches()
    completed = [m for m in matches if m["state"] == "post"]
    scheduled = [m for m in matches if m["state"] in ("pre", "in")]
    print(f"\n{len(completed)} abgeschlossene Spiele, {len(scheduled)} geplante/laufende Spiele\n")
    update_ics(matches)
