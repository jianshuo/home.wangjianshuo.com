#!/usr/bin/env python3
"""Download off-site images referenced in content/*.md into the local tree.

TWO versions are saved per image:

  1. LINKED (display) size  -> static/archives/YYYY/MM/DD/<file>   (en)
                               static/cn/YYYY/MM/DD/<file>         (cn)
     The markdown reference is rewritten to the root-relative local path
     (/archives/... or /cn/...). THIS goes into git.

  2. ORIGINAL (biggest) size -- FLICKR ONLY -> originals/archives/... or
     originals/cn/...  (same date structure, separate tree). The true Flickr
     original (`_o`) is preferred; if unavailable, the largest derivable size
     (`_b`/`_c`/`_z`) that beats the linked size is kept. NOT referenced by any
     page and NOT committed (originals/ is git-ignored). For future use only.

The date folder comes from each post's `date:` front matter. Dead links
(404/410/non-image) are logged to scripts/dead_image_urls.txt and left
untouched in the markdown so nothing breaks. The run is resumable: existing
files are skipped.

Usage:
  python3 scripts/download_external_images.py --dry-run   # probe only, no writes
  python3 scripts/download_external_images.py             # real run
"""
import os
import re
import sys
import json
import shutil
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, 'content')
STATIC = os.path.join(ROOT, 'static')
ORIGINALS = os.path.join(ROOT, 'originals')

IMG_RE = re.compile(r'https?://[^\s"\'<>)\]]+\.(?:jpg|jpeg|png|gif|webp|bmp)', re.I)
DATE_RE = re.compile(r'^date:\s*(\d{4})-(\d{2})-(\d{2})', re.M)
OWN_HOST_RE = re.compile(r'^https?://(?:www\.|home\.)?wangjianshuo\.com|^https?://archives\.wangjianshuo\.com', re.I)
# flickr id_secret base, optional size suffix
FLICKR_BASE_RE = re.compile(r'(.*/\d+_[0-9a-f]+)(_[a-z])?\.jpg$', re.I)

UA = 'Mozilla/5.0 (image-archiver; +https://home.wangjianshuo.com)'
TIMEOUT = 30
WORKERS = 16


def is_flickr(url):
    return 'flickr' in url.lower()


def is_image(data):
    if not data or len(data) < 12:
        return False
    return (data[:3] == b'\xff\xd8\xff'              # jpeg
            or data[:8] == b'\x89PNG\r\n\x1a\n'      # png
            or data[:6] in (b'GIF87a', b'GIF89a')    # gif
            or data[:4] == b'RIFF'                   # webp
            or data[:2] == b'BM')                    # bmp


def http_get(url):
    """Return (status, bytes). status is int or 'ERR:<type>'."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return (r.status, r.read())
    except urllib.error.HTTPError as e:
        return (e.code, b'')
    except Exception as e:  # noqa: BLE001
        return ('ERR:%s' % type(e).__name__, b'')


def collect():
    """Build download tasks + per-file rewrite refs.

    Returns (tasks, file_refs):
      tasks: dict static_abs -> {url, static_abs, static_rel, orig_dir, flickr}
      file_refs: dict md_path -> list of (url, static_rel, static_abs)
    """
    tasks = {}
    file_refs = {}
    for lang in ('en', 'cn'):
        d = os.path.join(CONTENT, lang)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if not name.endswith('.md'):
                continue
            path = os.path.join(d, name)
            with open(path, encoding='utf-8') as f:
                txt = f.read()
            dm = DATE_RE.search(txt)
            if not dm:
                continue
            y, mo, da = dm.groups()
            refs = []
            for url in IMG_RE.findall(txt):
                if OWN_HOST_RE.match(url):
                    continue
                fn = os.path.basename(url.split('?', 1)[0])
                # require the path itself (not a query string) to be an image,
                # else it's noise like a search URL with .gif buried in params
                if not re.search(r'\.(?:jpg|jpeg|png|gif|webp|bmp)$', fn, re.I):
                    continue
                if lang == 'en':
                    static_rel = '/archives/%s/%s/%s/%s' % (y, mo, da, fn)
                    static_abs = os.path.join(STATIC, 'archives', y, mo, da, fn)
                    orig_dir = os.path.join(ORIGINALS, 'archives', y, mo, da)
                else:
                    static_rel = '/cn/%s/%s/%s/%s' % (y, mo, da, fn)
                    static_abs = os.path.join(STATIC, 'cn', y, mo, da, fn)
                    orig_dir = os.path.join(ORIGINALS, 'cn', y, mo, da)
                refs.append((url, static_rel, static_abs))
                tasks.setdefault(static_abs, {
                    'url': url, 'static_abs': static_abs, 'static_rel': static_rel,
                    'orig_dir': orig_dir, 'flickr': is_flickr(url),
                })
            if refs:
                file_refs[path] = refs
    return tasks, file_refs


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(data)


def fetch_original(url, orig_dir, linked_size):
    """Flickr only: save the biggest version into the originals tree.
    Returns ('saved'|'none', bytes_written)."""
    m = FLICKR_BASE_RE.match(url)
    if not m:
        return ('none', 0)
    base, suf = m.group(1), (m.group(2) or '')

    # If the linked URL is already the original, mirror it into originals.
    if suf == '_o':
        dest = os.path.join(orig_dir, os.path.basename(url))
        if os.path.exists(dest):
            return ('saved', os.path.getsize(dest))
        st, data = http_get(url)
        if st == 200 and is_image(data):
            save(dest, data)
            return ('saved', len(data))
        return ('none', 0)

    # Prefer the true original (_o); fall back to the biggest derivable size.
    for s in ('_o', '_b', '_c', '_z'):
        cu = '%s%s.jpg' % (base, s)
        if cu == url:
            continue
        dest = os.path.join(orig_dir, os.path.basename(cu))
        if os.path.exists(dest):
            return ('saved', os.path.getsize(dest))
        st, data = http_get(cu)
        if st == 200 and is_image(data):
            # _o is the canonical original -> always keep. Others only if bigger.
            if s == '_o' or len(data) > linked_size:
                save(dest, data)
                return ('saved', len(data))
    return ('none', 0)


def run_task(t):
    """Download linked (-> static) and, for flickr, original (-> originals).
    Returns dict with status fields."""
    res = {'static_abs': t['static_abs'], 'linked': None, 'orig': 'skip',
           'linked_bytes': 0, 'orig_bytes': 0, 'status': None, 'url': t['url']}
    # linked / display version
    if os.path.exists(t['static_abs']) and os.path.getsize(t['static_abs']) > 0:
        res['linked'] = 'exists'
        res['linked_bytes'] = os.path.getsize(t['static_abs'])
    else:
        st, data = http_get(t['url'])
        res['status'] = st
        if st == 200 and is_image(data):
            save(t['static_abs'], data)
            res['linked'] = 'ok'
            res['linked_bytes'] = len(data)
        else:
            res['linked'] = 'dead'
            return res  # don't chase original for a dead link
    # original (flickr only)
    if t['flickr']:
        status, nb = fetch_original(t['url'], t['orig_dir'], res['linked_bytes'])
        res['orig'] = status
        res['orig_bytes'] = nb
    return res


def human(n):
    for u in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024:
            return '%.1f %s' % (n, u)
        n /= 1024
    return '%.1f PB' % n


def real_run():
    tasks, file_refs = collect()
    items = list(tasks.values())
    print('Unique download targets: %d' % len(items), flush=True)
    print('Markdown files to rewrite: %d' % len(file_refs), flush=True)

    ok = {}             # static_abs -> True if linked saved/exists
    counts = {'ok': 0, 'exists': 0, 'dead': 0}
    orig_counts = {'saved': 0, 'none': 0, 'skip': 0}
    linked_bytes = orig_bytes = 0
    dead_urls = []
    done = 0

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(run_task, t) for t in items]
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            ok[r['static_abs']] = (r['linked'] in ('ok', 'exists'))
            counts[r['linked']] = counts.get(r['linked'], 0) + 1
            orig_counts[r['orig']] = orig_counts.get(r['orig'], 0) + 1
            linked_bytes += r['linked_bytes'] if r['linked'] == 'ok' else 0
            orig_bytes += r['orig_bytes'] if r['orig'] == 'saved' else 0
            if r['linked'] == 'dead':
                dead_urls.append((r['status'], r['url']))
            if done % 100 == 0:
                print('  %d/%d  linked-ok=%d exists=%d dead=%d | orig-saved=%d  '
                      'static+%s originals+%s'
                      % (done, len(items), counts.get('ok', 0), counts.get('exists', 0),
                         counts.get('dead', 0), orig_counts.get('saved', 0),
                         human(linked_bytes), human(orig_bytes)), flush=True)

    # rewrite markdown: replace each successfully-downloaded url with its local rel
    rewritten = 0
    for md, refs in file_refs.items():
        with open(md, encoding='utf-8') as f:
            txt = f.read()
        orig_txt = txt
        # longest url first so a short url isn't replaced inside a longer one
        for url, rel, sabs in sorted(refs, key=lambda x: -len(x[0])):
            if ok.get(sabs):
                txt = txt.replace(url, rel)
        if txt != orig_txt:
            with open(md, 'w', encoding='utf-8') as f:
                f.write(txt)
            rewritten += 1

    if dead_urls:
        with open(os.path.join(ROOT, 'scripts', 'dead_image_urls.txt'), 'w', encoding='utf-8') as f:
            for st, u in sorted(dead_urls, key=lambda x: (str(x[0]), x[1])):
                f.write('%s\t%s\n' % (st, u))

    print('\n==================== RUN COMPLETE ====================')
    print('Linked downloaded : %d  (already present: %d)' % (counts.get('ok', 0), counts.get('exists', 0)))
    print('Dead / skipped    : %d  (left untouched; see scripts/dead_image_urls.txt)' % counts.get('dead', 0))
    print('Originals saved    : %d  (flickr only)' % orig_counts.get('saved', 0))
    print('Markdown files rewritten: %d' % rewritten)
    print('-----------------------------------------------------')
    print('static/ added    : %s' % human(linked_bytes))
    print('originals/ added : %s  (git-ignored)' % human(orig_bytes))
    print('=====================================================')


# ---- dry run (probe only) -------------------------------------------------
def dry_run():
    tasks, _ = collect()
    print('Unique off-site image URLs: %d' % len(tasks), file=sys.stderr)
    print('(use the real run to download)', file=sys.stderr)


if __name__ == '__main__':
    if '--dry-run' in sys.argv:
        dry_run()
    else:
        real_run()
