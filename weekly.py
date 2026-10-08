"""Verified weekly evidence, with separate editorial and advertising classifications."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from html import unescape
import hashlib
import json
import re
import urllib.request
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parent


def fetch_text(url):
    if urlsplit(url).scheme!='https': raise ValueError('Fonte non HTTPS.')
    request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 IOMA-BeautyRadar/3'})
    with urllib.request.urlopen(request,timeout=30) as response:
        raw=response.read(4_000_000).decode('utf-8','replace')
    clean=re.sub(r'<(script|style)\b[^>]*>.*?</\1>', ' ',raw,flags=re.S|re.I)
    return re.sub(r'\s+',' ',unescape(re.sub('<[^>]+>',' ',clean)))


def load_brief(path,now):
    brief=json.loads(Path(path).read_text())
    reviewed=datetime.fromisoformat(brief['reviewed_at'])
    if reviewed.tzinfo is None or not timedelta(0)<=now-reviewed<=timedelta(hours=36):
        raise ValueError('Ricerca settimanale da aggiornare: usare un brief verificato nelle ultime 36 ore.')
    seen=set(); recent=0
    for source in brief['sources']:
        if source['id'] in seen: raise ValueError('Fonte duplicata.')
        seen.add(source['id'])
        published=datetime.fromisoformat(source['published_at'])
        if published.tzinfo is None or published>now: raise ValueError('Data fonte non valida.')
        fresh=now-timedelta(days=7)<=published
        active=(source['kind']=='advertising_campaign' and source.get('event_start','9999')<=now.date().isoformat()<=source.get('event_end','0000'))
        if not (fresh or active): raise ValueError('Fonte fuori settimana senza campagna attiva: '+source['id'])
        if source['kind'] not in ('editorial','brand_promotion','advertising_campaign'):
            raise ValueError('Classificazione fonte non valida.')
        source['in_week']=fresh
        if fresh: recent+=1
        text=fetch_text(source['url'])
        if not source.get('evidence_terms') or any(term.casefold() not in text.casefold() for term in source['evidence_terms']):
            raise ValueError('La fonte non conferma più le evidenze: '+source['id'])
        source['checked_at']=now.isoformat()
        source['content_sha256']=hashlib.sha256(text.encode()).hexdigest()
    if not recent: raise ValueError('Mancano notizie della settimana.')
    if not any(s['kind']=='advertising_campaign' for s in brief['sources']):
        raise ValueError('Manca una campagna pubblicitaria documentata; non sostituirla con un articolo o una promozione.')
    return brief


def select_ingredients(product,brief,source_url,now):
    key=product['id'].split(':')[-1]
    if key!=brief['product_key']: raise ValueError('Il brief settimanale riguarda un altro prodotto.')
    candidates=json.loads((ROOT/'assets/ingredients.json').read_text()).get(key,[])
    text=fetch_text(source_url)
    # Limit identity matching to the official INCI list, not reviews or related products.
    upper=text.upper()
    start=upper.find('AQUA (WATER)')
    if start<0: start=upper.find('WATER (AQUA)')
    end=upper.find('PARFUM (FRAGRANCE)',start)
    if start<0 or end<start: raise ValueError('INCI ufficiale non individuabile: verificare la scheda.')
    inci={token.strip() for token in upper[start:end].split(',')}
    ranked=[]
    for candidate in candidates:
        evidence=[s['id'] for s in brief['sources'] if s['in_week'] and candidate['id'] in s.get('topics',[])]
        if evidence and all(token in inci for token in candidate['inci']):
            ranked.append({**candidate,'source_ids':evidence,'source_url':source_url,'verified_at':now.isoformat()})
    ranked.sort(key=lambda c:(len(c['source_ids']),c['priority']),reverse=True)
    if len(ranked)<2: raise ValueError('Mancano due ingredienti verificati nella formula e pertinenti alle notizie settimanali.')
    return ranked[:2]
