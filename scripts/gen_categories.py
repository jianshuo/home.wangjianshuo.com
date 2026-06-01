"""Generate category index + per-category list pages that match the original
WordPress URLs: /category/<slug>/ (English) and /cn/category/<slug>/ (Chinese),
using the original WP category slug (nicename). Reuses catslugs/categories from
the post front matter written by wxr_to_hugo.py.

Usage: gen_categories.py <section cn|en> <url_prefix> <outdir>
  e.g. gen_categories.py cn /cn/category/ content/cats
       gen_categories.py en /category/  content/cats
"""
import sys, os, re, json, glob


def read_fm(path):
    """Return the front-matter dict-ish fields we need (categories, catslugs)."""
    txt = open(path, encoding='utf-8').read()
    def arr(key):
        m = re.search(r'^%s:\s*(\[.*\])\s*$' % key, txt, re.M)
        return json.loads(m.group(1)) if m else []
    return arr('categories'), arr('catslugs')


def main(section, prefix, outdir):
    os.makedirs(outdir, exist_ok=True)
    slug_name = {}      # slug -> display name
    slug_count = {}
    for md in glob.glob('content/%s/*.md' % section):
        names, slugs = read_fm(md)
        for nm, sl in zip(names, slugs):
            if not sl:
                continue
            slug_name.setdefault(sl, nm)
            slug_count[sl] = slug_count.get(sl, 0) + 1

    # per-category list pages
    for sl, nm in slug_name.items():
        title = nm.replace('"', "'")
        fm = '\n'.join([
            '---', 'title: "%s"' % title, 'url: %s%s/' % (prefix, sl),
            'layout: catlist', 'catslug: "%s"' % sl, 'catsection: "%s"' % section,
            '---', ''])
        with open('%s/%s-%s.md' % (outdir, section, sl), 'w', encoding='utf-8') as f:
            f.write(fm)

    # index page listing all categories
    idx_title = '分类' if section == 'cn' else 'Categories'
    fm = '\n'.join([
        '---', 'title: "%s"' % idx_title, 'url: %s' % prefix,
        'layout: catindex', 'catsection: "%s"' % section, '---', ''])
    with open('%s/%s-index.md' % (outdir, section), 'w', encoding='utf-8') as f:
        f.write(fm)

    print('categories[%s]: %d wrote under %s' % (section, len(slug_name), prefix))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
