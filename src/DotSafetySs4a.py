SS4A_MAP = {
    'alcohol': {
        'ss4aCategories': ['Safe People'],
        'programs':        ['402', '405d', 'HSIP'],
        'ss4aEligible':    True,
        'projectType':     'Impaired Driving Prevention',
        'strategy':        'DUI enforcement campaigns, sobriety checkpoints, ignition interlock programs',
    },
    'drugs': {
        'ss4aCategories': ['Safe People'],
        'programs':        ['402', '405d'],
        'ss4aEligible':    True,
        'projectType':     'Impaired Driving Prevention',
        'strategy':        'DUID enforcement training, drug recognition expert (DRE) expansion',
    },
    'speeding': {
        'ss4aCategories': ['Safe Speeds', 'Safe Roads'],
        'programs':        ['402', '405b', 'HSIP'],
        'ss4aEligible':    True,
        'projectType':     'Speed Management',
        'strategy':        'Speed management infrastructure, automated enforcement, targeted patrols',
    },
    'distracted_driving': {
        'ss4aCategories': ['Safe People'],
        'programs':        ['402', '405e'],
        'ss4aEligible':    False,
        'projectType':     'Distracted Driving Prevention',
        'strategy':        'Awareness campaigns, hands-free law enforcement, technology solutions',
    },
    'drowsy_driving': {
        'ss4aCategories': ['Safe People'],
        'programs':        ['402'],
        'ss4aEligible':    False,
        'projectType':     'Fatigued Driver Education',
        'strategy':        'Public awareness, commercial vehicle enforcement, rumble strip installation',
    },
    'seatbelt_nonuse': {
        'ss4aCategories': ['Safe People'],
        'programs':        ['402', '405b'],
        'ss4aEligible':    False,
        'projectType':     'Occupant Protection',
        'strategy':        'Click It or Ticket enforcement, primary seat belt law advocacy',
    },
    'pedestrian_fatality': {
        'ss4aCategories': ['Safe People', 'Safe Roads'],
        'programs':        ['402', '405h', 'HSIP', 'SS4A'],
        'ss4aEligible':    True,
        'projectType':     'Pedestrian Safety Infrastructure',
        'strategy':        'High-visibility crosswalks, HAWK signals, protected intersections, Vision Zero corridors',
    },
    'wrong_way': {
        'ss4aCategories': ['Safe Roads'],
        'programs':        ['HSIP', 'SS4A'],
        'ss4aEligible':    True,
        'projectType':     'Infrastructure Safety',
        'strategy':        'Wrong-way detection systems, enhanced signing, median barriers',
    },
    'hit_run': {
        'ss4aCategories': ['Safe People'],
        'programs':        ['402', 'HSIP'],
        'ss4aEligible':    False,
        'projectType':     'Enforcement & Technology',
        'strategy':        'Camera surveillance, targeted enforcement, public reporting systems',
    },
}


def getSs4aAlignment(cls, stateFips, year, month=None):
    state = c3.StateRef.fetch({
        'filter': c3.Filter.eq('fips', stateFips), 'include': 'this', 'limit': 1,
    }).objs
    state_name = state[0].name if state else stateFips
    state_abbr = state[0].abbr if state else ''

    analysis = c3.DotSafetyBehavioral.getStateAnalysis(stateFips, year, 9, month)
    bm_data  = c3.DotSafetyBenchmark.getStateBenchmark(stateFips, year, month)
    all_b    = analysis.get('allBehaviors', [])

    aligned = []
    for b in all_b:
        m = SS4A_MAP.get(b['id'])
        if not m:
            continue
        aligned.append({
            'id':             b['id'],
            'name':           b['name'],
            'crashes':        b['crashes'],
            'pctCrashes':     b['pctCrashes'],
            'rank':           b['rank'],
            'ss4aCategories': m['ss4aCategories'],
            'programs':       m['programs'],
            'ss4aEligible':   m['ss4aEligible'],
            'projectType':    m['projectType'],
            'strategy':       m['strategy'],
        })

    # Aggregate crash % by Safe System category
    cat_scores = {}
    for a in aligned:
        for cat in a['ss4aCategories']:
            cat_scores[cat] = round(cat_scores.get(cat, 0.0) + a['pctCrashes'], 1)

    return {
        'stateFips': stateFips,
        'stateName': state_name,
        'year':      year,
        'narrative': {
            'stateName':    state_name,
            'stateAbbr':    state_abbr,
            'year':         year,
            'totalFatals':  analysis.get('totalFatals', 0),
            'rate100k':     bm_data.get('ratePer100k'),
            'natRate100k':  bm_data.get('nationalAvg100k'),
            'pctVsNational': bm_data.get('vsNationalPct'),
        },
        'behaviors': aligned,
        'catScores': cat_scores,
    }
