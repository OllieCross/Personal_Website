import re
import json
import time
import requests
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

LOG_FILE   = "/var/log/nginx/access.log"
OUTPUT_MD  = "/data/visitors.md"
CACHE_FILE = "/data/ip_cache.json"
STATE_FILE = "/data/state.json"

# nginx log_format: '$remote_addr [$time_local] "$request" $status "$http_user_agent"'
LOG_RE = re.compile(
    r'^(\S+) \[([^\]]+)\] "(\S+) (\S+) [^"]*" (\d+) "([^"]*)"'
)

SKIP_EXTENSIONS = {
    ".css", ".js", ".jpg", ".jpeg", ".webp", ".png", ".svg",
    ".mov", ".mp4", ".woff2", ".woff", ".ico", ".webmanifest", ".map",
}
BOT_KEYWORDS = [
    "bot", "crawler", "spider", "slurp", "baidu", "yandex",
    "bingpreview", "facebookexternalhit", "pinterest", "semrush",
    "ahrefsbot", "mj12bot", "dotbot",
]


def is_bot(ua: str) -> bool:
    ua = ua.lower()
    return any(k in ua for k in BOT_KEYWORDS)


def is_page_request(method: str, path: str, status: str) -> bool:
    if method not in ("GET", "HEAD"):
        return False
    if int(status) >= 400:
        return False
    ext = Path(path.split("?")[0]).suffix.lower()
    return ext not in SKIP_EXTENSIONS


def get_country(ip: str, cache: dict) -> str:
    if ip in cache:
        return cache[ip]
    try:
        r = requests.get(
            f"http://ip-api.com/json/{ip}?fields=country",
            timeout=5,
        )
        country = r.json().get("country", "Unknown")
    except Exception:
        country = "Unknown"
    cache[ip] = country
    save_cache(cache)
    return country


def load_json(path: str, default):
    p = Path(path)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return default


def save_json(path: str, data):
    Path(path).write_text(json.dumps(data, indent=2))


def load_cache() -> dict:
    return load_json(CACHE_FILE, {})


def save_cache(cache: dict):
    save_json(CACHE_FILE, cache)


def write_markdown(total_views: int, unique_ips: int, countries: dict, recent: list):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# Visitor Statistics",
        "",
        f"_Last updated: {now}_",
        "",
        "## Summary",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total page views | {total_views} |",
        f"| Unique visitors (IP) | {unique_ips} |",
        f"| Countries | {len(countries)} |",
        "",
        "## Visitors by Country",
        "",
        "| Country | Views |",
        "|---------|-------|",
    ]
    for country, count in sorted(countries.items(), key=lambda x: -x[1]):
        lines.append(f"| {country} | {count} |")

    lines += [
        "",
        "## Recent Page Views (last 200)",
        "",
        "| Time (UTC) | IP (masked) | Country | Path |",
        "|------------|-------------|---------|------|",
    ]
    for entry in recent[-200:]:
        masked = entry["ip"][:6] + "..."
        lines.append(
            f"| {entry['time']} | {masked} | {entry['country']} | {entry['path']} |"
        )

    Path(OUTPUT_MD).write_text("\n".join(lines) + "\n")


def process_logs():
    state   = load_json(STATE_FILE, {"offset": 0, "total_views": 0, "unique_ips": []})
    cache   = load_cache()
    countries = load_json("/data/countries.json", {})
    recent    = load_json("/data/recent.json", [])

    log_path = Path(LOG_FILE)
    if not log_path.exists():
        return

    file_size = log_path.stat().st_size
    offset    = state.get("offset", 0)

    # Handle log rotation (file shrank)
    if file_size < offset:
        offset = 0

    if file_size == offset:
        return

    unique_ips = set(state.get("unique_ips", []))
    total_views = state.get("total_views", 0)

    with log_path.open("r", errors="replace") as f:
        f.seek(offset)
        new_lines = f.readlines()
        new_offset = f.tell()

    new_entries = 0
    for line in new_lines:
        m = LOG_RE.match(line.strip())
        if not m:
            continue
        ip, ts, method, path, status, ua = m.groups()

        if is_bot(ua) or not is_page_request(method, path, status):
            continue

        country = get_country(ip, cache)
        # ip-api returns empty or "Unknown" for private/local IPs
        if country in ("", "Unknown") and (
            ip.startswith("127.") or ip.startswith("10.") or ip.startswith("172.") or ip.startswith("192.168.")
        ):
            country = "Local"

        unique_ips.add(ip)
        total_views += 1
        countries[country] = countries.get(country, 0) + 1

        try:
            dt = datetime.strptime(ts.split()[0], "%d/%b/%Y:%H:%M:%S")
            clean_ts = dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            clean_ts = ts

        recent.append({"time": clean_ts, "ip": ip, "country": country, "path": path})
        new_entries += 1
        time.sleep(0.05)  # stay well under ip-api 45 req/min limit

    if new_entries > 0 or not Path(OUTPUT_MD).exists():
        write_markdown(total_views, len(unique_ips), countries, recent)
        save_json("/data/countries.json", countries)
        save_json("/data/recent.json", recent[-200:])
        print(f"[{datetime.now(timezone.utc).isoformat()}] Processed {new_entries} new entries. Total: {total_views} views, {len(unique_ips)} unique IPs.")

    save_json(STATE_FILE, {"offset": new_offset, "total_views": total_views, "unique_ips": list(unique_ips)})


if __name__ == "__main__":
    print("Visitor tracker started.")
    Path("/data").mkdir(exist_ok=True)
    while True:
        try:
            process_logs()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(300)  # run every 5 minutes
