"""WordPress WXR (.xml export) -> Hugo Markdown.

Pure-stdlib. Designed to work for ANY WordPress site: feed it the standard
"Tools -> Export -> All content" WXR file plus the wp-content/uploads folder.

Image URLs are left verbatim (e.g. /wp-content/uploads/2022/09/p.jpg); the
driver copies uploads/ into static/wp-content/uploads/ so they resolve
unchanged. Post URLs from <link> are preserved verbatim too (/archives/<id>/).

Unit-tested pure functions: parse_items, html_to_markdown,
build_front_matter, next_archive_id.  See tests/test_wxr.py.
"""
import re, html, os, json
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

NS = {
    'wp': 'http://wordpress.org/export/1.2/',
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'dc': 'http://purl.org/dc/elements/1.1/',
}


# --------------------------------------------------------------------------
# HTML -> Markdown
# --------------------------------------------------------------------------
def _root_relative(url):
    """Strip scheme+host from self-hosted media so URLs resolve under any host.
    Any absolute URL whose path is under /wp-content/ becomes root-relative;
    external images (other domains, not wp-content) stay absolute."""
    m = re.match(r'https?://[^/]+(/wp-content/.*)$', url)
    if m:
        return m.group(1)
    m = re.match(r'https?://(?:www\.|home\.)?wangjianshuo\.com(/.*)$', url, re.I)
    if m:
        return m.group(1)
    return url


def _en_image_rewrite(url):
    """English blog images are NOT bundled into Hugo; they live on the
    archives.wangjianshuo.com host (which IS the old /archives folder, so that
    leading path segment is dropped). External images (Flickr etc.) stay
    absolute."""
    m = re.match(r'https?://(?:www\.|home\.)?wangjianshuo\.com(/.*)$', url, re.I)
    if m:
        path = re.sub(r'^/archives(?=/|$)', '', m.group(1)) or '/'
        return 'https://archives.wangjianshuo.com' + path
    return url


# Active image-URL rewriter; the driver swaps this for the English blog.
IMG_REWRITE = _root_relative



class _MD(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.images = []
        self._in_link = False
        self._href = None
        self._link_text = []
        self._in_gallery = 0
        self._fig_stack = []
        self._qstart = []   # blockquote content start indices (for line-prefixing)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ('p', 'div'):
            self.parts.append('\n\n')
        elif tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.parts.append('\n\n' + '#' * int(tag[1]) + ' ')
        elif tag == 'li':
            if not self._in_gallery:
                self.parts.append('\n- ')
        elif tag in ('strong', 'b'):
            self.parts.append('**')
        elif tag in ('em', 'i'):
            self.parts.append('*')
        elif tag == 'br':
            self.parts.append('  \n')
        elif tag == 'blockquote':
            self.parts.append('\n\n')
            self._qstart.append(len(self.parts))   # remember where content begins
        elif tag == 'figure':
            is_gallery = 'wp-block-gallery' in a.get('class', '')
            self._fig_stack.append(is_gallery)
            if is_gallery:
                self._in_gallery += 1
        elif tag == 'img':
            src = a.get('data-full-url') or a.get('src', '')
            if src:
                self.images.append(src)
                self.parts.append('\n\n![](%s)\n\n' % IMG_REWRITE(src))
        elif tag in ('video', 'audio', 'iframe'):
            # Pass embeds through as raw HTML (Hugo goldmark unsafe=true renders them).
            src = a.get('src', '')
            ctl = ' controls' if tag in ('video', 'audio') else ''
            if src:
                self.parts.append('\n\n<%s%s src="%s"></%s>\n\n' % (tag, ctl, src, tag))
                self._raw_media = True
        elif tag == 'source':
            # <video><source src=...></video> — capture if outer tag had no src
            src = a.get('src', '')
            if src and not getattr(self, '_raw_media', False):
                self.parts.append('\n\n<video controls src="%s"></video>\n\n' % src)
        elif tag == 'a':
            self._in_link = True
            self._href = a.get('href', '')
            self._link_text = []

    def handle_startendtag(self, tag, attrs):
        # <img .../> arrives here, not handle_starttag
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == 'a' and self._in_link:
            text = ''.join(self._link_text).strip()
            if self._href and text:
                self.parts.append('[%s](%s)' % (text, self._href))
            elif text:
                self.parts.append(text)
            self._in_link = False
            self._href = None
            self._link_text = []
        elif tag in ('strong', 'b'):
            self.parts.append('**')
        elif tag in ('em', 'i'):
            self.parts.append('*')
        elif tag in ('video', 'audio', 'iframe'):
            self._raw_media = False
        elif tag == 'figure' and self._fig_stack:
            if self._fig_stack.pop():
                self._in_gallery -= 1
        elif tag == 'blockquote' and self._qstart:
            start = self._qstart.pop()
            inner = ''.join(self.parts[start:]).strip()
            del self.parts[start:]
            # Prefix EVERY line with '> ' so multi-line quotes stay quoted.
            quoted = '\n'.join(('> ' + ln) if ln.strip() else '>'
                               for ln in inner.split('\n'))
            self.parts.append(quoted + '\n\n')
        elif tag in ('p', 'div'):
            self.parts.append('\n\n')

    def handle_data(self, data):
        if self._in_link:
            self._link_text.append(data)
        else:
            self.parts.append(data)


def html_to_markdown(content):
    """Return (markdown, [image_urls]). Image URLs and links preserved verbatim."""
    p = _MD()
    p.feed(content)
    md = ''.join(p.parts)
    md = re.sub(r'[ \t]+\n', '\n', md)
    md = re.sub(r'\n{3,}', '\n\n', md)
    return md.strip(), p.images


# --------------------------------------------------------------------------
# Front matter
# --------------------------------------------------------------------------
# Default WordPress / common-plugin scaffolding page slugs (not real content).
SCAFFOLD_SLUGS = {
    'sample-page', 'login', 'register', 'findpassword', 'password-protected',
    'login-designer', 'archives', 'cart', 'checkout', 'my-account',
}


def is_real_page(page):
    """False for WordPress scaffolding: empty body, single-shortcode body, or
    a known default slug. Keeps genuine content pages."""
    if page['slug'] in SCAFFOLD_SLUGS:
        return False
    body = html_to_markdown(page['content'])[0].strip()
    if not body:
        return False
    if re.fullmatch(r'\[[^\]]+\]', body):   # body is exactly one shortcode
        return False
    return True


def build_front_matter(post):
    # Escape backslashes so YAML double-quoted titles (e.g. "ROBOCOPY D:\my")
    # don't trip the front-matter parser; collapse stray quotes to apostrophes.
    title = html.unescape(post['title']).replace('\\', '\\\\').replace('"', "'")
    lines = [
        '---',
        'title: "%s"' % title,
        'date: %s' % post['date'],
        'lastmod: %s' % post.get('modified', post['date']),
        'categories: %s' % json.dumps(post.get('categories', []), ensure_ascii=False),
        'catslugs: %s' % json.dumps(post.get('catslugs', []), ensure_ascii=False),
        'tags: %s' % json.dumps(post.get('tags', []), ensure_ascii=False),
        'url: %s' % post['url'],
    ]
    if post.get('aliases'):
        lines.append('aliases: %s' % json.dumps(post['aliases'], ensure_ascii=False))
    lines.append('---')
    return '\n'.join(lines)


# --------------------------------------------------------------------------
# Archive-id allocation for new posts
# --------------------------------------------------------------------------
def next_archive_id(content_dir):
    mx = 0
    for root, _dirs, files in os.walk(content_dir):
        for fn in files:
            if fn.endswith('.md'):
                txt = open(os.path.join(root, fn), encoding='utf-8').read()
                for m in re.finditer(r'url:\s*/archives/(\d+)/', txt):
                    n = int(m.group(1))
                    mx = max(mx, n)
    return mx + 1


# --------------------------------------------------------------------------
# WXR parsing
# --------------------------------------------------------------------------
def _norm_url(link, post_id, post_type):
    """Preserve the original permalink path. Percent-encoded bytes are DECODED
    to raw UTF-8 so Hugo writes a file whose on-disk name matches what a browser
    asks for (the browser re-encodes; the server decodes before file lookup).
    Storing the literal %xx would create a '%e5%af...'-named file that no decoded
    request can ever hit (404)."""
    import urllib.parse
    if link:
        path = re.sub(r'^https?://[^/]+', '', link).strip()
        path = urllib.parse.unquote(path)        # %e5%af%b9 -> 对  (raw UTF-8)
        if not path:
            path = '/'
        if re.search(r'/[^/]+\.[A-Za-z0-9]{2,5}$', path):
            return path
        if not path.endswith('/'):
            path += '/'
        return path
    return '/archives/%s/' % post_id


def _cjk_slug_to_pid(path, post_id):
    """If the /cn/<date>_<slug>.htm slug contains CJK (a WordPress-era Chinese
    permalink), rewrite it to the uniform /cn/<date>_p<id>.htm form. ASCII
    letter slugs (MovableType era) are kept verbatim. Returns
    (new_path, original_path) when changed, else (path, None)."""
    import urllib.parse
    m = re.match(r'(/cn/\d{8})_(.+)(\.htm)$', path)
    if not m:
        return path, None
    decoded = urllib.parse.unquote(m.group(2))
    if not any('一' <= c <= '鿿' for c in decoded):
        return path, None
    return '%s_p%s.htm' % (m.group(1), post_id), path


def _write_redirects(pairs, static_root='static'):
    """Write meta-refresh redirect pages at the (decoded) old permalink paths so
    pre-existing Chinese URLs keep resolving after the slug change.
    pairs: list of (old_url_path, new_url_path)."""
    import urllib.parse
    for old, new in pairs:
        rel = urllib.parse.unquote(old.lstrip('/'))      # cn/<date>_<中文>.htm
        dest = os.path.join(static_root, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        doc = ('<!DOCTYPE html><html><head><meta charset="utf-8">'
               '<meta http-equiv="refresh" content="0; url=%s">'
               '<link rel="canonical" href="%s"></head>'
               '<body>This page has moved to <a href="%s">%s</a>.</body></html>'
               % (new, new, new, new))
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(doc)


def parse_items(xml_text, post_type):
    """Parse a WXR string; return published items of the given post_type.

    Each item: {id, title, slug, date, modified, url, categories, tags, content}.
    """
    root = ET.fromstring(xml_text)
    out = []
    for item in root.iter('item'):
        ptype = item.findtext('wp:post_type', default='', namespaces=NS)
        status = item.findtext('wp:status', default='', namespaces=NS)
        if ptype != post_type or status != 'publish':
            continue
        # Password-protected posts can't be gated on a static site -> skip them.
        if (item.findtext('wp:post_password', default='', namespaces=NS) or '').strip():
            continue
        pid = item.findtext('wp:post_id', default='', namespaces=NS)
        title = (item.findtext('title') or '').strip()
        slug = item.findtext('wp:post_name', default='', namespaces=NS) or pid
        link = (item.findtext('link') or '').strip()
        cats, catslugs, tags = [], [], []
        for c in item.findall('category'):
            domain = c.get('domain')
            name = (c.text or '').strip()
            if not name:
                continue
            if domain == 'category':
                cats.append(name)
                catslugs.append(c.get('nicename') or name)   # original WP slug
            elif domain == 'post_tag':
                tags.append(name)
        out.append({
            'id': int(pid) if pid.isdigit() else pid,
            'title': title,
            'slug': slug,
            'date': item.findtext('wp:post_date', default='', namespaces=NS),
            'modified': (item.findtext('wp:post_modified', default='', namespaces=NS)
                         or item.findtext('wp:post_date', default='', namespaces=NS)),
            'url': _norm_url(link, pid, ptype),
            'categories': cats,
            'catslugs': catslugs,
            'tags': tags,
            'content': item.findtext('content:encoded', default='', namespaces=NS) or '',
        })
    return out


# --------------------------------------------------------------------------
# Comments (baked straight into each post from the original WXR; no new files)
# --------------------------------------------------------------------------
def _cdata_text(m):
    if not m:
        return ''
    t = m.group(1)
    c = re.search(r'<!\[CDATA\[(.*?)\]\]>', t, re.S)
    t = c.group(1) if c else t
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', t).strip()


def _strip_comment_html(s):
    """Drop all HTML/markup from a comment, keeping only the readable text.
    <a href=x>label</a> -> label ; <br> -> newline ; entities decoded."""
    s = re.sub(r'(?is)<\s*br\s*/?\s*>', '\n', s)
    s = re.sub(r'(?is)</p\s*>|<p[^>]*>', '\n', s)
    s = re.sub(r'(?s)<[^>]+>', '', s)          # remove every remaining tag
    s = html.unescape(s)                        # &lt; &amp; &#039; ...
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()


def parse_comments(xml_text):
    """post_id -> [ {author, date, content} ] for APPROVED real comments only.
    Regex-based so it tolerates the malformed entities in the English export.
    Email and IP are intentionally never extracted."""
    out = {}
    for item in xml_text.split('<item>')[1:]:
        pm = re.search(r'<wp:post_id>(\d+)</wp:post_id>', item)
        if not pm:
            continue
        cs = []
        for cm in re.findall(r'<wp:comment>(.*?)</wp:comment>', item, re.S):
            ap = re.search(r'<wp:comment_approved><!\[CDATA\[(.*?)\]\]>', cm, re.S)
            if not ap or ap.group(1).strip() != '1':
                continue
            ct = re.search(r'<wp:comment_type><!\[CDATA\[(.*?)\]\]>', cm, re.S)
            if ct and ct.group(1).strip() not in ('', 'comment'):
                continue   # skip pingback/trackback
            content = _strip_comment_html(_cdata_text(
                re.search(r'<wp:comment_content>(.*?)</wp:comment_content>', cm, re.S)))
            if not content:           # was pure HTML / a bare link -> drop it
                continue
            cs.append({
                'author': _cdata_text(re.search(r'<wp:comment_author>(.*?)</wp:comment_author>', cm, re.S)) or 'Anonymous',
                'date': _cdata_text(re.search(r'<wp:comment_date>(.*?)</wp:comment_date>', cm, re.S))[:16],
                'content': content,
            })
        if cs:
            out[pm.group(1)] = cs
    return out


def render_comments(comments):
    if not comments:
        return ''
    # Collapsed by default: <summary> shows the count, clicking reveals them.
    parts = ['\n\n<details class="comments">',
             '<summary class="comments-head">%d Comments</summary>' % len(comments)]
    for c in comments:
        body = html.escape(c['content']).replace('\n', '<br>')
        # content first, then the author · date on its own line below
        parts.append('<div class="comment">%s<div class="comment-meta">— %s · %s</div></div>'
                     % (body, html.escape(c['author']), c['date']))
    parts.append('</details>')
    return '\n'.join(parts)


# --------------------------------------------------------------------------
# CLI driver
# --------------------------------------------------------------------------
def _copy_uploads(src='uploads', dst='static/wp-content/uploads'):
    import shutil
    if not os.path.isdir(src):
        return 0
    n = 0
    for root, _dirs, files in os.walk(src):
        for fn in files:
            if fn == '.DS_Store' or fn.endswith('.sql'):
                continue
            s = os.path.join(root, fn)
            rel = os.path.relpath(s, src)
            d = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)
            n += 1
    return n


def convert_all(xml_path, outdir='content/cn', comments_xml=None):
    xml_text = open(xml_path, encoding='utf-8').read()
    posts = parse_items(xml_text, 'post')
    pages = parse_items(xml_text, 'page')
    os.makedirs(outdir, exist_ok=True)
    all_images = set()
    report = {'posts': 0, 'pages': 0, 'images': 0, 'comments': 0, 'warnings': []}
    # URLs are kept exactly as the original <link> (see _norm_url) — no rewriting.

    # Comments come straight from the WXR (the original export, which for English
    # still has them); baked into each post, no separate files.
    cmap = {}
    if comments_xml:
        ctext = xml_text if comments_xml == xml_path else open(comments_xml, encoding='utf-8').read()
        cmap = parse_comments(ctext)

    for post in posts:
        body, imgs = html_to_markdown(post['content'])
        all_images.update(imgs)
        fm = build_front_matter(post)
        cms = cmap.get(str(post['id']), [])
        report['comments'] += len(cms)
        with open('%s/%s.md' % (outdir, post['id']), 'w', encoding='utf-8') as f:
            f.write(fm + '\n\n' + body + '\n' + render_comments(cms) + '\n')
        if not body.strip():
            report['warnings'].append('empty body: %s' % post['id'])
        report['posts'] += 1

    for page in pages:
        if not is_real_page(page):
            report['warnings'].append('skipped scaffolding page: %s' % page['slug'])
            continue
        body, imgs = html_to_markdown(page['content'])
        all_images.update(imgs)
        title = html.unescape(page['title']).replace('\\', '\\\\').replace('"', "'")
        fm = '\n'.join(['---', 'title: "%s"' % title, 'url: %s' % page['url'], '---'])
        with open('content/%s.md' % page['slug'], 'w', encoding='utf-8') as f:
            f.write(fm + '\n\n' + body + '\n')
        report['pages'] += 1

    report['images'] = len(all_images)
    copied = _copy_uploads()
    report['uploads_copied'] = copied
    # any image whose host differs from the site (can't be served locally)
    ext = [u for u in all_images if u.startswith('http') and '/wp-content/uploads/' not in u]
    if ext:
        report['warnings'].append('external/off-site images: %d' % len(ext))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    import sys
    # usage: wxr_to_hugo.py <export.xml> [outdir] [cn|en] [comments.xml]
    args = sys.argv[1:]
    if not args:
        print('usage: python3 scripts/wxr_to_hugo.py <export.xml> [outdir] [cn|en] [comments.xml]')
        sys.exit(1)
    xml = args[0]
    outdir = args[1] if len(args) > 1 else 'content/cn'
    mode = args[2] if len(args) > 2 else 'cn'
    # comments come from the original WXR (default: the posts file itself; for the
    # English blog pass the un-stripped original which still holds the comments).
    comments_xml = args[3] if len(args) > 3 else xml
    # Both blogs keep images root-relative (cn -> /cn/..., en -> /archives/...);
    # the en /archives/* bytes are served from another host via Cloudflare routing,
    # so the URL the browser sees stays on home.wangjianshuo.com.
    convert_all(xml, outdir, comments_xml)
