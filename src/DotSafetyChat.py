import re
import os

STATE_ABBR_TO_FIPS = {
    'AL':'01','AK':'02','AZ':'04','AR':'05','CA':'06','CO':'08','CT':'09','DE':'10',
    'DC':'11','FL':'12','GA':'13','HI':'15','ID':'16','IL':'17','IN':'18','IA':'19',
    'KS':'20','KY':'21','LA':'22','ME':'23','MD':'24','MA':'25','MI':'26','MN':'27',
    'MS':'28','MO':'29','MT':'30','NE':'31','NV':'32','NH':'33','NJ':'34','NM':'35',
    'NY':'36','NC':'37','ND':'38','OH':'39','OK':'40','OR':'41','PA':'42','RI':'44',
    'SC':'45','SD':'46','TN':'47','TX':'48','UT':'49','VT':'50','VA':'51','WA':'53',
    'WV':'54','WI':'55','WY':'56','PR':'72',
}

STATE_NAME_TO_FIPS = {
    'alabama':'01','alaska':'02','arizona':'04','arkansas':'05','california':'06',
    'colorado':'08','connecticut':'09','delaware':'10','district of columbia':'11',
    'florida':'12','georgia':'13','hawaii':'15','idaho':'16','illinois':'17',
    'indiana':'18','iowa':'19','kansas':'20','kentucky':'21','louisiana':'22',
    'maine':'23','maryland':'24','massachusetts':'25','michigan':'26','minnesota':'27',
    'mississippi':'28','missouri':'29','montana':'30','nebraska':'31','nevada':'32',
    'new hampshire':'33','new jersey':'34','new mexico':'35','new york':'36',
    'north carolina':'37','north dakota':'38','ohio':'39','oklahoma':'40','oregon':'41',
    'pennsylvania':'42','rhode island':'44','south carolina':'45','south dakota':'46',
    'tennessee':'47','texas':'48','utah':'49','vermont':'50','virginia':'51',
    'washington':'53','west virginia':'54','wisconsin':'55','wyoming':'56',
    'puerto rico':'72',
}

BEHAVIOR_KEYWORDS = {
    'alcohol':            ['alcohol','drunk','dui','dwi','impaired','drinking','bac'],
    'speeding':           ['speed','speeding','fast'],
    'distracted_driving': ['distract','phone','texting','inattention'],
    'drowsy_driving':     ['drowsy','fatigue','tired','sleep'],
    'seatbelt_nonuse':    ['seatbelt','seat belt','belt','restraint'],
    'pedestrian_fatality':['pedestrian','walker','walking'],
    'wrong_way':          ['wrong way','wrong-way'],
    'hit_run':            ['hit and run','hit-and-run','hit run'],
    'drugs':              ['drug','narcotics','opioid'],
}

METHODOLOGY = {
    'behavioral_analysis': (
        'Behavioral flags from NHTSA FARS Auxiliary Crash file (acc_aux). '
        'All counts are fatal crashes unless otherwise noted.'
    ),
    'benchmark': (
        'Fatality rate per 100K: NHTSA FARS fatalities ÷ Census NST-EST population × 100,000. '
        'VMT rate: fatalities ÷ FHWA VM-2 vehicle-miles-traveled (millions) × 100. '
        'National rank: states sorted by rate/100K descending (1 = highest/worst rate).'
    ),
    'hotspots': (
        'County data from FARS county_name field. Top 10 counties by fatality count shown.'
    ),
    'trend': (
        'Year-over-year trend from NHTSA FARS 2021-2024.'
    ),
    'countermeasures': (
        'Countermeasures sourced from NHTSA "Countermeasures That Work," 10th Edition (2023).'
    ),
}


def _extract_state(query):
    q = query.lower()
    for name, fips in STATE_NAME_TO_FIPS.items():
        if name in q:
            return fips
    for abbr, fips in STATE_ABBR_TO_FIPS.items():
        if re.search(r'\b' + abbr.lower() + r'\b', q):
            return fips
    return None


def _extract_year(query):
    m = re.search(r'\b(202[1-4])\b', query)
    return int(m.group(1)) if m else 2024


def _extract_behavior(query):
    q = query.lower()
    for bid, keywords in BEHAVIOR_KEYWORDS.items():
        for kw in keywords:
            if kw in q:
                return bid
    return None


def _classify_intent(query):
    q = query.lower()
    if any(w in q for w in ['top','issue','problem','cause','contributor','worst']):
        return 'behavioral_analysis'
    if any(w in q for w in ['compare','benchmark','rank','national','average','rate']):
        return 'benchmark'
    if any(w in q for w in ['county','where','hotspot','location','map']):
        return 'hotspots'
    if any(w in q for w in ['trend','over time','increasing','decreasing','worse','better','year']):
        return 'trend'
    if any(w in q for w in ['countermeasure','recommend','program','strategy','fix','reduce']):
        return 'countermeasures'
    return 'behavioral_analysis'


def _fetch_data(query, state_fips, year, intent):
    state = c3.StateRef.fetch({
        'filter': c3.Filter.eq('fips', state_fips), 'include': 'this', 'limit': 1,
    }).objs
    state_name = state[0].name if state else state_fips
    state_abbr = state[0].abbr if state else ''
    base = {'stateName': state_name, 'stateAbbr': state_abbr}

    if intent == 'benchmark':
        bm = c3.DotSafetyBenchmark.getAllBenchmarks(year, None)
        st = next((s for s in bm['states'] if s['stateFips'] == state_fips), None)
        return {**base, 'benchmark': st, 'national': bm['national'],
                'nStates': bm['nStates'], 'allStates': bm['states']}

    if intent == 'hotspots':
        bid      = _extract_behavior(query) or 'speeding'
        counties = c3.DotSafetyBehavioral.getCountyHotspots(state_fips, year, bid, 10, None)
        return {**base, 'behaviorId': bid, 'counties': counties}

    if intent == 'trend':
        bid   = _extract_behavior(query) or 'speeding'
        trend = c3.DotSafetyBehavioral.getYoyTrend(state_fips, bid)
        return {**base, 'behaviorId': bid, 'trend': trend}

    if intent == 'countermeasures':
        recs = c3.DotSafetyCountermeasures.getRecommendations(state_fips, year, None, None, None, None)
        return {**base, 'recommendations': recs}

    analysis = c3.DotSafetyBehavioral.getStateAnalysis(state_fips, year, 3, None)
    bm       = c3.DotSafetyBenchmark.getStateBenchmark(state_fips, year, None)
    return {**base, 'analysis': analysis, 'benchmark': bm}


def _format_context(intent, year, data):
    name = data.get('stateName', 'Unknown')
    abbr = data.get('stateAbbr', '')

    if intent == 'benchmark':
        st   = data.get('benchmark') or {}
        nat  = data.get('national') or {}
        top10 = sorted(data.get('allStates', []), key=lambda s: s.get('rank100k') or 999)[:10]
        lines = [
            f'State: {name} ({abbr}), Year: {year}',
            f"Fatalities: {st.get('fatals', 'N/A')}",
            f"Rate per 100K: {st.get('ratePer100k', 'N/A')}",
            f"National rank: #{st.get('rank100k', 'N/A')} of {data.get('nStates', 'N/A')} states",
            f"vs national avg (%): {st.get('vsNationalPct', 'N/A')}",
            f"National avg rate/100K: {nat.get('ratePer100k', 'N/A')}",
            '', 'Top 10 states by fatality rate:',
        ] + [f"  #{s.get('rank100k')} {s.get('abbr')} {s.get('name')}: {s.get('ratePer100k')} per 100K" for s in top10]
        return '\n'.join(lines)

    if intent == 'hotspots':
        lines = [f'State: {name} ({abbr}), Year: {year}', ''] + [
            f"  {i+1}. {c['name']}: {c['fatals']} fatalities, {c['crashes']} crashes"
            for i, c in enumerate(data.get('counties', []))
        ]
        return '\n'.join(lines)

    if intent == 'trend':
        t   = data.get('trend', {})
        pts = t.get('trend', [])
        lines = [f'State: {name} ({abbr})', ''] + [
            f"  {p['year']}: {p['crashes']} fatal crashes" for p in pts
        ] + ['', f"Overall direction: {t.get('overallDirection')}", f"Overall % change: {t.get('overallPctChange')}%"]
        return '\n'.join(lines)

    if intent == 'countermeasures':
        recs  = data.get('recommendations', [])
        lines = [f'State: {name} ({abbr}), Year: {year}', '']
        for r in recs:
            lines.append(f"Behavior: {r.get('behaviorId')}")
            for cm in r.get('countermeasures', [])[:3]:
                lines.append(f"  - {cm.get('title')} | evidence: {cm.get('evidenceLevel')} | program: {cm.get('programType')}")
                if cm.get('summary'):
                    lines.append(f"    {cm['summary'][:200]}")
            lines.append('')
        return '\n'.join(lines)

    # behavioral_analysis
    analysis  = data.get('analysis', {})
    bm        = data.get('benchmark', {})
    behaviors = analysis.get('behaviors', [])
    lines = [
        f'State: {name} ({abbr}), Year: {year}',
        f"Total fatal crashes: {analysis.get('totalCrashes', 0)}",
        f"Total fatalities: {analysis.get('totalFatals', 0)}",
        f"Rate per 100K: {bm.get('ratePer100k', 'N/A')}",
        '', 'Top 3 behavioral contributors:',
    ]
    for b in behaviors:
        lines.append(f"  #{b['rank']} {b['name']}: {b['crashes']} crashes ({b.get('pctCrashes', 0):.1f}% of total), trend: {b['trend']}")
    return '\n'.join(lines)


def _answer_with_llm(query, year, intent, data):
    import anthropic
    context = _format_context(intent, year, data)
    client  = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY', ''))
    msg = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=512,
        system=(
            'You are a highway safety analyst. Answer questions about state crash data '
            'using ONLY the data provided — never invent numbers not in the context. '
            'Cite NHTSA FARS as the source. Keep answers concise (under 150 words). '
            'Note that correlation does not imply causation.'
        ),
        messages=[{'role': 'user', 'content': f'Data context:\n{context}\n\nQuestion: {query}'}],
    )
    return msg.content[0].text


def _answer_without_llm(query, year, intent, data):
    state_name = data.get('stateName', 'this state')

    if intent == 'benchmark':
        st  = data.get('benchmark') or {}
        nat = data.get('national') or {}
        direction = 'above' if (st.get('vsNational100k') or 0) > 0 else 'below'
        return (
            f"{state_name} had {st.get('fatals', 0):,} fatalities in {year}, "
            f"a rate of {st.get('ratePer100k')} per 100K. "
            f"That's {direction} the national average by {abs(st.get('vsNationalPct') or 0):.1f}%. "
            f"Ranked #{st.get('rank100k')} of {data.get('nStates')} states."
        )

    if intent == 'hotspots':
        counties = data.get('counties', [])
        names = [f"{c['name']} ({c['fatals']} fatalities)" for c in counties[:5]]
        return f"Top counties in {state_name} ({year}): " + ', '.join(names) + '.'

    if intent == 'trend':
        t   = data.get('trend', {})
        pts = ', '.join(f"{p['year']}: {p['crashes']}" for p in t.get('trend', []))
        return (
            f"{t.get('behaviorName')} crashes in {state_name}: {pts}. "
            f"Overall trend: {t.get('overallDirection')}"
            + (f" ({t.get('overallPctChange'):+.1f}%)." if t.get('overallPctChange') is not None else '.')
        )

    if intent == 'countermeasures':
        recs  = data.get('recommendations', [])
        lines = []
        for r in recs:
            for cm in r.get('countermeasures', [])[:2]:
                lines.append(f"• {cm.get('title')} ({cm.get('evidenceLevel')} evidence)")
        return f"Top countermeasure recommendations for {state_name}:\n" + '\n'.join(lines)

    analysis  = data.get('analysis', {})
    behaviors = analysis.get('behaviors', [])
    if not behaviors:
        return f'No data available for {state_name} in {year}.'
    top3 = ', '.join(f"#{b['rank']} {b['name']} ({b['crashes']:,} crashes)" for b in behaviors)
    return (
        f"Top safety issues in {state_name} ({year}): {top3}. "
        f"Total fatalities: {analysis.get('totalFatals', 0):,}."
    )


def chat(cls, query, sessionId=None):
    state_fips = _extract_state(query) or '48'
    year       = _extract_year(query)
    intent     = _classify_intent(query)

    data = _fetch_data(query, state_fips, year, intent)

    api_key = os.getenv('ANTHROPIC_API_KEY', '')
    if api_key:
        try:
            answer = _answer_with_llm(query, year, intent, data)
        except Exception:
            answer = _answer_without_llm(query, year, intent, data)
    else:
        answer = _answer_without_llm(query, year, intent, data)

    state_name = data.get('stateName', state_fips)

    state = c3.StateRef.fetch({
        'filter': c3.Filter.eq('fips', state_fips), 'include': 'this', 'limit': 1,
    }).objs
    name = state[0].name if state else state_fips
    suggestions = {
        'behavioral_analysis': [
            f'How does {name} compare to the national average?',
            f'Which counties have the most alcohol crashes in {name}?',
            f'What countermeasures are recommended for {name}?',
        ],
        'benchmark': [
            f'What are the top safety issues in {name}?',
            f'Is speeding getting better or worse in {name}?',
            'Which states have the highest fatality rates?',
        ],
        'hotspots': [
            f'What are the top safety issues in {name}?',
            f'What countermeasures address this in {name}?',
        ],
        'trend': [
            f'How does {name} rank nationally?',
            f'What countermeasures are recommended for {name}?',
        ],
        'countermeasures': [
            f'What are the top behaviors in {name}?',
            f'How does {name} compare nationally?',
        ],
    }.get(intent, [])

    return {
        'answer':             answer,
        'intent':             intent,
        'stateFips':          state_fips,
        'stateName':          state_name,
        'year':               year,
        'data':               data,
        'explanation':        METHODOLOGY.get(intent, ''),
        'disclaimer':         'Correlation does not imply causation. Source: NHTSA FARS.',
        'suggestedQuestions': suggestions,
    }
