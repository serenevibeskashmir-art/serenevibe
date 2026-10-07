"""
Real satellite basemap for the itinerary PDF's "Tour Route Map".

How it works
------------
* A "master" satellite mosaic of the whole Kashmir valley is stitched from
  standard Web-Mercator (XYZ) tiles.
* The master is looked up in this order, so PDF generation is fast and never
  depends on a third-party server at request time in production:
    1. backend/assets/maps/kashmir_satellite.jpg (+ .json)  <- baked, committed
    2. a copy cached in the OS temp dir from an earlier live fetch
    3. a live tile fetch (≈ 80 tiles, a few seconds, then cached in /tmp)
* If none of that works, get_viewport_jpeg() returns None and the PDF falls back
  to the old stylised map, so PDF generation can never fail because of imagery.

Bake the master once (recommended) with:  python scripts/build_map_assets.py

Environment overrides
---------------------
SATELLITE_TILE_URL   XYZ template with {z} {x} {y}  (default: Esri World Imagery)
SATELLITE_ATTRIBUTION  text printed on the map (must match your tile provider)
MAP_ZOOM             tile zoom level, default 11 (~75 m / pixel)
"""
import io
import json
import logging
import math
import os
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PIL import Image, ImageFilter

log = logging.getLogger(__name__)

TILE_SIZE = 256
ZOOM = int(os.environ.get("MAP_ZOOM", "11"))
TILE_URL = os.environ.get(
    "SATELLITE_TILE_URL",
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
)
ATTRIBUTION = os.environ.get(
    "SATELLITE_ATTRIBUTION",
    "Imagery © Esri, Maxar, Earthstar Geographics, and the GIS User Community",
)
USER_AGENT = "SereneVibesKashmir-ItineraryPDF/1.0"

# (south, west, north, east) - generous, so any PDF layout/margin fits inside it
MASTER_BBOX = (33.62, 73.80, 34.56, 75.90)

ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "maps"
CACHE_DIR = Path(tempfile.gettempdir()) / "serenevibe_maps"
MASTER_NAME = "kashmir_satellite"

_lock = threading.Lock()
_master = None                 # (PIL.Image, meta dict)
_last_fetch_failure = 0.0      # don't retry a dead tile server on every PDF
_RETRY_AFTER_FAILURE_S = 300
_viewport_cache = {}


# ─── Web-Mercator helpers ────────────────────────────────────────────────────
def merc_y(lat):
    """Mercator y (radians) for a latitude in degrees."""
    r = math.radians(max(min(lat, 85.0511), -85.0511))
    return math.log(math.tan(math.pi / 4 + r / 2))


def inv_merc_y(my):
    return math.degrees(2 * math.atan(math.exp(my)) - math.pi / 2)


def world_xy(lat, lon, z):
    """Global pixel coordinates (origin top-left of the world) at zoom z."""
    n = TILE_SIZE * 2 ** z
    return (lon + 180.0) / 360.0 * n, (1.0 - merc_y(lat) / math.pi) / 2.0 * n


# ─── Building the master mosaic ──────────────────────────────────────────────
def _fetch_tile(session, z, x, y, deadline):
    url = TILE_URL.format(z=z, x=x, y=y, s="a")
    for _ in range(2):
        if time.monotonic() > deadline:
            return None
        try:
            r = session.get(url, timeout=8)
            if r.status_code == 200 and r.content:
                return Image.open(io.BytesIO(r.content)).convert("RGB")
        except Exception as exc:                      # network / decode error
            log.debug("tile %s/%s/%s failed: %s", z, x, y, exc)
    return None


def build_master(bbox=MASTER_BBOX, z=None, workers=12, budget_s=30):
    """Download + stitch tiles. Returns (image, meta) or None if anything is missing."""
    z = z or ZOOM
    south, west, north, east = bbox
    x0, y0 = world_xy(north, west, z)
    x1, y1 = world_xy(south, east, z)
    tx0, tx1 = int(x0 // TILE_SIZE), int(x1 // TILE_SIZE)
    ty0, ty1 = int(y0 // TILE_SIZE), int(y1 // TILE_SIZE)
    coords = [(tx, ty) for ty in range(ty0, ty1 + 1) for tx in range(tx0, tx1 + 1)]

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    deadline = time.monotonic() + budget_s
    with ThreadPoolExecutor(max_workers=workers) as pool:
        tiles = list(pool.map(lambda c: _fetch_tile(session, z, c[0], c[1], deadline), coords))
    if any(t is None for t in tiles):
        log.warning("satellite_map: %d/%d tiles missing - not using imagery",
                    sum(t is None for t in tiles), len(tiles))
        return None

    canvas = Image.new("RGB", ((tx1 - tx0 + 1) * TILE_SIZE, (ty1 - ty0 + 1) * TILE_SIZE))
    for (tx, ty), tile in zip(coords, tiles):
        canvas.paste(tile, ((tx - tx0) * TILE_SIZE, (ty - ty0) * TILE_SIZE))
    left, top = int(x0 - tx0 * TILE_SIZE), int(y0 - ty0 * TILE_SIZE)
    right, bottom = int(x1 - tx0 * TILE_SIZE), int(y1 - ty0 * TILE_SIZE)
    img = canvas.crop((left, top, right, bottom))
    meta = {"z": z, "x0": tx0 * TILE_SIZE + left, "y0": ty0 * TILE_SIZE + top,
            "w": img.width, "h": img.height, "attribution": ATTRIBUTION}
    return img, meta


def save_master(img, meta, directory=ASSET_DIR):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    img.save(directory / f"{MASTER_NAME}.jpg", "JPEG", quality=86, optimize=True, progressive=True)
    (directory / f"{MASTER_NAME}.json").write_text(json.dumps(meta, indent=2))


def _read_master(directory):
    jpg, js = Path(directory) / f"{MASTER_NAME}.jpg", Path(directory) / f"{MASTER_NAME}.json"
    if jpg.exists() and js.exists():
        try:
            img = Image.open(jpg).convert("RGB")
            img.load()
            return img, json.loads(js.read_text())
        except Exception as exc:
            log.warning("satellite_map: could not read %s: %s", jpg, exc)
    return None


def load_master(allow_fetch=True):
    global _master, _last_fetch_failure
    with _lock:
        if _master:
            return _master
        for d in (ASSET_DIR, CACHE_DIR):
            found = _read_master(d)
            if found:
                _master = found
                return _master
        if not allow_fetch or time.time() - _last_fetch_failure < _RETRY_AFTER_FAILURE_S:
            return None
        built = build_master()
        if not built:
            _last_fetch_failure = time.time()
            return None
        try:
            save_master(*built, directory=CACHE_DIR)
        except Exception as exc:                          # read-only FS etc. - not fatal
            log.debug("satellite_map: could not cache master: %s", exc)
        _master = built
        return _master


# ─── What the PDF asks for ───────────────────────────────────────────────────
def get_viewport_jpeg(south, west, north, east, max_px=2200):
    """
    JPEG bytes of the satellite imagery for exactly this lat/lon window
    (Mercator-true, so it lines up with a Mercator projection of the same window),
    or None if imagery is unavailable / the window isn't covered by the master.
    """
    key = tuple(round(v, 5) for v in (south, west, north, east)) + (max_px,)
    if key in _viewport_cache:
        return _viewport_cache[key]

    loaded = load_master()
    if not loaded:
        return None
    img, meta = loaded
    z = meta["z"]
    ax, ay = world_xy(north, west, z)
    bx, by = world_xy(south, east, z)
    box = (ax - meta["x0"], ay - meta["y0"], bx - meta["x0"], by - meta["y0"])
    if box[0] < -1 or box[1] < -1 or box[2] > meta["w"] + 1 or box[3] > meta["h"] + 1:
        log.warning("satellite_map: viewport outside master imagery %s", box)
        return None

    crop = img.crop(tuple(int(round(v)) for v in box))
    if crop.width > max_px:
        crop = crop.resize((max_px, int(round(crop.height * max_px / crop.width))), Image.LANCZOS)
        crop = crop.filter(ImageFilter.UnsharpMask(radius=1.1, percent=55, threshold=2))
    buf = io.BytesIO()
    crop.save(buf, "JPEG", quality=84, optimize=True)
    _viewport_cache[key] = buf.getvalue()
    return _viewport_cache[key]


def attribution():
    loaded = _master
    return (loaded[1].get("attribution") if loaded else None) or ATTRIBUTION
