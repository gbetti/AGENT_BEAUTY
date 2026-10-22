"""Creative Studio: consume the shared brief and export original-product assets."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3

from agents.contracts import CampaignBrief
from agents.trends import QUERY
from creative import recent_campaigns
from delivery import create_manifest
from editorial import LANGUAGES, campaign_plan
from newsletter import create_email
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
        creative = campaign_plan(product, recent_campaigns(args.database))
        ingredients = select_ingredients(product, trends.weekly, creative['source'], now)
        # Keep both upstream results intact; the creative agent works on its own copy.
        weekly = deepcopy(trends.weekly)
        weekly['google_trends_results'] = deepcopy(keywords.markets)
        creative['research_basis'] = {
            'source_ids': [source['id'] for source in weekly['sources']],
            'ingredient_ids': [ingredient['id'] for ingredient in ingredients],
            'keyword_hypotheses': deepcopy(keywords.messaging_hypotheses),
            'public_copy_basis': 'documented_product_benefit',
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
        localized_reports = {}
        for language in languages:
            copy = creative['copies'][language]
            locale_working = working/language
            locale_working.mkdir()
            graphics = render_campaign(product, copy, locale_working, creative['scene'])
            (locale_working/'caption.txt').write_text(copy['caption'].strip()+'\n', encoding='utf-8')
            localized_reports[language] = {
                **copy,
                'graphics': {kind: {**{k: v for k, v in info.items() if k != 'path'},
                                    'path': str((directory/language/info['path'].name).resolve())}
                             for kind, info in graphics.items()}}
        report = {'created_at': now.isoformat(), 'window_start': (now-timedelta(days=7)).isoformat(),
                  'query': QUERY, 'product': product['name'], 'product_id': product['id'],
                  'creative': creative, 'source_claim': claim, 'theme': theme,
                  'weekly': weekly, 'ingredients': ingredients,
                  'theme_news_counts': scores, 'matched_news': matched, 'news': news,
                  'localizations': localized_reports,
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
        report['delivery'] = create_manifest(working, generation_id)
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
        result[language]['caption'] = directory/language/'caption.txt'
        for path in result[language].values():
            print(path.resolve())
    print((directory/'delivery.json').resolve())
    print('Post + story + email creati. Invio Gmail a '
          + report['delivery']['email']['to'] + ' e pubblicazione story su @'
          + report['delivery']['instagram_story']['username'] + ' in attesa: consegna da completare.')
    return result
