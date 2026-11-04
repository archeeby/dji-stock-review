"""Reverse-geocode DJI video coordinates with backwards-compatible string caching.

Existing resolve(video) API and metadata/location_cache.json format are preserved.
"""
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path.home() / "DroneStock"
CACHE = ROOT / "metadata" / "location_cache.json"
DETAILS_CACHE = ROOT / "metadata" / "location_details_cache.json"
BASE_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "DroneStockLocal/1.1 (personal footage metadata)"


def _load(path):
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _cached_enrichment(video):
    path = ROOT / "metadata" / "source_enrichment" / (video.stem + ".json")
    if not path.exists():
        return None
    try:
        obj = _load(path)
        source = obj.get("source", {})
        stat = video.stat()
        if (source.get("filename") != video.name or
                source.get("size_bytes") != stat.st_size or
                source.get("mtime_ns") != stat.st_mtime_ns):
            return None
        gps = obj.get("source_gps", {})
        return gps.get("latitude"), gps.get("longitude")
    except (OSError, ValueError, TypeError):
        return None


def get_gps(video):
    video = Path(video).resolve()
    coords = _cached_enrichment(video)
    if coords is None:
        result = subprocess.run(
            ["exiftool", "-j", "-n", "-GPSLatitude", "-GPSLongitude", str(video)],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(result.stdout)[0]
        coords = (data.get("GPSLatitude"), data.get("GPSLongitude"))
    lat, lon = coords
    if (not isinstance(lat, (int, float)) or isinstance(lat, bool) or
            not isinstance(lon, (int, float)) or isinstance(lon, bool)):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def _key(lat, lon):
    return f"{lat:.4f},{lon:.4f}"


def _fetch(lat, lon):
    query = urlencode({"lat": lat, "lon": lon, "format": "jsonv2",
                       "addressdetails": 1, "zoom": 16, "accept-language": "en"})
    request = Request(BASE_URL + "?" + query, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def _place(address):
    return next((address[k] for k in (
        "city", "town", "village", "city_district", "suburb", "hamlet",
        "municipality", "county", "state") if address.get(k)), None)


def _format_location(address):
    return ", ".join(x for x in (_place(address), address.get("country")) if x)


def resolve(video):
    """Original API: returns 'Place, Country' string or None."""
    gps = get_gps(video)
    if gps is None:
        return None
    lat, lon = gps
    key = _key(lat, lon)
    cache = _load(CACHE)
    cached = cache.get(key)
    if isinstance(cached, str) and "," in cached:
        return cached
    details = _load(DETAILS_CACHE).get(key)
    if isinstance(details, dict) and details.get("location"):
        location = details["location"]
    else:
        data = _fetch(lat, lon)
        location = _format_location(data.get("address", {}))
    if not location:
        return None
    cache[key] = location
    _save(CACHE, cache)
    return location


def resolve_details(video):
    """Structured location; fetched only if details are not already cached."""
    gps = get_gps(video)
    if gps is None:
        return None
    lat, lon = gps
    key = _key(lat, lon)
    details_cache = _load(DETAILS_CACHE)
    cached = details_cache.get(key)
    if isinstance(cached, dict) and cached.get("country"):
        return cached
    data = _fetch(lat, lon)
    address = data.get("address") or {}
    location = _format_location(address)
    if not location:
        return None
    details = {
        "latitude": lat, "longitude": lon,
        "location": location,
        "country": address.get("country"),
        "country_code": (address.get("country_code") or "").upper() or None,
        "region": address.get("state") or address.get("region") or address.get("county"),
        "city": _place(address),
        "address": address,
        "display_name": data.get("display_name"),
        "provider": "OpenStreetMap Nominatim",
    }
    details_cache[key] = details
    _save(DETAILS_CACHE, details_cache)
    # Do not modify old cache entries: preserve existing AI metadata consistency.
    old_cache = _load(CACHE)
    if key not in old_cache:
        old_cache[key] = location
        _save(CACHE, old_cache)
    return details


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python3 resolve_location.py VIDEO [--details]")
    video = Path(sys.argv[1]).resolve()
    if "--details" in sys.argv[2:]:
        print(json.dumps(resolve_details(video), indent=2, ensure_ascii=False))
    else:
        print("Location:", resolve(video) or "Unknown")
