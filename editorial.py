"""Product-specific French and Italian copy grounded in the local catalog."""
import json
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LANGUAGES = ('fr', 'it')
BRIEFS = {
 'creme-sublime-revitalisante': {
  'name': 'Crème Sublime Revitalisante',
  'claim_it': 'Nutre la pelle in profondità. Per una pelle più soda.',
  'source': 'https://ioma-paris.com/products/creme-sublime-revitalisante',
  'category': {'fr': 'NUTRITION & FERMETÉ', 'it': 'NUTRIMENTO & COMPATTEZZA'},
  'headlines': [ {'fr': 'Nourrir.\nRaffermir.', 'it': 'Nutrire.\nRassodare.'},
                {'fr': 'La nutrition.\nLa fermeté.', 'it': 'Nutrimento.\nCompattezza.'}],
  'caption': {
   'fr': 'La nutrition et la fermeté, dans un même soin.\n\nCrème Sublime Revitalisante nourrit la peau en profondeur et contribue à une peau plus ferme. Sa texture riche et fondante transforme l’application en un moment de soin.\n\nDécouvrez Crème Sublime Revitalisante sur ioma-paris.com.\n\n#IOMAParis #CrèmeSublimeRevitalisante #SoinVisage',
   'it': 'Nutrimento e compattezza, in un unico trattamento.\n\nCrème Sublime Revitalisante nutre la pelle in profondità e contribuisce a renderla più soda. La sua texture ricca e fondente trasforma l’applicazione in un momento di cura.\n\nScopri Crème Sublime Revitalisante su ioma-paris.com.\n\n#IOMAParis #CrèmeSublimeRevitalisante #Skincare'},
  'scenes': ['silk-ivory', 'silk-pearl'],
 },
 'cc-gel': {
  'name': 'CC Gel',
  'claim_it': 'Un incarnato luminoso, dalla coprenza naturale.',
  'source': 'https://ioma-paris.com/products/cc-gel-soin-teinte-eclat-parfait',
  'category': {'fr': 'ÉCLAT & TEINT NATUREL', 'it': 'LUMINOSITÀ & NATURALEZZA'},
  'headlines': [{'fr': 'L’éclat.\nAu naturel.', 'it': 'Luce.\nAl naturale.'},
                {'fr': 'Un teint\nlumineux.', 'it': 'Un incarnato\nluminoso.'}],
  'caption': {'fr': 'Un teint lumineux, une couvrance naturelle.\n\nCC Gel accompagne votre routine avec un fini naturel et lumineux.\n\nDécouvrez CC Gel sur ioma-paris.com.\n\n#IOMAParis #CCGel #Éclat',
              'it': 'Un incarnato luminoso, una coprenza naturale.\n\nCC Gel accompagna la tua routine con un risultato naturale e luminoso.\n\nScopri CC Gel su ioma-paris.com.\n\n#IOMAParis #CCGel #IncarnatoLuminoso'},
  'scenes': ['silk-pearl', 'silk-ivory'],
 },
 'creme-genereuse-contour-des-yeux': {
  'name': 'Crème Généreuse\nContour des Yeux',
  'claim_it': 'Leviga rughe e linee sottili del contorno occhi.',
  'source': 'https://ioma-paris.com/products/creme-genereuse-contour-des-yeux',
  'category': {'fr': 'SOIN DU CONTOUR DES YEUX', 'it': 'TRATTAMENTO CONTORNO OCCHI'},
  'headlines': [{'fr': 'Lisser.\nDéfroisser.', 'it': 'Levigare.\nDistendere.'},
                {'fr': 'Cibler les\nridules.', 'it': 'Linee sottili.\nCura mirata.'}],
  'caption': {'fr': 'Un soin dédié au contour des yeux.\n\nCrème Généreuse Contour des Yeux lisse les rides et les ridules de cette zone délicate.\n\nDécouvrez le soin sur ioma-paris.com.\n\n#IOMAParis #ContourDesYeux #SoinVisage',
              'it': 'Un trattamento dedicato al contorno occhi.\n\nCrème Généreuse Contour des Yeux leviga rughe e linee sottili di questa zona delicata.\n\nScopri il trattamento su ioma-paris.com.\n\n#IOMAParis #ContornoOcchi #Skincare'},
  'scenes': ['silk-ivory', 'silk-pearl'],
 },
}


def campaign_plan(product, history):
    key = product['id'].split(':')[-1]
    if key not in BRIEFS:
        raise ValueError('Manca un brief editoriale verificato per '+product['name'])
    brief = BRIEFS[key]
    if product['data']['editorial']['claim_it'] != brief['claim_it']:
        raise ValueError('Il claim del catalogo è cambiato: aggiornare prima il brief bilingue.')
    previous = next((r.get('creative', {}) for r in history if r.get('product_id') == product['id']), {})
    variants = [i for i in range(len(brief['headlines'])) if i != previous.get('variant')]
    variant = secrets.choice(variants)
    last_scene = next((r.get('creative', {}).get('scene', {}).get('id') for r in history), None)
    scene_id = secrets.choice([s for s in brief['scenes'] if s != last_scene])
    scenes = json.loads((ROOT/'assets/backgrounds/editorial-scenes.json').read_text())
    scene = next(s for s in scenes if s['id'] == scene_id)
    copies = {lang: {'language': lang, 'headline': brief['headlines'][variant][lang],
                     'category': brief['category'][lang], 'product_name': brief['name'],
                     'cta': 'Découvrir' if lang == 'fr' else 'Scopri',
                     'caption': brief['caption'][lang]} for lang in LANGUAGES}
    return {'variant': variant, 'scene': scene, 'copies': copies, 'source': brief['source'],
            'source_claim_it': brief['claim_it'], 'editorial_basis': 'documented_product_benefit',
            'art_direction': 'Soft studio light, restrained silk, original packshot, editorial typography.'}
