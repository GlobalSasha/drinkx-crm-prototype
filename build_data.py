#!/usr/bin/env python3
"""Build data.js for prototype from drinkx-client-map CSV files."""
import csv
import json
import ast
import re
import random
from collections import defaultdict
from pathlib import Path

random.seed(42)  # reproducible

BASE = Path("/Users/aleksandrhvastunov/Downloads/drinkx-client-map-v0.5-linkedin-industry-enriched")
OUT = Path("/Users/aleksandrhvastunov/Desktop/crm-prototype/data.js")

SEGMENT_LABELS = {
    "food_retail": "Продуктовый ритейл",
    "non_food_retail": "Непродуктовый ритейл",
    "coffee_shops": "Кофейни и кафе",
    "qsr_fast_food": "QSR / Fast Food",
    "gas_stations": "АЗС / дорожный foodservice",
    "coffee_equipment_distributors": "Дистрибьюторы оборудования",
}

SEGMENT_FROM_FOLDER = {
    "01_food_retail": "food_retail",
    "02_non_food_retail": "non_food_retail",
    "03_coffee_shops": "coffee_shops",
    "04_qsr_fast_food": "qsr_fast_food",
    "05_gas_stations": "gas_stations",
    "06_coffee_equipment_distributors": "coffee_equipment_distributors",
}


def safe_list(s):
    """Parse Python-list-as-string to actual list. Empty/malformed → []."""
    if not s or not s.strip():
        return []
    s = s.strip()
    if s == "[]":
        return []
    try:
        return ast.literal_eval(s)
    except Exception:
        # fallback: try to split by ', ' if it looks like list-ish
        return [s.strip("[]'\"")]


def parse_person_str(s):
    """Decision Makers/People to Verify items have format:
    'Name | Title | Role | Source | Confidence' or shorter.
    """
    parts = [p.strip() for p in s.split("|")]
    out = {"name": parts[0] if parts else ""}
    if len(parts) > 1:
        out["title"] = parts[1]
    if len(parts) > 2:
        out["role"] = parts[2]
    if len(parts) > 3:
        out["source"] = parts[3]
    if len(parts) > 4:
        out["confidence"] = parts[4]
    return out


def parse_entity(entity_str):
    """Format: 'Client Name | file=path/to/file.md | website=https://...'"""
    parts = [p.strip() for p in entity_str.split("|")]
    info = {"name": parts[0]}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            info[k.strip()] = v.strip()
    return info


def slugify(s):
    s = re.sub(r"[^a-zа-яё0-9-]+", "-", s.lower(), flags=re.IGNORECASE)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:60]


def load_linkedin_contacts():
    """Group LinkedIn contacts by client_name."""
    by_client = defaultdict(list)
    p = BASE / "data" / "linkedin_assistant_contacts_v0.5.csv"
    if not p.exists():
        return by_client
    with open(p, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cn = row.get("client_name", "").strip()
            if not cn:
                continue
            by_client[cn].append({
                "name": row.get("person_name", ""),
                "title": row.get("current_title", ""),
                "role": row.get("relevance_role", ""),
                "linkedin_url": row.get("linkedin_url", ""),
                "tier": row.get("tier", ""),
                "next_action": row.get("next_action", ""),
                "company_on_linkedin": row.get("company_on_linkedin", ""),
                "verification_status": row.get("verification_status", ""),
            })
    return by_client


def load_outreach_tiers():
    """Map (client_name OR person) → tier info."""
    p = BASE / "data" / "outreach_tiers_v0.5.csv"
    by_client = defaultdict(list)
    if not p.exists():
        return by_client
    with open(p, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cn = row.get("client_name", "").strip()
            if not cn:
                continue
            by_client[cn].append({
                "person_name": row.get("person_name", ""),
                "tier": row.get("tier", ""),
                "title": row.get("title", ""),
                "next_action": row.get("next_action", ""),
            })
    return by_client


PRIORITY_A_CLIENTS = {
    "X5 Group", "Магнит", "Лента", "ВкусВилл", "Пятёрочка", "Перекрёсток", "Чижик",
    "Яндекс Лавка", "Ozon Fresh", "Дикси", "Азбука вкуса",
    "Lemana PRO", "Петрович",
    "Stars Coffee", "Дринкит", "Правда Кофе",
    "Вкусно — и точка", "Rostic's", "Burger King Россия",
    "Газпромнефть АЗС", "ЛУКОЙЛ АЗС / Teboil", "Роснефть АЗС", "Татнефть АЗС",
    "АЗС Трасса", "ЕКА", "Teboil", "Башнефть АЗС",
    "Dr.Coffee Россия / K-Rus",
}


def derive_stage(tier, seg, has_signals):
    """Distribute leads into pipeline stages by heuristic."""
    r = random.random()
    if tier == "Tier 1":
        if r < 0.18: return "Закрыто (won)"
        if r < 0.36: return "Согласование"
        if r < 0.55: return "Переговоры"
        if r < 0.72: return "КП отправлено"
        if r < 0.88: return "Квалификация"
        return "Новые лиды"
    elif tier == "Tier 2":
        if r < 0.04: return "Закрыто (won)"
        if r < 0.14: return "Согласование"
        if r < 0.32: return "Переговоры"
        if r < 0.52: return "КП отправлено"
        if r < 0.78: return "Квалификация"
        return "Новые лиды"
    else:  # Tier 3 / unknown
        if r < 0.06: return "Закрыто (lost)"
        if r < 0.12: return "КП отправлено"
        if r < 0.30: return "Квалификация"
        return "Новые лиды"


def biased_low(max_val, exp=2.0):
    """Random int 0..max with exponential bias toward 0 (recent)."""
    u = random.random()
    return int((u ** exp) * max_val)


def derive_deal_amount(seg):
    """Generate plausible deal amount in ₽ by segment."""
    ranges = {
        "food_retail": (8_000_000, 25_000_000),
        "non_food_retail": (5_000_000, 15_000_000),
        "coffee_shops": (1_500_000, 6_000_000),
        "qsr_fast_food": (3_500_000, 14_000_000),
        "gas_stations": (8_000_000, 30_000_000),
        "coffee_equipment_distributors": (2_500_000, 6_500_000),
    }
    lo, hi = ranges.get(seg, (1_000_000, 5_000_000))
    return round(random.uniform(lo, hi) / 100_000) * 100_000


def derive_fit_score(coffee_signals, tier, decision_makers_count):
    """Score 0-10 based on signals + tier + decision-maker availability."""
    score = 5
    if "нет упоминан" in coffee_signals.lower() or coffee_signals.strip() == "":
        score -= 1
    elif "кофе" in coffee_signals.lower() or "foodservice" in coffee_signals.lower():
        score += 2
    if tier == "Tier 1":
        score += 2
    elif tier == "Tier 2":
        score += 1
    if decision_makers_count >= 2:
        score += 1
    return max(0, min(10, score))


MANAGERS = [
    {"id": "kirill", "name": "Кирилл Перов", "av": "КП", "color": "var(--accent)", "spec": ["coffee_shops", "food_retail", "non_food_retail"]},
    {"id": "ivan", "name": "Иван Кравченко", "av": "ИК", "color": "#af52de", "spec": ["qsr_fast_food", "gas_stations"]},
    {"id": "alexey", "name": "Алексей Петров", "av": "АП", "color": "#ff9500", "spec": ["coffee_shops", "coffee_equipment_distributors", "food_retail"]},
]


def assign_manager(seg):
    """Assign manager based on specialization preference."""
    candidates = [m for m in MANAGERS if seg in m["spec"]]
    if not candidates:
        candidates = MANAGERS
    return random.choice(candidates)["id"]


def build():
    research_csv = BASE / "data" / "research_results_v0.3.csv"
    linkedin_by_client = load_linkedin_contacts()
    outreach_by_client = load_outreach_tiers()

    leads = []

    with open(research_csv, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entity_info = parse_entity(row["entity"])
            client_name = row["Client Name"].strip()
            file_path = entity_info.get("file", "")

            # Segment from file path
            seg = "unknown"
            for folder, key in SEGMENT_FROM_FOLDER.items():
                if folder in file_path:
                    seg = key
                    break

            # Decision makers
            dms = [parse_person_str(s) for s in safe_list(row["Decision Makers"]) if s.strip()]
            verify = [parse_person_str(s) for s in safe_list(row["People to Verify"]) if s.strip()]
            triggers = safe_list(row["Sales Triggers"])

            # LinkedIn contacts
            li_contacts = linkedin_by_client.get(client_name, [])

            # Tier from priority list + heuristic
            outreach = outreach_by_client.get(client_name, [])
            if client_name in PRIORITY_A_CLIENTS:
                tier = "Tier 1"
            elif outreach and outreach[0]["tier"]:
                tier = outreach[0]["tier"]
            elif li_contacts and dms:
                tier = "Tier 2"
            elif dms or li_contacts:
                tier = "Tier 2"
            else:
                tier = "Tier 3"

            stage = derive_stage(tier, seg, bool(row["Coffee and Foodservice Signals"]))
            deal = derive_deal_amount(seg)
            fit = derive_fit_score(row["Coffee and Foodservice Signals"], tier, len(dms))
            mgr = assign_manager(seg)

            # Source links
            srcs = safe_list(row["Source Links"])
            srcs_clean = [s for s in srcs if s.startswith("[")][:6]

            lead = {
                "id": slugify(client_name),
                "company_name": client_name,
                "segment": seg,
                "segment_label": SEGMENT_LABELS.get(seg, seg),
                "tier": tier,
                "priority": "A" if tier == "Tier 1" else ("B" if tier == "Tier 2" else "C"),
                "website": entity_info.get("website", ""),
                "file_ref": file_path,
                "company_overview": row["Company Overview"][:600],
                "network_scale": row["Network Scale"][:300],
                "geography": row["Geography"][:300],
                "formats": row["Formats"][:300],
                "coffee_signals": row["Coffee and Foodservice Signals"][:500],
                "sales_triggers": triggers[:6],
                "entry_route": row["Recommended Entry Route"][:400],
                "research_gaps": row["Research Gaps"][:300],
                "confidence": row["Confidence"],
                "decision_makers": dms[:5],
                "people_to_verify": verify[:5],
                "linkedin_contacts": li_contacts[:5],
                "source_links_md": srcs_clean,
                # Generated
                "stage": stage,
                "deal_amount": deal,
                "fit_score": fit,
                "assigned_to": mgr,
                "created_days_ago": biased_low(120, exp=1.5) + 1,
                "last_activity_days_ago": biased_low(20, exp=2.5),
                "is_rotting": False,  # set below
            }

            # Mark rotting if last_activity > stage threshold
            stage_rot = {"Новые лиды": 7, "Квалификация": 5, "КП отправлено": 3, "Переговоры": 5, "Согласование": 7}
            if stage in stage_rot and lead["last_activity_days_ago"] > stage_rot[stage]:
                lead["is_rotting"] = True

            leads.append(lead)

    # Stats
    by_stage = defaultdict(int)
    by_tier = defaultdict(int)
    by_seg = defaultdict(int)
    by_mgr = defaultdict(int)
    total_deal = 0
    rotting = 0
    for l in leads:
        by_stage[l["stage"]] += 1
        by_tier[l["tier"]] += 1
        by_seg[l["segment"]] += 1
        by_mgr[l["assigned_to"]] += 1
        if l["stage"] not in ("Закрыто (won)", "Закрыто (lost)"):
            total_deal += l["deal_amount"]
        if l["is_rotting"]:
            rotting += 1

    print(f"✓ Parsed {len(leads)} leads")
    print(f"  Tiers: {dict(by_tier)}")
    print(f"  Stages: {dict(by_stage)}")
    print(f"  Segments: {dict(by_seg)}")
    print(f"  Managers: {dict(by_mgr)}")
    print(f"  Total deal in pipeline: ₽{total_deal:,.0f}")
    print(f"  Rotting: {rotting}")

    # Build managers data
    mgr_stats = []
    for m in MANAGERS:
        ml = [l for l in leads if l["assigned_to"] == m["id"]]
        active = [l for l in ml if l["stage"] not in ("Закрыто (won)", "Закрыто (lost)")]
        mgr_stats.append({
            **m,
            "active_count": len(active),
            "max_active": 30,
            "load_pct": round(len(active) / 30 * 100),
            "deal_amount_total": sum(l["deal_amount"] for l in active),
            "rotting_count": sum(1 for l in ml if l["is_rotting"]),
            "won_count": sum(1 for l in ml if l["stage"] == "Закрыто (won)"),
        })

    data = {
        "leads": leads,
        "managers": mgr_stats,
        "stats": {
            "total": len(leads),
            "active_total": sum(1 for l in leads if l["stage"] not in ("Закрыто (won)", "Закрыто (lost)")),
            "deal_total": total_deal,
            "rotting": rotting,
            "by_stage": dict(by_stage),
            "by_tier": dict(by_tier),
            "by_segment": dict(by_seg),
        },
        "segment_labels": SEGMENT_LABELS,
        "stages": ["Новые лиды", "Квалификация", "КП отправлено", "Переговоры", "Согласование", "Закрыто (won)"],
    }

    js_content = "// Auto-generated from drinkx-client-map-v0.5\n"
    js_content += f"// {len(leads)} leads · ₽{total_deal/1_000_000:.1f}M in pipeline\n\n"
    js_content += "window.REAL_DATA = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n"

    OUT.write_text(js_content, encoding="utf-8")
    print(f"\n✓ Wrote {OUT} ({len(js_content)/1024:.1f} KB)")


if __name__ == "__main__":
    build()
