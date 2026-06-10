#!/usr/bin/env python3
"""Submit all sitemap URLs to IndexNow (Bing, Yandex, Seznam, Naver).

Run after a deploy so search engines re-crawl changed pages quickly:

    python3 scripts/indexnow_submit.py

The key file must be live at https://home.wangjianshuo.com/<key>.txt
(it lives in static/<key>.txt in this repo).
"""
import json
import re
import sys
import urllib.request

HOST = "home.wangjianshuo.com"
KEY = "b4bbcd371088410f9d5fdfa34bc0f188"
SITEMAP = f"https://{HOST}/sitemap.xml"
ENDPOINT = "https://api.indexnow.org/indexnow"
BATCH = 10000  # IndexNow max URLs per request


def main():
    with urllib.request.urlopen(SITEMAP, timeout=60) as r:
        xml = r.read().decode("utf-8")
    urls = re.findall(r"<loc>([^<]+)</loc>", xml)
    print(f"sitemap: {len(urls)} URLs")
    if not urls:
        sys.exit("no URLs found in sitemap")

    for i in range(0, len(urls), BATCH):
        batch = urls[i : i + BATCH]
        payload = json.dumps(
            {
                "host": HOST,
                "key": KEY,
                "keyLocation": f"https://{HOST}/{KEY}.txt",
                "urlList": batch,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            ENDPOINT,
            data=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            print(f"batch {i // BATCH + 1}: {len(batch)} URLs -> HTTP {r.status}")


if __name__ == "__main__":
    main()
