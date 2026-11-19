"""
Seer swarm — 500 mini-AIs, one coordinator brain.
==================================================
Christopher's design: instead of one big brain watching everything,
500 tiny specialist AIs, each expert at its ONE job, all reporting up
to a single coordinator brain that fuses their outputs into the
predictions the user sees.

THE HONEST CONSTRAINT
---------------------
You cannot load 500 separate models at once on free Hugging Face
hardware. So the swarm is built as a MIX (the only honest workable
architecture on $0):
  * ONE shared base model does the heavy thinking: Qwen2.5-1.5B-Instruct
    is the coordinator brain, and it also does on-demand reasoning for
    the few hard specialist jobs (via specialist prompts).
  * ONE shared forecaster: amazon/chronos-2 (120M) forecasts the
    numbers for every mini that needs a numeric forecast.
  * The 500 minis themselves are tiny, fast specialists: small
    rule/statistical agents that each watch one slice of the world
    (one camera cluster, one quake zone, one flight corridor...).
    They run on plain CPU in seconds — the GitHub Action runs all of
    them every 15 minutes. They are small on purpose: small = fast,
    cheap, and easy to retrain one at a time.

Each mini keeps its OWN score. Minis that keep getting it wrong lose
trust (the coordinator listens to them less) and get adjusted; minis
that keep getting it right earn trust. That is the learning loop,
per mini.

THE 500 — the split (adds up to exactly 500)
----------------------------------------------
  200  camera-cluster minis   50 cities x 4 clusters
                                  (downtown / highway / airport / waterfront)
  100  region watchers        100 regions, each fusing all feeds for its region
   60  quake specialists      29 seismic zones x 2 + 2 global
                                  (aftershock / magnitude-trend)
   40  fire specialists       39 fire-prone regions + 1 global
   40  flight specialists     39 flight corridors / airports + 1 global
   30  weather specialists    29 storm-prone regions + 1 global
   30  ship/port specialists  29 major ports + 1 global
  ----
  500

HOME REGION (v1 focus): Tulsa + Sapulpa, Oklahoma — Christopher's home
turf. The 14 home minis are active first; the rest of the swarm is
defined and on standby, activating region by region after that.
"""

import json

# ---------------------------------------------------------------- the split

CAMERA_CLUSTERS = ["downtown", "highway", "airport", "waterfront"]

# 50 cities the camera minis cover (home cities first).
CITIES = [
    ("tulsa", "Tulsa", 36.15, -95.99),
    ("sapulpa", "Sapulpa", 36.00, -96.11),
    ("oklahoma-city", "Oklahoma City", 35.47, -97.52),
    ("new-york", "New York", 40.71, -74.01),
    ("los-angeles", "Los Angeles", 34.05, -118.24),
    ("chicago", "Chicago", 41.88, -87.63),
    ("houston", "Houston", 29.76, -95.37),
    ("phoenix", "Phoenix", 33.45, -112.07),
    ("dallas", "Dallas", 32.78, -96.80),
    ("austin", "Austin", 30.27, -97.74),
    ("san-francisco", "San Francisco", 37.77, -122.42),
    ("seattle", "Seattle", 47.61, -122.33),
    ("denver", "Denver", 39.74, -104.99),
    ("boston", "Boston", 42.36, -71.06),
    ("atlanta", "Atlanta", 33.75, -84.39),
    ("miami", "Miami", 25.76, -80.19),
    ("las-vegas", "Las Vegas", 36.17, -115.14),
    ("nashville", "Nashville", 36.16, -86.78),
    ("portland", "Portland", 45.52, -122.68),
    ("san-diego", "San Diego", 32.72, -117.16),
    ("london", "London", 51.50, -0.12),
    ("paris", "Paris", 48.85, 2.35),
    ("berlin", "Berlin", 52.52, 13.40),
    ("madrid", "Madrid", 40.42, -3.70),
    ("rome", "Rome", 41.90, 12.50),
    ("tokyo", "Tokyo", 35.68, 139.69),
    ("singapore", "Singapore", 1.35, 103.82),
    ("sydney", "Sydney", -33.87, 151.21),
    ("mumbai", "Mumbai", 19.08, 72.88),
    ("dubai", "Dubai", 25.20, 55.27),
    ("toronto", "Toronto", 43.65, -79.38),
    ("mexico-city", "Mexico City", 19.43, -99.13),
    ("sao-paulo", "Sao Paulo", -23.55, -46.63),
    ("lagos", "Lagos", 6.52, 3.37),
    ("cairo", "Cairo", 30.04, 31.24),
    ("moscow", "Moscow", 55.76, 37.62),
    ("beijing", "Beijing", 39.90, 116.41),
    ("seoul", "Seoul", 37.57, 126.98),
    ("bangkok", "Bangkok", 13.76, 100.50),
    ("jakarta", "Jakarta", -6.21, 106.85),
    ("manila", "Manila", 14.60, 120.98),
    ("delhi", "Delhi", 28.61, 77.21),
    ("karachi", "Karachi", 24.86, 67.01),
    ("istanbul", "Istanbul", 41.01, 28.98),
    ("amsterdam", "Amsterdam", 52.37, 4.90),
    ("stockholm", "Stockholm", 59.33, 18.07),
    ("dublin", "Dublin", 53.35, -6.26),
    ("auckland", "Auckland", -36.85, 174.76),
    ("cape-town", "Cape Town", -33.92, 18.42),
    ("buenos-aires", "Buenos Aires", -34.60, -58.38),
]

# 50 macro-regions (the other half of the 100 region watchers).
MACRO_REGIONS = [
    "North Atlantic", "South Atlantic", "North Pacific", "South Pacific",
    "Indian Ocean", "Arctic Ocean", "Mediterranean Sea", "Caribbean Sea",
    "Gulf of Mexico", "Bering Sea", "US West Coast", "US East Coast",
    "US Gulf Coast", "US Midwest", "US Great Lakes", "US Pacific Northwest",
    "US Southwest Desert", "Alaska", "Hawaii", "Puerto Rico",
    "Central America", "Andes", "Amazon Basin", "Patagonia",
    "West Africa", "East Africa", "Southern Africa", "Sahara",
    "Middle East", "Central Asia", "Siberia", "East Asia Coast",
    "Southeast Asia", "South Asia", "Oceania", "New Zealand",
    "Scandinavia", "Western Europe", "Eastern Europe", "Balkans",
    "Iberian Peninsula", "British Isles", "North Sea", "Baltic Sea",
    "Black Sea", "Caspian Sea", "Arabian Sea", "Bay of Bengal",
    "South China Sea", "Sea of Japan",
]

QUAKE_ZONES = [
    "japan", "indonesia", "chile", "peru", "mexico", "california",
    "alaska", "new-zealand", "turkey", "greece", "italy", "iran",
    "pakistan", "nepal", "philippines", "taiwan", "papua-new-guinea",
    "tonga", "vanuatu", "ecuador", "colombia", "iceland", "oklahoma",
    "nevada", "utah", "hawaii", "kamchatka", "kuril-islands",
    "solomon-islands",
]

FIRE_REGIONS = [
    "california", "oregon", "washington", "arizona", "texas", "oklahoma",
    "australia-nsw", "australia-victoria", "australia-queensland",
    "brazil-amazon", "greece", "spain", "portugal", "turkey",
    "siberia", "indonesia", "canada-bc", "canada-alberta", "alaska",
    "south-africa", "chile", "argentina", "france", "italy",
    "croatia", "morocco", "algeria", "india", "thailand", "vietnam",
    "congo", "angola", "madagascar", "new-zealand", "hawaii",
    "montana", "idaho", "colorado", "new-mexico",
]

FLIGHT_CORRIDORS = [
    "north-atlantic", "transpacific", "us-east-coast", "us-west-coast",
    "us-central", "europe-west", "europe-east", "middle-east",
    "asia-southeast", "asia-east", "africa-west", "africa-east",
    "south-america", "oceania", "jfk-hub", "lhr-hub", "dxb-hub",
    "sin-hub", "hnd-hub", "atl-hub", "ord-hub", "dfw-hub", "den-hub",
    "lax-hub", "cdg-hub", "ams-hub", "fra-hub", "ist-hub", "doh-hub",
    "gru-hub", "syd-hub", "bom-hub", "pek-hub", "icn-hub", "yyz-hub",
    "mad-hub", "fco-hub", "tul-hub", "okc-hub",
]

WEATHER_REGIONS = [
    "us-tornado-alley", "us-gulf-coast", "us-florida", "us-northeast",
    "us-midwest", "us-pacific-northwest", "caribbean", "bay-of-bengal",
    "south-china-sea", "philippines", "japan", "australia-north",
    "uk-ireland", "western-europe", "mediterranean", "west-africa",
    "east-africa", "india-monsoon", "southeast-asia", "central-america",
    "brazil", "argentina", "middle-east", "central-asia", "siberia",
    "alaska", "hawaii", "new-zealand", "oklahoma",
]

PORTS = [
    "shanghai", "singapore", "rotterdam", "los-angeles", "long-beach",
    "new-york", "savannah", "houston", "antwerp", "hamburg",
    "dubai", "busan", "hong-kong", "shenzhen", "ningbo", "qingdao",
    "tianjin", "kaohsiung", "tokyo", "yokohama", "sydney", "melbourne",
    "mumbai", "chennai", "durban", "cape-town", "lagos", "piraeus",
    "valencia",
]

# Home region: Tulsa + Sapulpa, Oklahoma. These 14 minis are active first.
HOME_MINI_IDS = [
    "cam-tulsa-downtown", "cam-tulsa-highway", "cam-tulsa-airport",
    "cam-tulsa-waterfront",
    "cam-sapulpa-downtown", "cam-sapulpa-highway", "cam-sapulpa-airport",
    "cam-sapulpa-waterfront",
    "region-tulsa", "region-sapulpa",
    "quake-oklahoma-aftershock", "fire-oklahoma",
    "weather-oklahoma", "flights-tul-hub",
]

# Global specialists active in v1 alongside the home minis.
# (These are real minis in the registry — the families below leave
# room for them; see build_registry.)
GLOBAL_MINI_IDS = [
    "quake-global-aftershock", "quake-global-trend",
    "fire-global", "flights-global-density",
    "weather-global-storm", "ships-global",
]

V1_ACTIVE_IDS = HOME_MINI_IDS + GLOBAL_MINI_IDS


# ---------------------------------------------------------------- registry


def _mini(mini_id, kind, name, region, status="standby"):
    return {
        "id": mini_id,
        "kind": kind,
        "name": name,
        "region": region,
        "status": status,
        "accuracy": None,          # None until it has scored predictions
        "trust": 0.5,              # coordinator weight; moves with accuracy
        "predictions_made": 0,
        "hits": 0,
        "misses": 0,
        "last_active": None,
    }


def build_registry():
    """Build all 500 minis. Deterministic — same output every run."""
    minis = []

    # 200 camera-cluster minis: 50 cities x 4 clusters.
    for slug, city, lat, lon in CITIES:
        for cluster in CAMERA_CLUSTERS:
            minis.append(_mini(
                f"cam-{slug}-{cluster}", "camera",
                f"{city} — {cluster} cameras", city))

    # 100 region watchers: 50 cities + 50 macro-regions.
    for slug, city, lat, lon in CITIES:
        minis.append(_mini(f"region-{slug}", "region",
                            f"{city} region watcher", city))
    for region in MACRO_REGIONS:
        slug = region.lower().replace(" ", "-")
        minis.append(_mini(f"region-{slug}", "region",
                            f"{region} region watcher", region))

    # 60 quake specialists: 29 zones x 2 jobs + 2 global.
    for zone in QUAKE_ZONES:
        minis.append(_mini(f"quake-{zone}-aftershock", "quake",
                            f"{zone} aftershock watcher", zone))
        minis.append(_mini(f"quake-{zone}-trend", "quake",
                            f"{zone} magnitude-trend watcher", zone))
    minis.append(_mini("quake-global-aftershock", "quake",
                        "Global aftershock watcher", "global"))
    minis.append(_mini("quake-global-trend", "quake",
                        "Global magnitude-trend watcher", "global"))

    # 40 fire specialists: 39 regions + 1 global.
    for region in FIRE_REGIONS:
        minis.append(_mini(f"fire-{region}", "fire",
                            f"{region} fire watcher", region))
    minis.append(_mini("fire-global", "fire",
                        "Global fire watcher", "global"))

    # 40 flight specialists: 39 corridors + 1 global.
    for corridor in FLIGHT_CORRIDORS:
        minis.append(_mini(f"flights-{corridor}", "flight",
                            f"{corridor} flight watcher", corridor))
    minis.append(_mini("flights-global-density", "flight",
                        "Global flight-density watcher", "global"))

    # 30 weather specialists: 29 regions + 1 global.
    for region in WEATHER_REGIONS:
        minis.append(_mini(f"weather-{region}", "weather",
                            f"{region} weather watcher", region))
    minis.append(_mini("weather-global-storm", "weather",
                        "Global storm watcher", "global"))

    # 30 ship/port specialists: 29 ports + 1 global.
    for port in PORTS:
        minis.append(_mini(f"ships-{port}", "ship",
                            f"{port} port watcher", port))
    minis.append(_mini("ships-global", "ship",
                        "Global shipping watcher", "global"))

    # Satellite tracking is handled by the region watchers + the
    # coordinator brain (it is a feed, not a separate mini family),
    # which keeps the swarm at exactly 500.
    assert len(minis) == 500, f"swarm must be exactly 500, got {len(minis)}"

    for m in minis:
        if m["id"] in V1_ACTIVE_IDS:
            m["status"] = "active"
    return minis


def swarm_summary(minis):
    """Counts by kind and status, for the dashboard."""
    by_kind, by_status = {}, {}
    for m in minis:
        by_kind[m["kind"]] = by_kind.get(m["kind"], 0) + 1
        by_status[m["status"]] = by_status.get(m["status"], 0) + 1
    scored = [m for m in minis if m["accuracy"] is not None]
    return {
        "total": len(minis),
        "by_kind": by_kind,
        "by_status": by_status,
        "active": by_status.get("active", 0),
        "standby": by_status.get("standby", 0),
        "scored_minis": len(scored),
        "mean_accuracy": (
            round(sum(m["accuracy"] for m in scored) / len(scored), 3)
            if scored else None
        ),
    }


def home_minis(minis):
    """The 14 Tulsa/Sapulpa home minis, in home order."""
    by_id = {m["id"]: m for m in minis}
    return [by_id[i] for i in HOME_MINI_IDS if i in by_id]


def update_trust(mini):
    """Trust follows accuracy, smoothed so one miss does not kill a mini.

    trust = 0.5 + (accuracy - 0.5) once it has 5+ scored predictions;
    below 5 scored, trust stays near the 0.5 prior.
    """
    n = mini["hits"] + mini["misses"]
    if n == 0 or mini["accuracy"] is None:
        mini["trust"] = 0.5
        return
    weight = min(n, 20) / 20.0  # full weight after 20 scored predictions
    mini["trust"] = round(0.5 + (mini["accuracy"] - 0.5) * weight, 3)


def record_outcome(mini, hit):
    """Score one prediction for one mini; update its accuracy + trust."""
    mini["predictions_made"] += 1
    if hit:
        mini["hits"] += 1
    else:
        mini["misses"] += 1
    n = mini["hits"] + mini["misses"]
    mini["accuracy"] = round(mini["hits"] / n, 3)
    update_trust(mini)


def needs_retraining(mini):
    """A mini needs adjusting when it is confidently wrong: 10+ scored
    predictions and accuracy under 0.4. v1 adjustment = threshold/prompt
    change; LoRA retraining is phase 2 (see learning-loop.md)."""
    n = mini["hits"] + mini["misses"]
    return n >= 10 and (mini["accuracy"] or 0) < 0.4


if __name__ == "__main__":
    registry = build_registry()
    print(json.dumps(swarm_summary(registry), indent=2))
    with open("minis.json", "w", encoding="utf-8") as fh:
        json.dump({"version": 1, "generated_by": "seer-swarm/0.1.0",
                   "minis": registry}, fh, indent=2)
    print(f"wrote minis.json with {len(registry)} minis")
