_summary_cache = {}


def getRecommendations(cls, stateFips, year, topBehaviors=None, minEvidence=None, programType=None, month=None):
    if not topBehaviors:
        analysis     = c3.DotSafetyBehavioral.getStateAnalysis(stateFips, year, 3, month)
        topBehaviors = [b['id'] for b in analysis.get('behaviors', [])]

    results = []
    for bid in topBehaviors:
        cms = c3.Countermeasure.getByBehavior(bid, minEvidence)
        if programType:
            cms = [c for c in cms if (getattr(c, 'programType', '') or '').lower() == programType.lower()]
        results.append({
            'behaviorId':       bid,
            'countermeasures':  [_cm_to_dict(c) for c in cms],
        })
    return results


def getBehaviorSummary(cls, stateFips, year, behaviorId):
    key = f'{stateFips}_{year}_{behaviorId}'
    if key in _summary_cache:
        return _summary_cache[key]

    import os
    api_key = os.getenv('ANTHROPIC_API_KEY', '')
    if not api_key:
        return None

    analysis = c3.DotSafetyBehavioral.getStateAnalysis(stateFips, year, 9, None)
    b = next((x for x in analysis.get('allBehaviors', []) if x['id'] == behaviorId), None)
    if not b:
        return None

    state = c3.StateRef.fetch({
        'filter': c3.Filter.eq('fips', stateFips), 'include': 'this', 'limit': 1,
    }).objs
    state_name = state[0].name if state else stateFips

    trend_str = b.get('trend', 'unknown')
    if b.get('trendPct') is not None:
        trend_str += f" ({b['trendPct']:+.1f}%)"

    cms      = c3.Countermeasure.getByBehavior(behaviorId, None)[:3]
    cms_str  = '; '.join(f"{getattr(c,'title','')} ({getattr(c,'evidenceLevel','')} evidence)" for c in cms)

    prompt = (
        f"State: {state_name}, Year: {year}\n"
        f"Behavior: {b['name']}\n"
        f"Fatal crashes: {b['crashes']:,} ({b.get('pctCrashes', 0):.1f}% of state total, "
        f"rank #{b['rank']} among 9 behaviors)\n"
        f"Trend vs prior year: {trend_str}\n"
        f"Available countermeasures: {cms_str}"
    )

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=150,
        system=(
            "You are a highway safety analyst writing for state DOT program managers. "
            "In exactly 2 sentences: (1) state why this behavior is a priority given the data, "
            "(2) name the single highest-impact countermeasure and why. "
            "Be specific to the numbers. No bullets. No hedging."
        ),
        messages=[{'role': 'user', 'content': prompt}],
    )
    summary = msg.content[0].text.strip()
    _summary_cache[key] = summary
    return summary


def _cm_to_dict(c):
    return {
        'id':                getattr(c, 'id', ''),
        'behaviorId':        getattr(c, 'behaviorId', ''),
        'title':             getattr(c, 'title', ''),
        'summary':           getattr(c, 'summary', ''),
        'evidenceLevel':     getattr(c, 'evidenceLevel', ''),
        'effectivenessNote': getattr(c, 'effectivenessNote', ''),
        'programType':       getattr(c, 'programType', ''),
        'chapter':           getattr(c, 'chapter', ''),
        'resourceUrl':       getattr(c, 'resourceUrl', ''),
    }
