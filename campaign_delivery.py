"""Finalize coordinated emails only with the durable receipt of this campaign's post."""
import json
from pathlib import Path
import sqlite3

from catalog import load_products
from newsletter import create_email


def finalize_published_emails(database, generation, state, assets_url):
    with sqlite3.connect(state) as db:
        db.row_factory = sqlite3.Row
        receipts = [dict(row) for row in db.execute(
            'SELECT * FROM instagram_publications WHERE generation_id=? AND status=? AND permalink IS NOT NULL',
            (generation, 'published'))]
    if len(receipts) != 1:
        raise ValueError('Serve il permalink confermato dell’unico post pubblicato per questa campagna.')
    receipt = receipts[0]
    with sqlite3.connect(database) as db:
        row = db.execute('SELECT research_json FROM generations WHERE id=?', (generation,)).fetchone()
        if not row:
            raise ValueError('Generazione non trovata.')
        report = json.loads(row[0])
        product = next(p for p in load_products(database) if p['id'] == report['product_id'])
        report['instagram_publication'] = {k: receipt[k] for k in ('status','media_id','permalink','language')}
        for language, localized in report['localizations'].items():
            directory = Path(localized['graphics']['feed']['path']).parent
            updated = create_email(product, {**report, 'headline': localized['headline'], 'instagram_url': receipt['permalink']},
                directory/'feed.png', directory, language=language, subject=localized['email']['subject'],
                assets_url=assets_url.rstrip('/')+'/'+language)
            localized['email'] = {k: str(v) if isinstance(v, Path) else v for k,v in updated.items()}
            for name in ('email.html', 'email.eml'):
                report['quality']['reviewed_sha256'].pop(language+'/'+name, None)
        report['quality'].update(visual_review='pending_email_recheck', publication_status='published')
        db.execute('UPDATE generations SET research_json=? WHERE id=?', (json.dumps(report, ensure_ascii=False), generation))
    return receipt['permalink']
