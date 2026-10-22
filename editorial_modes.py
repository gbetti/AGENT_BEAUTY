"""Rotate documented claims, ingredient inspiration and sourced customer opinions."""
from datetime import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODES = ('claim', 'inspiration', 'review')
REVIEW_TRANSLATIONS = {
    'd46393fd-32f8-4ced-81cc-8486bde8fa6f': 'Texture piacevole e flacone pratico',
    'a1aaeb60-4682-42bc-ab7b-b5e7afbb568f': 'Texture molto piacevole',
}


def sourced_review(product, review_id=None):
    key = product['id'].rsplit(':', 1)[-1]
    path = ROOT/'assets/catalog/reviews'/f'{key}.json'
    if not path.is_file():
        raise ValueError('Recensioni pubbliche mancanti per questo prodotto.')
    evidence = json.loads(path.read_text())
    candidates = [r for r in evidence['items'] if not r.get('from_group')
                  and r['id'] in REVIEW_TRANSLATIONS and (not review_id or r['id'] == review_id)]
    if not candidates:
        raise ValueError('Manca una recensione del prodotto con traduzione revisionata.')
    review = candidates[0]
    return {k: review[k] for k in ('id', 'rating', 'body', 'created_at')} | {
        'source_url': evidence['source_url'], 'collected_at': evidence['collected_at'],
        'translation_it': REVIEW_TRANSLATIONS[review['id']], 'opinion_not_efficacy_evidence': True}


def apply_editorial_mode(creative, product, history, *, mode='auto', review_id=None, theme='ingredients', ingredients=()):
    from editorial import BRIEFS
    # Catalog titles may contain SEO benefit/tagline suffixes. Use the reviewed
    # product name, especially for inspiration without an efficacy claim.
    display_name = BRIEFS[product['id'].rsplit(':', 1)[-1]]['name']
    caption_name = display_name.replace('\n', ' ')
    if mode == 'auto':
        last = next((r.get('creative', {}).get('editorial_mode') for r in history), None)
        mode = MODES[(MODES.index(last)+1) % len(MODES)] if last in MODES else 'claim'
        # Unsupported translations must never be invented to fill the rotation.
        if mode == 'review':
            try:
                sourced_review(product, review_id)
            except ValueError:
                mode = 'claim'
    if mode not in MODES:
        raise ValueError('Modalità editoriale non valida.')
    if mode == 'inspiration' and theme == 'ingredients' and not ingredients:
        raise ValueError('Verificare gli ingredienti nella formula prima di usarli nel copy.')
    if mode != 'claim':
        from art_direction import pack_product
        creative['content_mode'] = 'product'
        creative['scene']['design'].update(mode='product', products=[pack_product(product)])
        creative['scene']['design'].pop('model', None)
    creative['editorial_mode'] = mode
    creative['editorial_basis'] = {'claim': 'documented_product_benefit',
        'inspiration': 'ingredient_or_skin_inspiration_without_efficacy_claim',
        'review': 'attributed_customer_opinion'}[mode]
    review = sourced_review(product, review_id) if mode == 'review' else None
    if review:
        creative['customer_review'] = review
    for lang, copy in creative['copies'].items():
        copy['editorial_mode'] = mode
        if mode == 'claim':
            continue
        fr = lang == 'fr'
        copy['product_name'] = display_name
        if mode == 'inspiration':
            copy['inspiration_theme'] = theme
            copy['category'] = ('LA BEAUTÉ EN MOUVEMENT' if fr else 'BELLEZZA IN MOVIMENTO')
            if theme == 'ingredients':
                copy['headline'] = 'Au rythme\ndes peptides.' if fr else 'Al ritmo\ndei peptidi.'
                copy['banner_headline'] = 'Peptides.\nEn rythme.' if fr else 'Peptidi.\nIn ritmo.'
                copy['caption'] = ("Des lignes, des courbes, un peu de poésie. Une inspiration graphique autour des peptides présents dans la formule de " if fr else
                    "Linee, curve, un po’ di poesia. Un’ispirazione grafica intorno ai peptidi presenti nella formula di ") + caption_name + '.'
                if not any(item['id'] == 'peptides' for item in ingredients):
                    label = ingredients[0]['short'][lang]
                    copy['headline'] = label+'\n'+('En mouvement.' if fr else 'In movimento.')
                    copy['banner_headline'] = label+'\n'+('En rythme.' if fr else 'In ritmo.')
                    copy['caption'] = (f'Un jeu de lignes autour d’un ingrédient de {caption_name} : {label.lower()}.' if fr else
                                       f'Un gioco di linee intorno a un ingrediente di {caption_name}: {label.lower()}.')
            else:
                copy['headline'] = 'Votre peau.\nVotre rythme.' if fr else 'La tua pelle.\nIl tuo ritmo.'
                copy['banner_headline'] = 'Votre peau.\nVotre rythme.' if fr else 'La tua pelle.\nIl tuo ritmo.'
                copy['caption'] = ("Peau sèche, mixte ou grasse : chaque routine commence par l’écoute de sa peau. Un instant pour observer ses envies, ses habitudes, son propre rythme.\n\n" if fr else
                    "Pelle secca, mista o grassa: ogni routine inizia dall’ascolto della propria pelle. Un momento per osservare desideri, abitudini e il proprio ritmo.\n\n") + ('En image : ' if fr else 'In immagine: ') + caption_name + '.'
            copy['comment'] = 'Un instant pour soi.' if fr else 'Un momento per sé.'
            copy['caption'] += ('\n\nAnimation graphique d’inspiration. Aucun résultat de soin représenté.' if fr else '\n\nAnimazione grafica d’ispirazione. Nessun risultato di trattamento rappresentato.')
        else:
            text = review['body'] if fr else review['translation_it']
            copy['category'] = ('AVIS CLIENT' if fr else 'RECENSIONE CLIENTE') + f" · {review['rating']}/5"
            copy['headline'] = text
            copy['banner_headline'] = text
            copy['comment'] = 'Les petits détails font le rituel.' if fr else 'I piccoli dettagli fanno il rituale.'
            date = datetime.fromisoformat(review['created_at'].replace('Z', '+00:00')).strftime('%d.%m.%Y')
            copy['review_source'] = ('Avis du ' if fr else 'Recensione del ') + date + ' · ioma-paris.com'
            copy['caption'] = (f'« {text} » — {review["rating"]}/5.\n\n' + copy['comment'] +
                (' Merci pour ce retour.\n\n' if fr else ' Grazie per questo commento.\n\n') + caption_name + '\n' + copy['review_source'] +
                ('\nOpinion individuelle, pas une promesse de résultat.' if fr else '\nTraduzione dal francese. Opinione individuale, non una promessa di risultato.') + '\n' + review['source_url'])
        copy['caption'] += '\n\n#IOMAParis #RituelDeSoin #Skincare' if fr else '\n\n#IOMAParis #RitualeDiBellezza #Skincare'
    return creative
