"""Keyword & Domanda: auditable FR/IT queries, without creating product claims."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import uuid

from agents.contracts import KeywordBrief
from catalog import load_products
from google_trends import research_trends
from weekly import load_brief

ROOT = Path(__file__).resolve().parents[1]


class KeywordAgent:
    def run(self, trends, now):
        if trends.created_at != now:
            raise ValueError('Il brief trend appartiene a un’altra esecuzione.')
        expected_category = 146 if trends.product['data'].get('editorial', {}).get('theme') == 'hair' else 143
        if trends.weekly['google_trends']['category_id'] != expected_category:
            raise ValueError('La categoria Google Trends non corrisponde al prodotto: capelli 146, viso/corpo 143.')
        return self.analyze(trends.weekly, trends.product['id'], now)

    def analyze(self, weekly, product_id, now):
        """Analyze already verified evidence, without running the other agents."""
        if now.tzinfo is None:
            raise ValueError('La data della ricerca deve includere il fuso orario.')
        if product_id.rsplit(':', 1)[-1] != weekly['product_key']:
            raise ValueError('Il brief keyword riguarda un altro prodotto.')
        markets = research_trends(weekly, now)
        if set(markets) != {'fr', 'it'} or any(
                markets[lang]['data']['geo'] != geo
                for lang, geo in (('fr', 'FR'), ('it', 'IT'))):
            raise ValueError('Servono keyword francesi per FR e italiane per IT.')
        # Interpretations are reviewed hypotheses. Queries/indices stay unchanged
        # and are never substituted for documented IOMA benefits.
        hypotheses = {lang: {'interpretation': result['data']['interpretation'],
                            'status': 'hypothesis_to_test',
                            'product_claim_source': 'local_catalog'}
                      for lang, result in markets.items()}
        return KeywordBrief(now, product_id, markets, hypotheses)


def run_standalone(args, *, now=None):
    """Verified brief → Google Trends → one report; no campaign generation."""
    now = now or datetime.now(timezone.utc)
    print('[Keyword & Domanda] verifica del brief', file=sys.stderr, flush=True)
    weekly = load_brief(args.research, now)
    product = next((product for product in load_products(args.database)
                    if product['id'].rsplit(':', 1)[-1] == weekly['product_key']), None)
    if product is None:
        raise ValueError('Il prodotto del brief non è presente nel database.')
    expected_category = 146 if product['data'].get('editorial', {}).get('theme') == 'hair' else 143
    if weekly['google_trends']['category_id'] != expected_category:
        raise ValueError('La categoria Google Trends non corrisponde al prodotto.')
    print('[Keyword & Domanda] ricerca Google Trends FR e IT', file=sys.stderr, flush=True)
    result = KeywordAgent().analyze(weekly, product['id'], now)
    report = {'schema_version': 1, 'kind': 'keyword_analysis',
              'created_at': result.created_at.isoformat(), 'product_id': result.product_id,
              'research_brief': str(args.research.resolve()),
              'reviewed_at': weekly['reviewed_at'], 'markets': result.markets,
              'messaging_hypotheses': result.messaging_hypotheses,
              'limitations': 'Editorial relevance filter; TOP scores are not search volumes. '
                             'FR/IT scores are not directly comparable. Hypotheses are not product claims.'}
    serialized = json.dumps(report, ensure_ascii=False, indent=2)+'\n'
    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output/('keywords-'+now.strftime('%Y%m%dT%H%M%SZ-')+uuid.uuid4().hex[:8]+'.json')
    created = False
    try:
        with destination.open('x', encoding='utf-8') as stream:
            created = True
            stream.write(serialized)
    except Exception:
        if created:
            destination.unlink(missing_ok=True)
        raise
    for language, country in (('fr', 'Francia'), ('it', 'Italia')):
        data = result.markets[language]['data']
        print(f"\n{country} — {data['period_start']} / {data['period_end']}")
        print('TOP — indice relativo 0–100')
        for row in data['top']:
            print(f"  {row['query']}: {row['value']}")
        print('IN CRESCITA — rispetto ai sette giorni precedenti')
        for row in data['rising']:
            value = 'Impennata (>5000%)' if row['breakout'] else '+'+str(row['value'])+'%'
            print(f"  {row['query']}: {value}")
    print(f'\nReport JSON: {destination.resolve()}')
    print('[Keyword & Domanda] completato', file=sys.stderr, flush=True)
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description='Esegue soltanto la ricerca keyword per Francia e Italia.')
    parser.add_argument('--research', type=Path, required=True,
                        help='Brief della settimana realmente revisionato nelle ultime 36 ore')
    parser.add_argument('--database', type=Path, default=ROOT/'data/catalog.sqlite')
    parser.add_argument('--output', type=Path, default=ROOT/'output/keywords',
                        help='Cartella dei report JSON; ogni avvio crea un nuovo file')
    args = parser.parse_args(argv)
    try:
        run_standalone(args)
    except Exception as error:
        parser.exit(1, f'Errore nell’agente Keyword & Domanda: {error}\n')


if __name__ == '__main__':
    main()
