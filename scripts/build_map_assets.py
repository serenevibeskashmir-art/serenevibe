#!/usr/bin/env python3
"""
One-time (re-runnable) build of the assets behind the PDF "Tour Route Map".

    python scripts/build_map_assets.py            # satellite mosaic + real road geometry
    python scripts/build_map_assets.py --no-routes  # satellite mosaic only
    python scripts/build_map_assets.py --zoom 12    # sharper (4x the tiles / file size)

Writes into backend/assets/maps/ - commit those files and the PDF generator will
use them directly (fast, offline, deterministic):

    kashmir_satellite.jpg / .json   stitched satellite imagery of the valley
    routes.json                     Srinagar -> each destination, real driving geometry (OSRM / OpenStreetMap)

Imagery default: Esri World Imagery. Check your provider's terms for commercial
PDF use, or point SATELLITE_TILE_URL / SATELLITE_ATTRIBUTION at a licensed provider
(Mapbox, MapTiler, Google, ...) before running this.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests                                           # noqa: E402
from backend.services import satellite_map as sm          # noqa: E402

STOPS = {   # keep in sync with KashmirRouteMap.STOPS (lat, lon)
    "srinagar":    (34.0837, 74.7973),
    "gulmarg":     (34.0484, 74.3805),
    "pahalgam":    (34.0161, 75.3147),
    "sonamarg":    (34.3088, 75.2969),
    "doodhpathri": (33.8700, 74.3700),
}
OSRM = "https://router.project-osrm.org/route/v1/driving/{a};{b}?overview=full&geometries=geojson"


def rdp(pts, eps):
    """Douglas-Peucker simplification (degrees) - keeps routes.json small."""
    if len(pts) < 3:
        return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1
    norm = (dx * dx + dy * dy) ** 0.5 or 1e-12
    idx, dmax = 0, 0.0
    for i in range(1, len(pts) - 1):
        d = abs(dy * pts[i][0] - dx * pts[i][1] + x2 * y1 - y2 * x1) / norm
        if d > dmax:
            idx, dmax = i, d
    if dmax <= eps:
        return [pts[0], pts[-1]]
    return rdp(pts[: idx + 1], eps)[:-1] + rdp(pts[idx:], eps)


def build_routes(out_dir):
    hub = STOPS["srinagar"]
    routes = {}
    for key, (lat, lon) in STOPS.items():
        if key == "srinagar":
            continue
        url = OSRM.format(a=f"{hub[1]},{hub[0]}", b=f"{lon},{lat}")
        data = requests.get(url, timeout=30, headers={"User-Agent": sm.USER_AGENT}).json()
        coords = data["routes"][0]["geometry"]["coordinates"]            # [lon, lat]
        pts = rdp([(la, lo) for lo, la in coords], 0.0004)
        pts[0], pts[-1] = hub, (lat, lon)                                 # pins stay exactly on the road ends
        routes[key] = [[round(a, 5), round(b, 5)] for a, b in pts]
        print(f"  route {key}: {len(coords)} -> {len(pts)} points, {data['routes'][0]['distance']/1000:.0f} km")
    (out_dir / "routes.json").write_text(json.dumps(routes))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zoom", type=int, default=sm.ZOOM)
    ap.add_argument("--no-routes", action="store_true")
    args = ap.parse_args()

    out = sm.ASSET_DIR
    out.mkdir(parents=True, exist_ok=True)
    print(f"Fetching satellite tiles at zoom {args.zoom} ...")
    built = sm.build_master(z=args.zoom, budget_s=300)
    if not built:
        sys.exit("Could not download all tiles - check your connection / SATELLITE_TILE_URL.")
    img, meta = built
    sm.save_master(img, meta, out)
    print(f"  saved {img.width}x{img.height}px -> {out/'kashmir_satellite.jpg'}")

    if not args.no_routes:
        print("Fetching road geometry from OSRM ...")
        try:
            build_routes(out)
        except Exception as exc:
            print(f"  skipped routes ({exc}); the built-in waypoints will be used instead.")
    print("Done. Commit backend/assets/maps/ to your repo.")


if __name__ == "__main__":
    main()
