"""Explicit handoffs between research, keyword analysis and creative production."""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TrendBrief:
    created_at: datetime
    product: dict
    theme: str
    source_claim: str
    news: list
    matched_news: list
    theme_scores: dict
    weekly: dict


@dataclass(frozen=True)
class KeywordBrief:
    created_at: datetime
    product_id: str
    markets: dict
    messaging_hypotheses: dict


@dataclass(frozen=True)
class CampaignBrief:
    trends: TrendBrief
    keywords: KeywordBrief
    weekly: dict
    creative: dict
    ingredients: list

    def summary(self):
        """JSON-compatible shared brief, separate from public product claims."""
        return {
            'schema_version': 1,
            'created_at': self.trends.created_at.isoformat(),
            'product_id': self.trends.product['id'],
            'product_name': self.trends.product['name'],
            'source_claim': self.trends.source_claim,
            'product_source_url': self.creative['source'],
            'original_packshots': self.trends.product['images'],
            'theme': self.trends.theme,
            'source_ids': [s['id'] for s in self.weekly['sources']],
            'ingredient_ids': [i['id'] for i in self.ingredients],
            'scene_id': self.creative['scene']['id'],
            'headlines': {lang: copy['headline']
                          for lang, copy in self.creative['copies'].items()},
            'keyword_analysis': {
                lang: {'geo': result['data']['geo'],
                       'period_start': result['data']['period_start'],
                       'period_end': result['data']['period_end'],
                       'top': result['data']['top'],
                       'rising': result['data']['rising'],
                       'source_url': result['data']['source_url']}
                for lang, result in self.keywords.markets.items()},
            'messaging_hypotheses': self.keywords.messaging_hypotheses,
            'claim_policy': 'Catalog benefits only; news and search queries are editorial signals, not efficacy evidence.',
        }
