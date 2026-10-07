"""Headline relevance checks for beauty news collected from RSS search."""
import re


BEAUTY_TERMS = re.compile(
    r'\b(?:beauty|skincare|skin|glow|radiance|make-?up|trucc\w*|cosmetic\w*|'
    r'pelle|capelli|hair|cipria|blush|fondotinta|mascara|rossett\w*|gloss|'
    r'ombretto|eyeshadow|peeling|siero|sieri|serum|crema|creme|crème|'
    r'peptid\w*|toner|profum\w*|fragran\w*|idrata\w*|hydrata\w*|rughe)\b',
    re.IGNORECASE,
)


def is_beauty_headline(title):
    # RSS can match article bodies; require a beauty signal in the title too.
    return bool(BEAUTY_TERMS.search(title))
