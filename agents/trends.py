"""Trend Beauty: recent RSS news, reviewed sources and catalog selection."""
from datetime import timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from agents.contracts import TrendBrief
from research import is_beauty_headline
from weekly import load_brief

ROOT = Path(__file__).resolve().parents[1]
QUERY = '(beauty OR skincare) (trend OR glow OR hydration OR longevity) when:7d'
THEMES = {
    'glow': {'keywords': ('glow', 'radiance', 'luminos', 'makeup', 'make-up', 'tinted', 'skin tint', 'teint'), 'label': 'Il tuo momento glow', 'colors': ((247, 233, 221), (205, 170, 144))},
    'renew': {'keywords': ('longevity', 'aging', 'ageing', 'collagen', 'collag', 'barrier', 'barriera', 'hydrat', 'idrat', 'firm'), 'label': 'Dedicati un rituale di cura', 'colors': ((233, 237, 229), (161, 185, 169))},
}


def parse_news(raw, now):
    cutoff = now - timedelta(days=7)
    found = []
    seen = set()
    for item in ET.fromstring(raw).findall('.//item'):
        try:
            published = parsedate_to_datetime(item.findtext('pubDate', ''))
            if published.tzinfo is None:
                continue
        except (ValueError, TypeError, OverflowError):
            continue
        title = item.findtext('title', '').strip()
        url = item.findtext('link', '').strip()
        if not title or not is_beauty_headline(title) or not url.startswith('https://') or url in seen or not cutoff <= published <= now:
            continue
        seen.add(url)
        found.append({'title': title, 'url': url, 'publisher': item.findtext('source', ''), 'published_at': published.isoformat()})
    return sorted(found, key=lambda x: x['published_at'], reverse=True)


def search_news(now):
    query = urllib.parse.urlencode({'q': QUERY, 'hl': 'it', 'gl': 'IT', 'ceid': 'IT:it'})
    req = urllib.request.Request('https://news.google.com/rss/search?' + query, headers={'User-Agent': 'AgentBeauty/2.0'})
    with urllib.request.urlopen(req, timeout=30) as response:
        news = parse_news(response.read(), now)
    if not news:
        raise RuntimeError('Nessuna notizia beauty datata negli ultimi sette giorni. Nessun trend inventato.')
    return news


def choose_product(products, news, requested=None):
    candidates = [p for p in products if not requested or requested.casefold() in p['name'].casefold()]
    if not candidates:
        raise ValueError('Prodotto richiesto non trovato nel database.')
    scores = {theme: sum(any(word in n['title'].casefold() for word in config['keywords']) for n in news) for theme, config in THEMES.items()}
    ranked = []
    for product in candidates:
        editorial = product['data'].get('editorial', {})
        theme = editorial.get('theme')
        claim = editorial.get('claim_it')
        if theme in THEMES and claim:
            ranked.append((scores[theme], product['name'], product, theme, claim))
    if not ranked:
        raise RuntimeError('Mancano claim editoriale e tema nel catalogo. Aggiungerli senza inventare benefici.')
    _, _, product, theme, claim = max(ranked, key=lambda item: (item[0], item[1]))
    matched = [n for n in news if any(word in n['title'].casefold() for word in THEMES[theme]['keywords'])]
    return product, theme, claim, matched, scores



class TrendAgent:
    def run(self, products, args, now):
        # Fresh discovery on every invocation; reviewed evidence is still required.
        news = search_news(now)
        weekly = load_brief(getattr(args, 'research', ROOT/'research/2026-10-08.json'), now)
        eligible = [p for p in products if p['id'].split(':')[-1] == weekly['product_key']]
        product, theme, claim, matched, scores = choose_product(eligible, news, args.product)
        return TrendBrief(now, product, theme, claim, news, matched, scores, weekly)
