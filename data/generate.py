"""
Synthetic delivery dataset generator — delivery-sql-suite, Sprint 1.

Produces a fake but realistically messy delivery dataset shaped like a
Jira-style workflow:

    Backlog -> Waiting for In Progress -> In Progress -> Waiting for Test
            -> In Test -> Done -> Released

Business rules encoded here:
  * Lead time  = pulled from Backlog  -> Released
  * Cycle time = first entry In Progress -> Done (reopens RESUME the clock)
  * Time in status is NOT stored. It is derived from consecutive transitions.

Deliberate defects are injected on purpose (see DIRT below) so the query
suite has something real to catch.
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(1842)

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)

START = datetime(2025, 9, 1, 9, 0)
WEEKS = 40

STATUSES = [
    "Backlog",
    "Waiting for In Progress",
    "In Progress",
    "Waiting for Test",
    "In Test",
    "Done",
    "Released",
]

# ---------------------------------------------------------------- teams
# DIRT: team 3 is renamed mid-dataset. Same humans, new team_id.
# A naive GROUP BY team_id splits its history in two.
TEAMS = [
    (1, "Payments", "2025-09-01", None),
    (2, "Checkout", "2025-09-01", None),
    (3, "Search", "2025-09-01", "2026-01-15"),
    (4, "Discovery", "2026-01-15", None),   # <- Search, renamed
    (5, "Platform", "2025-09-01", None),
]
TEAM_IDS_ACTIVE_EARLY = [1, 2, 3, 5]
TEAM_IDS_ACTIVE_LATE = [1, 2, 4, 5]

ASSIGNEES = {
    1: ["r.silva", "m.okafor", "j.tan"],
    2: ["l.moreau", "d.byrne"],
    3: ["a.kowalski", "p.nair", "s.rossi"],
    4: ["a.kowalski", "p.nair", "s.rossi"],
    5: ["h.ozturk", "c.mendes"],
}

EPICS = [
    (10, "Card tokenisation", 1),
    (11, "SCA compliance", 1),
    (12, "Guest checkout", 2),
    (13, "Basket persistence", 2),
    (14, "Relevance tuning", 3),
    (15, "Autocomplete", 3),
    (16, "Observability rollout", 5),
    (17, "Cost reduction", 5),
]

ISSUE_TYPES = ["Story", "Bug", "Task", "Spike"]
TYPE_WEIGHTS = [0.52, 0.28, 0.16, 0.04]

BLOCK_REASONS = [
    "Waiting on third-party API",
    "Awaiting security review",
    "Dependency not released",
    "Environment unavailable",
    "Waiting on product decision",
    "Waiting on legal sign-off",
]


def business_hours_advance(ts, hours):
    """Advance a timestamp, skipping weekends crudely but plausibly."""
    ts = ts + timedelta(hours=hours)
    while ts.weekday() >= 5:
        ts = ts + timedelta(days=1)
    return ts


def fmt(ts, style="iso"):
    if style == "iso":
        return ts.strftime("%Y-%m-%d %H:%M:%S")
    if style == "slash":                      # DIRT: mixed timestamp formats
        return ts.strftime("%d/%m/%Y %H:%M")
    raise ValueError(style)


# ------------------------------------------------------------- sprints
sprints = []
sprint_start = START
for i in range(1, WEEKS // 2 + 1):
    sprints.append(
        {
            "sprint_id": i,
            "name": f"S{i:02d}",
            "start_date": sprint_start.date().isoformat(),
            "end_date": (sprint_start + timedelta(days=13)).date().isoformat(),
        }
    )
    sprint_start += timedelta(days=14)

# ------------------------------------------------------------ releases
releases = []
rel_ts = START + timedelta(days=10)
rid = 1
while rel_ts < START + timedelta(weeks=WEEKS):
    releases.append(
        {
            "release_id": rid,
            "name": f"R-{rel_ts.strftime('%Y.%m')}-{rid:03d}",
            "released_at": fmt(rel_ts),
        }
    )
    rid += 1
    rel_ts += timedelta(days=random.choice([7, 7, 10, 14]))

issues = []
transitions = []
blockers = []
dependencies = []

issue_id = 1000
blocker_id = 1

for sp in sprints:
    sp_start = datetime.fromisoformat(sp["start_date"] + "T09:00:00")
    late = sp_start >= datetime(2026, 1, 15)
    team_pool = TEAM_IDS_ACTIVE_LATE if late else TEAM_IDS_ACTIVE_EARLY

    for team_id in team_pool:
        # throughput per team per sprint, with variation
        n = random.randint(5, 12)
        for _ in range(n):
            issue_id += 1
            itype = random.choices(ISSUE_TYPES, TYPE_WEIGHTS)[0]

            epic_candidates = [e for e in EPICS if e[2] == team_id]
            if team_id == 4:
                epic_candidates = [e for e in EPICS if e[2] == 3]
            epic_id = random.choice(epic_candidates)[0] if epic_candidates else ""

            # DIRT: story points missing on a slice of issues, and on
            # every Spike (deliberately not estimated)
            if itype == "Spike" or random.random() < 0.11:
                points = ""
            else:
                points = random.choice([1, 2, 3, 5, 5, 8, 8, 13])

            created = business_hours_advance(
                sp_start, random.uniform(-96, 40)
            )

            # ---- walk the workflow
            ts = business_hours_advance(created, random.uniform(1, 30))
            path = []
            path.append(("", "Backlog", ts))

            # queue before work starts — this is where lead time bleeds
            ts = business_hours_advance(ts, random.uniform(2, 90))
            path.append(("Backlog", "Waiting for In Progress", ts))

            ts = business_hours_advance(ts, random.uniform(1, 120))
            path.append(("Waiting for In Progress", "In Progress", ts))

            # active work
            active = random.lognormvariate(2.4, 0.7)
            ts = business_hours_advance(ts, active)
            path.append(("In Progress", "Waiting for Test", ts))

            ts = business_hours_advance(ts, random.uniform(1, 80))
            path.append(("Waiting for Test", "In Test", ts))

            ts = business_hours_advance(ts, random.lognormvariate(1.9, 0.6))
            path.append(("In Test", "Done", ts))

            # DIRT: ~9% of issues reopen from Done back to In Progress
            reopened = random.random() < 0.09
            if reopened:
                ts = business_hours_advance(ts, random.uniform(4, 120))
                path.append(("Done", "In Progress", ts))
                ts = business_hours_advance(ts, random.lognormvariate(2.1, 0.6))
                path.append(("In Progress", "Waiting for Test", ts))
                ts = business_hours_advance(ts, random.uniform(1, 60))
                path.append(("Waiting for Test", "In Test", ts))
                ts = business_hours_advance(ts, random.lognormvariate(1.7, 0.5))
                path.append(("In Test", "Done", ts))

            # release — batched, so several issues share a release
            release_id = ""
            still_open = random.random() < 0.07     # never finished
            if not still_open:
                candidates = [
                    r for r in releases
                    if datetime.fromisoformat(r["released_at"]) > ts
                ]
                if candidates:
                    rel = candidates[0]
                    release_id = rel["release_id"]
                    rel_dt = datetime.fromisoformat(rel["released_at"])
                    path.append(("Done", "Released", rel_dt))

            if still_open:
                # truncate the path somewhere mid-flow
                cut = random.randint(2, max(2, len(path) - 2))
                path = path[:cut]
                release_id = ""

            # DIRT: ~4% of issues are missing a transition row entirely
            if random.random() < 0.04 and len(path) > 3:
                drop = random.randint(1, len(path) - 2)
                path.pop(drop)

            for frm, to, when in path:
                # DIRT: ~6% of timestamps written in DD/MM/YYYY HH:MM
                style = "slash" if random.random() < 0.06 else "iso"
                transitions.append(
                    {
                        "issue_id": issue_id,
                        "from_status": frm,
                        "to_status": to,
                        "changed_at": fmt(when, style),
                        "changed_by": random.choice(ASSIGNEES[team_id]),
                    }
                )

            issues.append(
                {
                    "issue_id": issue_id,
                    "epic_id": epic_id,
                    "team_id": team_id,
                    "sprint_id": sp["sprint_id"],
                    "issue_type": itype,
                    "summary": f"{itype} {issue_id}",
                    "assignee": random.choice(ASSIGNEES[team_id]),
                    "story_points": points,
                    "created_at": fmt(created),
                    "release_id": release_id,
                }
            )

            # blockers — some still open (NULL unblocked_at)
            if random.random() < 0.18:
                b_at = business_hours_advance(created, random.uniform(20, 200))
                if random.random() < 0.2:
                    ub = ""                     # still blocked
                else:
                    ub = fmt(business_hours_advance(b_at, random.uniform(4, 300)))
                blockers.append(
                    {
                        "blocker_id": blocker_id,
                        "issue_id": issue_id,
                        "blocked_at": fmt(b_at),
                        "unblocked_at": ub,
                        "reason": random.choice(BLOCK_REASONS),
                    }
                )
                blocker_id += 1

# dependencies — cross-team, some circular-ish
all_ids = [i["issue_id"] for i in issues]
for i in issues:
    if random.random() < 0.13:
        other = random.choice(all_ids)
        if other != i["issue_id"]:
            dependencies.append(
                {"issue_id": i["issue_id"], "depends_on_issue_id": other}
            )

# DIRT: a handful of exact duplicate transition rows
for _ in range(14):
    transitions.append(random.choice(transitions).copy())

transitions.sort(key=lambda r: (r["issue_id"],))


def write(name, rows, fields):
    p = OUT / name
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"{name:22} {len(rows):>6} rows")


write("teams.csv",
      [{"team_id": t[0], "team_name": t[1], "active_from": t[2],
        "active_to": t[3] or ""} for t in TEAMS],
      ["team_id", "team_name", "active_from", "active_to"])

write("epics.csv",
      [{"epic_id": e[0], "epic_name": e[1], "owning_team_id": e[2]} for e in EPICS],
      ["epic_id", "epic_name", "owning_team_id"])

write("sprints.csv", sprints, ["sprint_id", "name", "start_date", "end_date"])
write("releases.csv", releases, ["release_id", "name", "released_at"])

write("issues.csv", issues,
      ["issue_id", "epic_id", "team_id", "sprint_id", "issue_type", "summary",
       "assignee", "story_points", "created_at", "release_id"])

write("transitions.csv", transitions,
      ["issue_id", "from_status", "to_status", "changed_at", "changed_by"])

write("blockers.csv", blockers,
      ["blocker_id", "issue_id", "blocked_at", "unblocked_at", "reason"])

write("dependencies.csv", dependencies,
      ["issue_id", "depends_on_issue_id"])
