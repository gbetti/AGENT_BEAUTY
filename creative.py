"""Turn dated beauty news and catalog claims into a varied campaign concept."""
import json
from pathlib import Path
import secrets
import sqlite3

from campaign import ROOT, campaign_copy

SCENES_PATH = ROOT/'assets/backgrounds/scenes.json'
ANGLES = {
    'natural_glow': {
        'label': 'Incarnato naturale e glow',
        'words': ('glow', 'radiance', 'luminos', 'make-up', 'makeup', 'trucco', 'cipria', 'blush', 'skin tint', 'tinted'),
        'context': 'Incarnato e make-up sono nelle notizie beauty della settimana. La nostra idea: valorizzare il tuo glow naturale.',
        'scenes': ('sunlit-vanity', 'pearl-glass', 'mint-ritual'),
    },
    'kbeauty_ritual': {
        'label': 'Rituali ispirati alla K-beauty',
        'words': ('k-beauty', 'corean', 'korean'),
        'context': 'I rituali K-beauty fanno parlare questa settimana. Lo spunto per IOMA: dare spazio alla cura quotidiana.',
        'scenes': ('mint-ritual', 'pearl-glass', 'botanical-stone'),
    },
    'hydration': {
        'label': 'Idratazione e barriera cutanea',
        'words': ('hydrat', 'idrat', 'barrier', 'barriera'),
        'context': 'Idratazione e barriera cutanea sono tra i temi della settimana. Il nostro spunto: un rituale di cura da ricordare.',
        'scenes': ('aqua-spa', 'botanical-stone', 'mint-ritual'),
    },
    'renewal': {
        'label': 'Cura della pelle e anti-age',
        'words': ('longevity', 'aging', 'ageing', 'collagen', 'collag', 'anti-age', 'antiage', 'firm'),
        'context': 'La cura anti-age è nelle notizie della settimana. La nostra idea: rendere il rituale protagonista.',
        'scenes': ('violet-evening', 'silk-mocha', 'pearl-glass'),
    },
    'beauty_ritual': {
        'label': 'Rituali beauty della settimana',
        'words': (),
        'context': 'Dalle notizie beauty della settimana, uno spunto per dare spazio al tuo prossimo rituale.',
        'scenes': ('sunlit-vanity', 'mint-ritual', 'silk-mocha'),
    },
}
HOOKS = {
    'glow': ('Team incarnato naturale?', 'Il glow è tuo', 'Fai spazio al glow', 'Il tuo rituale glow', 'Glow: trova il tuo'),
    'eyes': ('Sguardo: cambia il rituale', 'Il tuo rituale occhi', 'Rughe? Parti dal rituale', 'Il tuo sguardo, protagonista'),
    'renew': ('Pelle soda? Inizia qui', 'Dai spazio alla cura', 'Il tuo prossimo rituale', 'La tua pausa anti-age'),
}
OBJECTIVES = ('commenti', 'salvataggi', 'clic')


def recent_campaigns(database, limit=40):
    with sqlite3.connect(database) as db:
        rows = db.execute('SELECT research_json FROM generations ORDER BY created_at DESC, rowid DESC LIMIT ?',
                          (limit,)).fetchall()
    return [json.loads(row[0]) for row in rows]


def varied_choice(values, previous=None):
    candidates = [value for value in values if value != previous]
    if not candidates:
        raise ValueError('Servono almeno due alternative per cambiare ambientazione a ogni esecuzione.')
    return secrets.choice(candidates)


def campaign_plan(product, news, history, headline=None, cta=None):
    if not news:
        raise ValueError('Mancano le fonti per scegliere il messaggio della campagna.')
    theme = product['data'].get('editorial', {}).get('theme')
    role = 'glow' if theme == 'glow' else ('eyes' if 'yeux' in product['name'].casefold() else 'renew')
    compatible = ('natural_glow', 'kbeauty_ritual', 'hydration') if theme == 'glow' else ('renewal', 'hydration', 'kbeauty_ritual')
    groups = {key: [article for article in news
                    if any(word in article['title'].casefold() for word in ANGLES[key]['words'])]
              for key in compatible}
    # Prefer the strongest relevant news signal; never infer new product ingredients or efficacy.
    topic = max(compatible, key=lambda key: (len(groups[key]), -compatible.index(key)))
    if not groups[topic]:
        topic, evidence = 'beauty_ritual', news[:3]
    else:
        evidence = groups[topic][:3]
    angle = ANGLES[topic]
    last = next((row['creative'] for row in history if row.get('creative')), {})
    product_last = next((row['creative'] for row in history
                         if row.get('product_id') == product['id'] and row.get('creative')), {})
    scenes = json.loads(SCENES_PATH.read_text(encoding='utf-8'))
    scene_id = varied_choice(angle['scenes'], last.get('scene', {}).get('id'))
    scene = next(item for item in scenes if item['id'] == scene_id)
    if not (ROOT/scene['path']).is_file():
        raise RuntimeError('Ambientazione fotografica non trovata: '+scene['path'])
    objective = varied_choice(OBJECTIVES, product_last.get('objective'))
    generated_headline = varied_choice(HOOKS[role], product_last.get('headline'))
    generated_cta = 'Scopri il tuo glow' if role == 'glow' else 'Scopri il rituale'
    editorial = product['data'].get('editorial', {})
    headline, cta = campaign_copy(product, headline if headline is not None else
                                 (editorial.get('headline_it') or generated_headline),
                                 cta if cta is not None else (editorial.get('cta_it') or generated_cta))
    claim = editorial['claim_it']
    if objective == 'commenti':
        question = ('Team glow naturale? Raccontacelo nei commenti.' if role == 'glow' else
                    'Il tuo rituale è al mattino o alla sera? Scrivilo nei commenti.')
    elif objective == 'salvataggi':
        question = 'Salva il post per il tuo prossimo rituale.'
    else:
        question = 'Vuoi inserirlo nel tuo rituale? Scopri la scheda del prodotto.'
    caption = f"{headline}\n\n{angle['context']}\n\n{product['name']}\n{claim}\n\n{question}"
    tags = ['#IOMAParis', '#Skincare', '#BeautyRoutine']
    tags += ['#CCGel', '#IncarnatoNaturale', '#Glow'] if role == 'glow' else (
        ['#ContornoOcchi', '#AntiAge', '#RitualeBeauty'] if role == 'eyes' else
        ['#CremaViso', '#AntiAge', '#RitualeBeauty'])
    return {'trend_id': topic, 'trend_label': angle['label'], 'evidence': evidence,
            'angle': angle['context'], 'claim': claim, 'headline': headline, 'cta': cta,
            'objective': objective, 'caption': caption, 'hashtags': tags, 'scene': scene}
