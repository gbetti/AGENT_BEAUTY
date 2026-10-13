"""Keyword & Domanda: auditable FR/IT queries, without creating product claims."""
from agents.contracts import KeywordBrief
from google_trends import research_trends


class KeywordAgent:
    def run(self, trends, now):
        if trends.created_at != now:
            raise ValueError('Il brief trend appartiene a un’altra esecuzione.')
        markets = research_trends(trends.weekly, now)
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
        return KeywordBrief(now, trends.product['id'], markets, hypotheses)
