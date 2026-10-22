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
    parser.add_argument('--research', type=Path, default=ROOT/'research/2026-10-08.json', help='Brief settimanale verificato nelle ultime 36 ore')
    parser.add_argument('--email-subject-fr', help='Oggetto francese esatto dell’email, massimo 55 caratteri')
    parser.add_argument('--email-subject-it', help='Oggetto italiano esatto dell’email, massimo 55 caratteri')
    parser.add_argument('--email-assets-url',
                        help='Base HTTPS degli asset: ogni lingua usa <base>/<lingua>/feed.png ed email-logo.png')
    parser.add_argument('--email-unsubscribe-url',
                        help='URL HTTPS di disiscrizione; l’HTML usa il tag Klaviyo quando non specificato')
    parser.add_argument('--prepare-only', action='store_true',
                        help='Esporta soltanto: Gmail e story Instagram restano pending_deliveries')
    args = parser.parse_args()
    try:
        run(args, progress=cli_progress)
    except Exception as error:
        parser.exit(1, f'Errore: {error}\n')
    if not args.prepare_only:
        parser.exit(2, 'Asset pronti; invio Gmail e pubblicazione story Instagram richiesti. Completare il flusso Codex descritto in AGENTS.md.\n')


if __name__ == '__main__':
    main()
