"""Create French and Italian campaigns through three specialized agents."""
import argparse
from pathlib import Path
import sys

# Public helper imports retained for existing scripts and archived workflows.
from catalog import initialize, link_product_images, load_products
from agents.assets import export_campaign
from agents.trends import choose_product, parse_news, search_news
from coordinator import BeautyCoordinator

ROOT = Path(__file__).resolve().parent


def run(args, *, progress=None):
    return BeautyCoordinator().run(args, progress=progress)


def cli_progress(agent, status):
    names = {'trends': '1/3 Trend Beauty', 'keywords': '2/3 Keyword & Domanda',
             'assets': '3/3 Creative Studio'}
    labels = {'running': 'in corso', 'completed': 'completato', 'failed': 'fallito'}
    print(f"[{names[agent]}] {labels[status]}", file=sys.stderr, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=ROOT/'data/catalog.sqlite')
    parser.add_argument('--output', type=Path, default=ROOT/'output')
    parser.add_argument('--product', help='Parte del nome per scegliere il prodotto')
    parser.add_argument('--creative-mode', choices=('auto', 'product', 'model', 'pack'), default='auto',
                        help='Rotazione automatica: prodotto, modella, pack; oppure scegli un formato')
    parser.add_argument('--editorial-mode', choices=('auto', 'claim', 'inspiration', 'review'), default='auto')
    parser.add_argument('--inspiration-theme', choices=('ingredients', 'skin'), default='ingredients')
    parser.add_argument('--review-id', help='ID di una recensione pubblica del prodotto selezionato')
    parser.add_argument('--pack-products', nargs='+', metavar='PRODUCT_KEY',
                        help='Chiavi dei prodotti da affiancare al protagonista; stesso ambito viso/capelli')
    parser.add_argument('--instagram-username', default='gb77ita',
                        help='Profilo proposto per la conferma di ogni feed (predefinito: gb77ita)')
    parser.add_argument('--research', type=Path, default=ROOT/'research/2026-10-08.json', help='Brief settimanale verificato nelle ultime 36 ore')
    parser.add_argument('--email-subject-fr', help='Oggetto francese esatto dell’email, massimo 55 caratteri')
    parser.add_argument('--email-subject-it', help='Oggetto italiano esatto dell’email, massimo 55 caratteri')
    parser.add_argument('--email-assets-url',
                        help='Base HTTPS degli asset: ogni lingua usa <base>/<lingua>/feed.png ed email-logo.png')
    parser.add_argument('--email-unsubscribe-url',
                        help='URL HTTPS di disiscrizione; l’HTML usa il tag Klaviyo quando non specificato')
    args = parser.parse_args()
    try:
        run(args, progress=cli_progress)
    except Exception as error:
        parser.exit(1, f'Errore: {error}\n')


if __name__ == '__main__':
    main()
