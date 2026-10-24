#!/usr/bin/env python3
"""Cache partilhada de distâncias rodoviárias a partir de 18 capitais de distrito.

Só utiliza GPS explícito e verificado do catálogo; nunca tenta geocodificar em
massa, nem transforma uma localidade aproximada numa partida confirmada.
Os resultados são estimativas: regresso = ida para distância e duração.
Portagens não são inventadas e continuam a ser calculadas a pedido no site.
"""
from __future__ import annotations

import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
CATALOGUE = ROOT / "eventos.json"
OUTPUT = ROOT / "rotas_precalculadas.json"
# Pontos aproximados no centro urbano; não representam moradas particulares.
CAPITAIS = {
    "aveiro": (-8.6538, 40.6405),
    "beja": (-7.8632, 38.0151),
    "braga": (-8.4265, 41.5454),
    "braganca": (-6.7567, 41.8061),
    "castelo branco": (-7.4909, 39.8222),
    "coimbra": (-8.4103, 40.2033),
    "evora": (-7.9135, 38.5714),
    "faro": (-7.9304, 37.0194),
    "guarda": (-7.2677, 40.5373),
    "leiria": (-8.8071, 39.7437),
    "lisboa": (-9.1393, 38.7223),
    "portalegre": (-7.4287, 39.2967),
    "porto": (-8.6109, 41.1496),
    "santarem": (-8.6850, 39.2369),
    "setubal": (-8.8882, 38.5244),
    "viana do castelo": (-8.8302, 41.6946),
    "vila real": (-7.7442, 41.3006),
    "viseu": (-7.9139, 40.6575),
}
ROUTE_TTL_DAYS = 90
# Poucos pedidos por execução, de forma sequencial e com intervalo > 1 segundo.
DAILY_LIMIT = max(0, min(40, int(os.getenv("TRILHARIO_ROTAS_LIMITE", "40"))))
BASE = os.getenv("TRILHARIO_ROUTER_URL", "https://router.project-osrm.org").rstrip("/")
USER_AGENT = "Trilhario/1.0 (https://github.com/lpdre/trilhario; cache de rotas públicas)"
COOLDOWN = 1.4


def coord_key(lat: float, lon: float) -> str:
    return f"{lat:.5f},{lon:.5f}"


def valid_gps(e: dict) -> bool:
    """Só aceitar posições confirmadas dentro do continente."""
    lat, lon = e.get("lat"), e.get("lon")
    return (
        e.get("verified") is True
        and isinstance(lat, (float, int)) and not isinstance(lat, bool)
        and isinstance(lon, (float, int)) and not isinstance(lon, bool)
        and 36.8 < lat < 42.2 and -9.6 < lon < -6.0
        and "confirmar" not in str(e.get("start", "")).casefold()
    )


def destinations(events: list, today: date) -> dict:
    """Deduplicar por GPS, privilegiando as caminhadas mais próximas."""
    selected = {}
    for e in sorted(events, key=lambda item: (item.get("date", ""), item.get("id", ""))):
        if not isinstance(e, dict) or str(e.get("date", "")) < today.isoformat() or not valid_gps(e):
            continue
        key = coord_key(e["lat"], e["lon"])
        if key not in selected:
            selected[key] = {"lat": e["lat"], "lon": e["lon"]}
    return selected


def load_cache() -> dict:
    if not OUTPUT.exists():
        return {"schema": 1, "origins": CAPITAIS, "locations": {}}
    data = json.loads(OUTPUT.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise ValueError("Formato da cache de rotas incompatível")
    if data.get("origins") != {key: list(value) for key, value in CAPITAIS.items()}:
        # Os centros urbanos foram alterados; não reutilizar distâncias antigas.
        return {"schema": 1, "origins": CAPITAIS, "locations": {}}
    if not isinstance(data.get("locations"), dict):
        raise ValueError("Cache de rotas sem locations")
    return data


def due(row: dict | None, today: date) -> bool:
    if not isinstance(row, dict):
        return True
    if not (isinstance(row.get("km"), (int, float)) and 0 <= row["km"] < 1600):
        return True
    if not (isinstance(row.get("minutes"), (int, float)) and 0 <= row["minutes"] < 10000):
        return True
    try:
        updated = date.fromisoformat(str(row["updated"])[:10])
    except (ValueError, KeyError, TypeError):
        return True
    return updated > today or today - updated > timedelta(days=ROUTE_TTL_DAYS)


def fetch_matrix(session: requests.Session, destination: dict, cities: list[str]) -> dict:
    """Uma consulta de matriz traz distâncias e tempos das cidades para 1 local.

    Não usar velocidade de recurso/fallback: na ausência de estrada real, não
    inventar distâncias rodoviárias.
    """
    coords = [CAPITAIS[city] for city in cities]
    coords.append((destination["lon"], destination["lat"]))
    coordinate_path = ";".join(f"{lon:.6f},{lat:.6f}" for lon, lat in coords)
    params = {
        "sources": ";".join(str(i) for i in range(len(cities))),
        "destinations": str(len(cities)),
        "annotations": "distance,duration",
    }
    response = session.get(f"{BASE}/table/v1/driving/{coordinate_path}", params=params, timeout=24)
    response.raise_for_status()
    data = response.json()
    if data.get("code") != "Ok":
        raise ValueError("Serviço de matriz sem trajecto: " + str(data.get("code")))
    dest = data.get("destinations", [])
    if len(dest) != 1 or float(dest[0].get("distance", 999999)) > 2500:
        raise ValueError("Destino demasiado longe da estrada calculada")
    distances, durations = data.get("distances"), data.get("durations")
    if not (isinstance(distances, list) and isinstance(durations, list) and
            len(distances) == len(cities) and len(durations) == len(cities)):
        raise ValueError("Matriz incompleta")
    source_waypoints = data.get("sources", [])
    today = datetime.now(timezone.utc).date().isoformat()
    computed = {}
    for i, city in enumerate(cities):
        try:
            if len(source_waypoints) != len(cities) or float(source_waypoints[i]["distance"]) > 2500:
                continue
            meters = distances[i][0]
            seconds = durations[i][0]
            if not (isinstance(meters, (int, float)) and isinstance(seconds, (int, float))):
                continue
            km, minutes = round(meters / 1000, 1), round(seconds / 60)
            if not (0 <= km < 1600 and 0 <= minutes < 10000):
                continue
            computed[city] = {"km": km, "minutes": minutes, "updated": today}
        except (IndexError, KeyError, TypeError, ValueError):
            continue
    return computed


def build_cache(today: date | None = None, budget: int = DAILY_LIMIT, requester=None) -> dict:
    today = today or date.today()
    payload = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    found = destinations(payload.get("events", []), today)
    cache = load_cache()
    old = cache["locations"]
    # Remover locais antigos, mantendo entradas partilhadas entre novos eventos.
    locations = {key: old.get(key, {"routes": {}}) for key in found}
    cache["locations"] = locations
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    requester_is_live = requester is None
    requester = requester or (lambda point, cities: fetch_matrix(session, point, cities))
    attempts, successes = 0, 0
    for key, point in found.items():
        entry = locations[key]
        if not isinstance(entry, dict):
            entry = {"routes": {}}
            locations[key] = entry
        routes = entry.get("routes")
        if not isinstance(routes, dict):
            routes = {}
            entry["routes"] = routes
        failures = entry.get("failures")
        if not isinstance(failures, dict):
            failures = {}
            entry["failures"] = failures
        pending = []
        for city in CAPITAIS:
            if not due(routes.get(city), today):
                continue
            try:
                failed_day = date.fromisoformat(str(failures.get(city, ""))[:10])
                if today - failed_day < timedelta(days=7):
                    continue
            except ValueError:
                pass
            pending.append(city)
        if not pending or attempts >= budget:
            continue
        attempts += 1
        try:
            results = requester(point, pending)
            if not isinstance(results, dict):
                raise ValueError("Resultado da matriz inválido")
            for city in pending:
                row = results.get(city)
                if isinstance(row, dict) and not due(row, today):
                    routes[city] = row
                    failures.pop(city, None)
                    successes += 1
                else:
                    failures[city] = today.isoformat()
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            for city in pending:
                failures[city] = today.isoformat()
            print(f"Matriz indisponível para {key}: {exc}")
        if requester_is_live and attempts < budget and COOLDOWN:
            time.sleep(COOLDOWN)
    session.close()
    OUTPUT.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Cache: {len(locations)} locais GPS; {attempts} consultas de matriz; {successes} distâncias guardadas.")
    return cache


if __name__ == "__main__":
    build_cache()
