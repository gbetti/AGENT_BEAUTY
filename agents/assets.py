"""Creative Studio: consume the shared brief and export original-product assets."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3

from agents.contracts import CampaignBrief
from agents.trends import QUERY, HAIR_QUERY
from catalog import load_products
from creative import recent_campaigns
from editorial import LANGUAGES, campaign_plan
from newsletter import create_email
from email_delivery import delivery_intent
from instagram_approval import publication_question
from radar_presentation import create_presentation
from studio import render_campaign
from weekly import select_ingredients


class AssetsAgent:
    def prepare(self, trends, keywords, args, now):
        if trends.created_at != now or keywords.created_at != now:
            raise ValueError('I brief appartengono a un’altra esecuzione.')
        if trends.product['id'] != keywords.product_id:
            raise ValueError('Il brief keyword riguarda un altro prodotto.')
        product = trends.product
        if trends.source_claim != product['data']['editorial']['claim_it']:
            raise ValueError('Il claim del brief trend non corrisponde al catalogo.')
        creative = campaign_plan(product, recent_campaigns(args.database, limit=-1),
                                 mode=getattr(args, 'creative_mode', 'auto'),
                                 products=load_products(args.database),
                                 pack_keys=getattr(args, 'pack_products', ()) or ())
        from editorial_modes import apply_editorial_mode
        creative = apply_editorial_mode(creative, product, recent_campaigns(args.database, limit=-1),
            mode=getattr(args, 'editorial_mode', 'auto'), review_id=getattr(args, 'review_id', None),
            theme=getattr(args, 'inspiration_theme', 'ingredients'))
        ingredients = select_ingredients(product, trends.weekly, creative['source'], now)
        # Keep both upstream results intact; the creative agent works on its own copy.
        weekly = deepcopy(trends.weekly)
        weekly['google_trends_results'] = deepcopy(keywords.markets)
        creative['research_basis'] = {
            'source_ids': [source['id'] for source in weekly['sources']],
            'ingredient_ids': [ingredient['id'] for ingredient in ingredients],
            'keyword_hypotheses': deepcopy(keywords.messaging_hypotheses),
            'public_copy_basis': creative.get('editorial_basis', 'documented_product_benefit'),
        }
        return CampaignBrief(trends, keywords, weekly, creative, ingredients)

    def run(self, trends, keywords, args, now, pipeline=None):
        brief = self.prepare(trends, keywords, args, now)
        return export_campaign(args, now, trends.product, trends.theme, trends.source_claim,
                               trends.matched_news, trends.theme_scores, trends.news,
                               brief.weekly, brief.creative, brief.ingredients,
                               campaign_brief=brief, pipeline=pipeline)


def export_campaign(args, now, product, theme, claim, matched, scores, news,
                    weekly, creative, ingredients, *, campaign_brief=None, pipeline=None):
    """Render verified evidence and store exports; no remote delivery here."""
    for copy in creative['copies'].values():
        copy['ingredients'] = ingredients
    import tempfile
    import uuid
    import shutil
    args.output.mkdir(parents=True, exist_ok=True)
    generation_id = now.strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8]
    directory = args.output / ('ioma-' + generation_id)
    if directory.exists():
        raise FileExistsError('La cartella della campagna esiste già: nessun file è stato sostituito.')
    working = Path(tempfile.mkdtemp(prefix='.campaign-', dir=args.output))
    published = False
    try:
        languages = LANGUAGES
        instagram_username = getattr(args, 'instagram_username', 'gb77ita')
        localized_reports = {}
        for language in languages:
            copy = creative['copies'][language]
            locale_working = working/language
            locale_working.mkdir()
            graphics = render_campaign(product, copy, locale_working, creative['scene'])
            localized_reports[language] = {
                **copy,
                'instagram': {'status': 'awaiting_review_and_confirmation',
                              'username': instagram_username,
                              'question': publication_question(instagram_username, language)},
                'graphics': {kind: {**{k: v for k, v in info.items() if k != 'path'},
                                    'path': str((directory/language/info['path'].name).resolve())}
                             for kind, info in graphics.items()}}
        report = {'created_at': now.isoformat(), 'window_start': (now-timedelta(days=7)).isoformat(),
                  'query': HAIR_QUERY if product['data'].get('editorial', {}).get('theme') == 'hair' else QUERY,
                  'product': product['name'], 'product_id': product['id'],
                  'creative': creative, 'source_claim': claim, 'theme': theme,
                  'weekly': weekly, 'ingredients': ingredients,
                  'theme_news_counts': scores, 'matched_news': matched, 'news': news,
                  'localizations': localized_reports,
                  'email_delivery': delivery_intent(),
                  'quality': {'technical_checks': 'passed', 'visual_review': 'pending',
                              'publication_status': 'not_published'},
                  'limitations': 'Weekly sources guide editorial ingredient selection, not concentration ranking. '
                                 'Advertising coverage is not proof of current paid delivery or budgets. '
                                 'Public copy uses documented IOMA claims.'}
        if campaign_brief is not None:
            report['campaign_brief'] = campaign_brief.summary()
        if pipeline is not None:
            report['agent_pipeline'] = pipeline
        for language in languages:
            graphics_paths = {kind: working/language/(kind+'.png') for kind in ('feed','story','banner')}
            presentation = create_presentation(product, report, graphics_paths, working/language/'presentazione.pptx', language)
            presentation['path'] = str((directory/language/'presentazione.pptx').resolve())
            report['localizations'][language]['presentation'] = presentation
        history = recent_campaigns(args.database)
        assets_base = getattr(args, 'email_assets_url', None)
        for language in languages:
            email_report = {**report, 'headline': localized_reports[language]['headline']}
            newsletter = create_email(product, email_report, working/language/'feed.png', working/language,
                                      language=language, history=history,
                                      subject=getattr(args, 'email_subject_'+language, None),
                                      assets_url=assets_base.rstrip('/')+'/'+language if assets_base else None,
                                      unsubscribe_url=getattr(args, 'email_unsubscribe_url', None))
            report['localizations'][language]['email'] = {
                key: str((directory/language/value.name).resolve()) if isinstance(value,Path) else value
                for key,value in newsletter.items()}
        # Mark successful rendering before storing the same pipeline trace atomically.
        if pipeline is not None:
            pipeline['stages'][-1].update(status='completed',
                finished_at=datetime.now(timezone.utc).isoformat())
        # Graphics, decks, coordinated emails and history are committed together.
        with sqlite3.connect(args.database) as db:
            db.execute('INSERT INTO generations VALUES(?,?,?,?,?)',
                       (generation_id, now.isoformat(), product['id'], str((directory/languages[0]/'feed.png').resolve()),
                        json.dumps(report, ensure_ascii=False)))
            working.rename(directory)
            published = True
    except Exception:
        shutil.rmtree(working, ignore_errors=True)
        # This directory belongs to this invocation, never to an earlier campaign.
        if published and directory.exists():
            shutil.rmtree(directory)
        raise
    result = {language: {kind: directory/language/(kind+'.png') for kind in graphics}
              for language in languages}
    for language in languages:
        result[language]['presentation'] = directory/language/'presentazione.pptx'
        result[language]['email'] = directory/language/'email.html'
        result[language]['email_draft'] = directory/language/'email.eml'
        for path in result[language].values():
            print(path.resolve())
        print(localized_reports[language]['instagram']['question'])
    print('Nessun post inviato. Prima della risposta: completa la revisione visiva, '
          'prepara il JPEG pubblico e usa python -m agents.publisher offer. '
          'La conferma di un feed non autorizza gli altri contenuti.')
    print(f"Email e asset destinati a {report['email_delivery']['recipient']}. "
          'Dopo la revisione visiva registrata, esegui: '
          f'python -m agents.mailer deliver --generation {generation_id} '
          f'--database {args.database} --output {directory}/delivery. '
          'L’invio email è già autorizzato; richiede un mittente collegato.')
    return result
