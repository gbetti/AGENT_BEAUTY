"""Preview the three art directions; these are not researched, publishable campaigns."""
import argparse
import hashlib
import json
from pathlib import Path

from catalog import ROOT, load_products
from editorial import campaign_plan
from studio import render_campaign


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=ROOT/'data/catalog.sqlite')
    parser.add_argument('--product', default='shampooing-soin-hydratant-anti-casse', help='Chiave del prodotto')
    parser.add_argument('--output', required=True, type=Path, help='Nuova cartella per le anteprime tecniche')
    args = parser.parse_args(argv)
    products = load_products(args.database)
    product = next((p for p in products if p['id'].rsplit(':', 1)[-1] == args.product), None)
    if product is None:
        parser.error('Chiave del prodotto non trovata.')
    args.output.mkdir(parents=True, exist_ok=False)
    history = []
    for mode in ('product', 'model', 'pack'):
        plan = campaign_plan(product, history, mode=mode, products=products)
        history.insert(0, {'product_id': product['id'], 'creative': plan})
        # Only documented registry labels, with no fabricated weekly evidence.
        ingredients = json.loads((ROOT/'assets/ingredients.json').read_text()).get(args.product, [])[:2]
        outputs = {}
        for lang, copy in plan['copies'].items():
            folder = args.output/mode/lang
            folder.mkdir(parents=True)
            copy['ingredients'] = ingredients
            graphics = render_campaign(product, copy, folder, plan['scene'])
            outputs[lang] = {kind: hashlib.sha256(info['path'].read_bytes()).hexdigest() for kind, info in graphics.items()}
        manifest = {'preview_only': True, 'publication_status': 'not_published',
                    'reason': 'Layout validation; not a new weekly researched campaign.',
                    'creative': plan, 'export_sha256': outputs}
        (args.output/mode/'design.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
        print(args.output/mode)
    print('Anteprime tecniche: ricerca e revisione della campagna necessarie prima di offrire la pubblicazione.')


if __name__ == '__main__':
    main()
