"""Auditable weekly Google Trends queries, with explicit editorial selection."""
from datetime import datetime, timedelta, timezone
from http.cookiejar import CookieJar
import hashlib
import json
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPCookieProcessor

BASE = 'https://trends.google.com'
METHOD_URL = 'https://support.google.com/trends/answer/4355000'


def week_window(now):
    """Seven completed UTC days, excluding the current partial day."""
    today = now.astimezone(timezone.utc).date()
    return (today-timedelta(days=7)).isoformat(), (today-timedelta(days=1)).isoformat()


def fetch_market(geo, language, category, now):
    if geo not in ('FR', 'IT') or language not in ('fr', 'it'):
        raise ValueError('Mercato Google Trends non supportato.')
    start, end = week_window(now)
    period = start+' '+end
    opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def get(url, structured=True):
        request = Request(url, headers={'User-Agent':'Mozilla/5.0',
                                        'Referer':BASE+'/trends/explore'})
        with opener.open(request, timeout=30) as response:
            raw = response.read(4_000_000).decode('utf-8')
        return json.loads(raw[raw.index('{'):]) if structured else raw

    # Establish the normal public Trends session before requesting its widgets.
    get(BASE+'/trends/?geo='+geo, structured=False)
    request = {'comparisonItem':[{'keyword':'','geo':geo,'time':period}],
               'category':category,'property':''}
    explore = get(BASE+'/trends/api/explore?'+urlencode({
        'hl':language,'tz':'0','req':json.dumps(request,separators=(',',':'))}))
    widget = next(w for w in explore['widgets'] if w['id']=='RELATED_QUERIES')
    response = get(BASE+'/trends/api/widgetdata/relatedsearches?'+urlencode({
        'hl':language,'tz':'0','token':widget['token'],
        'req':json.dumps(widget['request'],separators=(',',':'))}))
    return {'retrieved_at':now.isoformat(),'geo':geo,'language':language,
            'period_start':start,'period_end':end,'category_id':category,
            'category_name':'Face & Body Care','search_property':'web',
            'timezone':'UTC','seed_keyword':'',
            'source_url':BASE+'/trends/explore?'+urlencode({
                'cat':category,'date':period,'geo':geo,'hl':language}),
            'widget_request':widget['request'],'response':response}


def select_queries(packet,selection,now):
    """Keep source order and values; never rank a hand-picked comparison as top searches."""
    start,end = week_window(now)
    if (packet['period_start'],packet['period_end']) != (start,end):
        raise ValueError('Dati Google Trends fuori dalla settimana richiesta.')
    retrieved = datetime.fromisoformat(packet['retrieved_at'])
    if retrieved.tzinfo is None or not timedelta(0)<=now-retrieved<=timedelta(hours=36):
        raise ValueError('Dati Google Trends da aggiornare.')
    req = packet['widget_request']
    restriction = req['restriction']
    first = datetime.fromisoformat(start).date()
    comparison_start=(first-timedelta(days=7)).isoformat()
    comparison_end=(first-timedelta(days=1)).isoformat()
    if (packet['geo'] != selection['geo'] or restriction['geo']['country'] != selection['geo']
            or restriction['time'] != start+' '+end
            or req['requestOptions']['category'] != 143 or packet['category_id'] != 143
            or req['requestOptions']['property'] != '' or packet['search_property'] != 'web'
            or packet.get('seed_keyword') != '' or packet.get('timezone') != 'UTC'
            or req.get('trendinessSettings',{}).get('compareTime') != comparison_start+' '+comparison_end
            or restriction.get('complexKeywordsRestriction')
            or req.get('metric') != ['TOP','RISING'] or req.get('keywordType') != 'QUERY'):
        raise ValueError('Perimetro Google Trends non coerente con il brief.')
    result = {key:packet[key] for key in ('retrieved_at','geo','language','period_start',
              'period_end','category_id','category_name','search_property','timezone','source_url')}
    groups = packet['response']['default']['rankedList']
    if len(groups)!=2:
        raise ValueError('Google Trends non ha restituito TOP e RISING.')
    for metric,group in zip(('top','rising'),groups):
        selected = selection[metric]
        if len(selected)!=len(set(selected)) or not selected:
            raise ValueError('Selezione keyword vuota o duplicata.')
        rows = []
        for rank,row in enumerate(group.get('rankedKeyword',[]),1):
            if row['query'] not in selected:continue
            value = row['value']
            if (not isinstance(value,(int,float)) or isinstance(value,bool) or value<0
                    or (metric=='top' and value>100) or row.get('hasData') is False):
                raise ValueError('Valore Google Trends non valido.')
            rows.append({'query':row['query'],'value':value,'source_rank':rank,
                         'breakout':metric=='rising' and value>5000})
        if any(a['value']<b['value'] for a,b in zip(rows,rows[1:])):
            raise ValueError('Ordine Google Trends inatteso.')
        # Google samples can change within the same day. Choose only present
        # queries from the reviewed relevance pool; never substitute a value.
        result[metric] = rows[:5 if metric=='top' else 3]
    if len(result['top'])!=5 or len(result['rising'])!=3:
        raise ValueError('Il layout richiede cinque query principali e tre in crescita.')
    result['interpretation'] = selection['interpretation']
    result['comparison_start']=comparison_start
    result['comparison_end']=comparison_end
    result['method_url'] = METHOD_URL
    result['response_sha256'] = hashlib.sha256(json.dumps(packet['response'],
        sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    result['selection_note'] = 'Editorial relevance filter; original order, spelling and scores retained. Not exhaustive beauty search volumes.'
    return result


def research_trends(brief,now):
    config = brief['google_trends']
    if config['category_id']!=143 or set(config['markets'])!={'fr','it'}:
        raise ValueError('Configurazione Google Trends non valida.')
    result = {}
    for lang,selection in config['markets'].items():
        packet = fetch_market(selection['geo'],lang,config['category_id'],now)
        result[lang] = {'data':select_queries(packet,selection,now),'evidence':packet}
    return result
