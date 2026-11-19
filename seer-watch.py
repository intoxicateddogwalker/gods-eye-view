#!/usr/bin/env python3
"""Seer watch — the always-on half of the swarm.

Runs in GitHub Actions every 15 minutes (see seer-watch.yml).
Plain CPU, no models: it pulls the keyless feeds, runs the ACTIVE
minis' rule checks, scores expired predictions per mini, and writes
data/seer/predictions.json + data/seer/minis.json.

The LLM coordinator + Chronos live on the Hugging Face Space and
write richer predictions on demand; this script keeps fresh
predictions flowing while the Space sleeps.
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swarm  # noqa: E402  (the 500-mini registry, same folder)


def fetch(url, timeout=20):
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Seer-watch/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001 - feeds fail; Seer keeps going
        print(f"fetch failed {url}: {e}")
        return {}


def load(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return default


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def main():
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat(timespec="seconds")

    preds_path = "data/seer/predictions.json"
    minis_path = "data/seer/minis.json"
    preds = load(preds_path, {
        "version": 2, "generated_at": now_iso, "predictions": [],
        "scoreboard": {"total_scored": 0, "hits": 0, "misses": 0,
                       "accuracy": None, "by_kind": {}},
        "lessons": []})
    reg = load(minis_path, None)
    minis = reg["minis"] if reg and reg.get("minis") else swarm.build_registry()
    by_id = {m["id"]: m for m in minis}

    # --- observe the world right now (same feeds as the Space) ---
    quakes = fetch("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson")
    feats = quakes.get("features", []) if isinstance(quakes, dict) else []
    mags = [f["properties"].get("mag") for f in feats
            if f.get("properties", {}).get("mag") is not None]
    places = [f["properties"].get("place", "") for f in feats]
    obs = {
        "quakes_m5_plus": sum(1 for m in mags if m >= 5.0),
        "oklahoma_quakes": sum(1 for p in places if "Oklahoma" in p),
    }
    eonet = fetch("https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=100")
    events = eonet.get("events", []) if isinstance(eonet, dict) else []
    obs["wildfires"] = sum(
        1 for ev in events
        for c in ev.get("categories", [])
        if c.get("title") == "Wildfires")
    flights = fetch("https://raw.githubusercontent.com/intoxicateddogwalker/gods-eye-view/main/data/flights.json")
    obs["civil_flights"] = len(flights.get("ac", [])) if isinstance(flights, dict) else 0
    mil = fetch("https://raw.githubusercontent.com/intoxicateddogwalker/gods-eye-view/main/data/military.json")
    obs["military_flights"] = len(mil.get("ac", [])) if isinstance(mil, dict) else 0
    tulsa = fetch("https://api.open-meteo.com/v1/forecast?latitude=36.15&longitude=-95.99"
                  "&current=temperature_2m,wind_speed_10m,precipitation")
    cur = tulsa.get("current", {}) if isinstance(tulsa, dict) else {}
    obs["tulsa_wind_kmh"] = cur.get("wind_speed_10m")
    obs["tulsa_precip_mm"] = cur.get("precipitation")
    obs["severe_weather"] = bool(
        (cur.get("wind_speed_10m") or 0) >= 60
        or (cur.get("precipitation") or 0) >= 10)

    # --- score expired predictions, per mini (the learning loop) ---
    sb = preds.setdefault("scoreboard",
                          {"total_scored": 0, "hits": 0, "misses": 0,
                           "accuracy": None, "by_kind": {}})
    for p in preds["predictions"]:
        if p.get("status") != "open":
            continue
        end = p.get("window", {}).get("end", "")
        if not end or end > now_iso:
            continue  # window still open
        kind = p.get("kind")
        hit = None
        if kind == "quake_aftershock":
            hit = obs["quakes_m5_plus"] >= 1
        elif kind == "fire_spread":
            hit = obs["wildfires"] > 0
        elif kind == "weather_impact":
            hit = obs["severe_weather"]
        elif kind == "flight_density":
            hit = obs["civil_flights"] > 0  # v1: any live traffic counts
        if hit is None:
            p["status"] = "expired"
            continue
        p["status"] = "hit" if hit else "miss"
        p["scored_at"] = now_iso
        p["outcome"] = ("Came true." if hit else "Did not come true.") + \
            f" Observed: {obs}"
        sb["total_scored"] += 1
        sb["hits" if hit else "misses"] += 1
        byk = sb["by_kind"].setdefault(kind, {"hits": 0, "misses": 0, "accuracy": None})
        byk["hits" if hit else "misses"] += 1
        n = byk["hits"] + byk["misses"]
        byk["accuracy"] = round(byk["hits"] / n, 3)
        for mid in p.get("mini_ids", []):
            if mid in by_id:
                swarm.record_outcome(by_id[mid], hit)
        if not hit:
            preds.setdefault("lessons", []).append({
                "prediction_id": p.get("id"),
                "lesson": f"{p.get('title')}: predicted '{p.get('prediction')}' "
                          f"but it did not happen. Check the basis before repeating it.",
                "recorded_at": now_iso,
            })
    if sb["total_scored"]:
        sb["accuracy"] = round(sb["hits"] / sb["total_scored"], 3)

    # --- v1 rule-based predictions from the active minis ---
    # (The LLM coordinator on the Space writes richer ones on demand;
    # the Action keeps fresh predictions flowing while it sleeps.)
    stamp = now.strftime("%Y%m%d%H%M")
    window_end = (now + timedelta(hours=6)).isoformat(timespec="seconds")
    new_preds = []
    if obs["quakes_m5_plus"] >= 1:
        new_preds.append({
            "id": f"pred-{stamp}-q1", "kind": "quake_aftershock",
            "title": "Aftershocks likely after M5+ quake",
            "region": {"name": "global", "lat": 0, "lon": 0, "radius_km": 1000},
            "prediction": "At least one M4.5+ aftershock will occur within 6 hours.",
            "confidence": 0.72,
            "window": {"start": now_iso, "end": window_end},
            "basis": f"{obs['quakes_m5_plus']} M5+ quake(s) in 24h (USGS).",
            "mini_ids": ["quake-global-aftershock", "quake-global-trend"],
            "status": "open", "outcome": None, "scored_at": None})
    open_titles = {p.get("title") for p in preds["predictions"]
                   if p.get("status") == "open"}
    for p in new_preds:
        if p["title"] not in open_titles:
            preds["predictions"].append(p)
    preds["generated_at"] = now_iso
    preds["generated_by"] = "seer-swarm/0.1.0 (watch Action)"

    save(preds_path, preds)
    save(minis_path, {"version": 1, "generated_by": "seer-swarm/0.1.0",
                      "minis": minis})
    print(f"scored to {sb['total_scored']} total "
          f"(accuracy {sb.get('accuracy')}); "
          f"{len(new_preds)} new rule predictions; "
          f"{sum(1 for m in minis if m['status'] == 'active')} minis active")


if __name__ == "__main__":
    main()
