#!/usr/bin/env python3
"""Submit all sitemap URLs to IndexNow (Bing, Yandex, Seznam, Naver).

Run after a deploy so search engines re-crawl changed pages quickly:

    python3 scripts/indexnow_submit.py

The key file must be live at https://home.wangjianshuo.com/<key>.txt
(it lives in static/<key>.txt in this repo).

POSTs go through curl: api.indexnow.org's WAF rejects python-urllib
requests with 403 but accepts identical payloads from curl.
"""
import json
import re
import subprocess
import sys
import tempfile
import urllib.request

HOST = "home.wangjianshuo.com"
KEY = "b4bbcd371088410f9d5fdfa34bc0f188"
SITEMAP = f"https://{HOST}/sitemap.xml"
ENDPOINT = "https://api.indexnow.org/indexnow"
BATCH = 10000  # IndexNow max URLs per request
# Cloudflare 403s the default python-urllib UA on the sitemap fetch.
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) indexnow-submit/1.0"


def main():
    req = urllib.request.Request(SITEMAP, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        xml = r.read().decode("utf-8")
    urls = re.findall(r"<loc>([^<]+)</loc>", xml)
    print(f"sitemap: {len(urls)} URLs")
    if not urls:
        sys.exit("no URLs found in sitemap")

    for i in range(0, len(urls), BATCH):
        batch = urls[i : i + BATCH]
        payload = {
            "host": HOST,
            "key": KEY,
            "keyLocation": f"https://{HOST}/{KEY}.txt",
            "urlList": batch,
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json") as f:
            json.dump(payload, f)
            f.flush()
            r = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                 "-X", "POST",
                 "-H", "Content-Type: application/json; charset=utf-8",
                 "-d", f"@{f.name}", ENDPOINT],
                capture_output=True, text=True,
            )
        status = r.stdout.strip()
        print(f"batch {i // BATCH + 1}: {len(batch)} URLs -> HTTP {status}")
        if status != "200":
            sys.exit(1)


if __name__ == "__main__":
    main()
