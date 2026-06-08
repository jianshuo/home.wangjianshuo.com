"""Publish selected DRAFT posts from a WXR.

Rule (per user): skip empty / near-empty drafts; for drafts with real content,
skip ones that duplicate an already-published post (by title, slug, link, or
normalized content); publish the rest. Drafts never had a clean permalink
(WordPress ?p=<id> links), so each gets a freshly minted /cn/p<id>.htm URL.

Reuses the tested pure functions in wxr_to_hugo. Run AFTER wxr_to_hugo.py.
"""
import os, re, sys, html, hashlib
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(__file__))
import wxr_to_hugo as w

NS = w.NS
MIN_TEXT = 20  # <= this many non-space text chars => "empty / almost empty"


def _norm_text(content):
    """Strip tags + whitespace -> bare text for length + dup comparison."""
    t = re.sub(r'<[^>]+>', '', content or '')
    return re.sub(r'\s+', '', t)


def main(xml_path, outdir='content/cn', url_prefix='/cn/'):
    root = ET.fromstring(open(xml_path, encoding='utf-8').read())
    pub_titles, pub_slugs, pub_links, pub_hashes = set(), set(), set(), set()
    drafts = []
    for it in root.iter('item'):
        if it.findtext('wp:post_type', '', NS) != 'post':
            continue
        st = it.findtext('wp:status', '', NS)
        title = (it.findtext('title', '', NS) or '').strip()
        slug = (it.findtext('wp:post_name', '', NS) or '').strip()
        link = (it.findtext('link', '', NS) or '').strip()
        content = it.findtext('content:encoded', '', NS) or ''
        if st == 'publish':
            pub_titles.add(title)
            if slug:
                pub_slugs.add(slug)
            pub_links.add(link)
            pub_hashes.add(hashlib.md5(_norm_text(content).encode()).hexdigest())
        elif st == 'draft':
            drafts.append(it)

    published = skipped_empty = skipped_dup = 0
    for it in drafts:
        pid = it.findtext('wp:post_id', '', NS)
        title = (it.findtext('title', '', NS) or '').strip()
        slug = (it.findtext('wp:post_name', '', NS) or '').strip()
        link = (it.findtext('link', '', NS) or '').strip()
        content = it.findtext('content:encoded', '', NS) or ''
        text = _norm_text(content)
        if len(text) <= MIN_TEXT:
            skipped_empty += 1
            continue
        h = hashlib.md5(text.encode()).hexdigest()
        if (title in pub_titles or (slug and slug in pub_slugs)
                or link in pub_links or h in pub_hashes):
            skipped_dup += 1
            continue
        date = it.findtext('wp:post_date', '', NS)
        ymd = re.sub(r'[^0-9]', '', date)[:8]   # 'YYYY-MM-DD HH:MM:SS' -> 'YYYYMMDD'
        post = {
            'id': pid,
            'title': title or ('(草稿 %s)' % pid),
            'date': date,
            'modified': (it.findtext('wp:post_modified', '', NS) or date),
            'categories': [c.text.strip() for c in it.findall('category')
                           if c.get('domain') == 'category' and (c.text or '').strip()],
            'tags': [c.text.strip() for c in it.findall('category')
                     if c.get('domain') == 'post_tag' and (c.text or '').strip()],
            # match original <YYYYMMDD>_<slug>.htm pattern; drafts have no slug -> p<id>
            'url': '%s%s_p%s.htm' % (url_prefix, ymd, pid),
        }
        body, _ = w.html_to_markdown(content)
        fm = w.build_front_matter(post)
        with open('%s/%s.md' % (outdir, pid), 'w', encoding='utf-8') as f:
            f.write(fm + '\n\n' + body + '\n')
        # dedup within drafts too, so two identical drafts don't both publish
        pub_titles.add(title); pub_hashes.add(h)
        if slug:
            pub_slugs.add(slug)
        published += 1

    print('drafts: published=%d  skipped_empty=%d  skipped_duplicate=%d'
          % (published, skipped_empty, skipped_dup))


if __name__ == '__main__':
    # usage: add_drafts.py <export.xml> [outdir] [url_prefix] [cn|en]
    a = sys.argv[1:]
    xml = a[0]
    outdir = a[1] if len(a) > 1 else 'content/cn'
    prefix = a[2] if len(a) > 2 else '/cn/'
    mode = a[3] if len(a) > 3 else 'cn'   # kept for symmetry; images stay root-relative
    main(xml, outdir, prefix)
