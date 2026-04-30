BEHAVIORS = {
    'alcohol':             ('alcFlag',        'Alcohol-Impaired Driving'),
    'drugs':               ('drugFlag',       'Drug-Impaired Driving'),
    'speeding':            ('speedFlag',      'Speeding-Related'),
    'distracted_driving':  ('distractFlag',   'Distracted Driving'),
    'drowsy_driving':      ('drowsyFlag',     'Drowsy/Fatigued Driving'),
    'seatbelt_nonuse':     ('beltFlag',       'Seatbelt Non-Use'),
    'pedestrian_fatality': ('pedFlag',        'Pedestrian Fatality'),
    'wrong_way':           ('wrongwayFlag',   'Wrong-Way Driving'),
    'hit_run':             ('hitrunFlag',     'Hit-and-Run'),
}

AGE_BINS = [
    ('Under 16',  0,  15),
    ('16-20',    16,  20),
    ('21-24',    21,  24),
    ('25-34',    25,  34),
    ('35-44',    35,  44),
    ('45-54',    45,  54),
    ('55-64',    55,  64),
    ('65+',      65, 120),
]

YEARS = [2021, 2022, 2023, 2024]


def _fetch_crashes(stateFips, year, month=None):
    f = c3.Filter.eq('stateFips', stateFips).and_(c3.Filter.eq('year', year))
    if month:
        f = f.and_(c3.Filter.eq('month', month))
    return c3.FatalCrash.fetch({'filter': f, 'include': 'this', 'limit': -1}).objs or []


def getStateAnalysis(cls, stateFips, year, topN=3, month=None):
    crashes = _fetch_crashes(stateFips, year, month)
    if not crashes:
        return {'behaviors': [], 'allBehaviors': [], 'totalCrashes': 0,
                'totalFatals': 0, 'stateFips': stateFips, 'year': year}

    total_crashes = len(crashes)
    total_fatals  = sum(getattr(c, 'fatals', 0) or 0 for c in crashes)

    prev_crashes = _fetch_crashes(stateFips, year - 1, month)
    prev_total   = len(prev_crashes)

    ranked = []
    for bid, (field, name) in BEHAVIORS.items():
        count  = sum(1 for c in crashes if getattr(c, field, False))
        fatals = sum(getattr(c, 'fatals', 0) or 0 for c in crashes if getattr(c, field, False))

        trend, trend_pct = 'no_prior_data', None
        if prev_total > 0:
            prior = sum(1 for c in prev_crashes if getattr(c, field, False))
            if prior > 0:
                pct       = (count - prior) / prior * 100
                trend_pct = round(pct, 1)
                trend     = 'increasing' if pct > 2 else 'decreasing' if pct < -2 else 'stable'

        ranked.append({
            'id':         bid,
            'name':       name,
            'crashes':    count,
            'fatals':     fatals,
            'pctCrashes': round(count  / total_crashes * 100, 1) if total_crashes else 0,
            'pctFatals':  round(fatals / total_fatals  * 100, 1) if total_fatals  else 0,
            'trend':      trend,
            'trendPct':   trend_pct,
        })

    ranked.sort(key=lambda x: x['crashes'], reverse=True)
    for i, b in enumerate(ranked):
        b['rank'] = i + 1

    top = ranked[:topN]
    for b in top:
        b['counties']     = c3.DotSafetyBehavioral.getCountyHotspots(stateFips, year, b['id'], 10, month)
        b['cities']       = c3.DotSafetyBehavioral.getCityHotspots(stateFips, year, b['id'], 15, month)
        b['demographics'] = c3.DotSafetyBehavioral.getDemographics(stateFips, year, b['id'], month)

    return {
        'stateFips':    stateFips,
        'year':         year,
        'totalCrashes': total_crashes,
        'totalFatals':  total_fatals,
        'behaviors':    top,
        'allBehaviors': ranked,
    }


def getCountyHotspots(cls, stateFips, year, behaviorId, topN=10, month=None):
    if behaviorId not in BEHAVIORS:
        return []
    field = BEHAVIORS[behaviorId][0]
    crashes = _fetch_crashes(stateFips, year, month)

    county_map = {}
    for c in crashes:
        if not getattr(c, field, False):
            continue
        key  = (getattr(c, 'countyFips', '') or '', getattr(c, 'countyName', '') or '')
        fips = key[0]
        if not fips or fips == '000':
            continue
        if key not in county_map:
            county_map[key] = {'name': key[1], 'fips': fips, 'crashes': 0, 'fatals': 0}
        county_map[key]['crashes'] += 1
        county_map[key]['fatals']  += getattr(c, 'fatals', 0) or 0

    counties = sorted(county_map.values(), key=lambda x: x['fatals'], reverse=True)
    return counties[:topN]


def getCityHotspots(cls, stateFips, year, behaviorId, topN=15, month=None):
    if behaviorId not in BEHAVIORS:
        return []
    field   = BEHAVIORS[behaviorId][0]
    crashes = _fetch_crashes(stateFips, year, month)

    city_map = {}
    skip = {'', 'NOT REPORTED', 'NOT APPLICABLE'}
    for c in crashes:
        if not getattr(c, field, False):
            continue
        city = (getattr(c, 'cityName', '') or '').strip()
        code = getattr(c, 'cityCode', '0') or '0'
        if city.upper() in skip or code == '0':
            continue
        if city not in city_map:
            city_map[city] = {'name': city, 'crashes': 0, 'fatals': 0}
        city_map[city]['crashes'] += 1
        city_map[city]['fatals']  += getattr(c, 'fatals', 0) or 0

    cities = sorted(city_map.values(), key=lambda x: (x['fatals'], x['crashes']), reverse=True)
    return cities[:topN]


def getDemographics(cls, stateFips, year, behaviorId, month=None):
    if behaviorId not in BEHAVIORS:
        return {'age': [], 'sex': [], 'personType': []}
    field = BEHAVIORS[behaviorId][0]

    crash_filter = c3.Filter.eq('stateFips', stateFips).and_(
        c3.Filter.eq('year', year)
    ).and_(c3.Filter.eq(field, True))
    if month:
        crash_filter = crash_filter.and_(c3.Filter.eq('month', month))

    flagged = c3.FatalCrash.fetch({'filter': crash_filter, 'include': 'this', 'limit': -1}).objs or []
    if not flagged:
        return {'age': [], 'sex': [], 'personType': []}

    st_cases = list({getattr(c, 'stCase', '') for c in flagged if getattr(c, 'stCase', '')})

    persons = c3.CrashPerson.fetch({
        'filter': c3.Filter.eq('stateFips', stateFips).and_(
            c3.Filter.eq('year', year)).and_(
            c3.Filter.eq('injSev', 4)).and_(
            c3.Filter.intersects('stCase', st_cases)),
        'include': 'this',
        'limit': -1,
    }).objs or []

    total = len(persons)
    if total == 0:
        return {'age': [], 'sex': [], 'personType': []}

    age_counts   = {label: 0 for label, _, _ in AGE_BINS}
    sex_counts   = {}
    ptype_counts = {}

    for p in persons:
        age = getattr(p, 'age', None) or 998
        if age < 998:
            for label, lo, hi in AGE_BINS:
                if lo <= age <= hi:
                    age_counts[label] += 1
                    break
        sex   = getattr(p, 'sex', 'unknown')   or 'unknown'
        ptype = getattr(p, 'personType', 'other') or 'other'
        sex_counts[sex]    = sex_counts.get(sex, 0) + 1
        ptype_counts[ptype] = ptype_counts.get(ptype, 0) + 1

    def to_list(d):
        return sorted(
            [{'segment': k, 'count': v, 'pct': round(v / total * 100, 1)} for k, v in d.items()],
            key=lambda x: x['count'], reverse=True,
        )

    return {
        'age':        [x for x in to_list(age_counts) if x['count'] > 0],
        'sex':        [x for x in to_list(sex_counts) if x['segment'] != 'unknown'],
        'personType': to_list(ptype_counts),
    }


def getYoyTrend(cls, stateFips, behaviorId):
    if behaviorId not in BEHAVIORS:
        return {'stateFips': stateFips, 'behaviorId': behaviorId, 'trend': []}
    field, name = BEHAVIORS[behaviorId]

    trend = []
    for yr in YEARS:
        crashes = _fetch_crashes(stateFips, yr)
        count   = sum(1 for c in crashes if getattr(c, field, False))
        fatals  = sum(getattr(c, 'fatals', 0) or 0 for c in crashes if getattr(c, field, False))
        trend.append({'year': yr, 'crashes': count, 'fatals': fatals})

    direction, pct = 'insufficient_data', None
    if len(trend) >= 2:
        first, last = trend[0]['crashes'], trend[-1]['crashes']
        if first > 0:
            pct       = round((last - first) / first * 100, 1)
            direction = 'increasing' if pct > 2 else 'decreasing' if pct < -2 else 'stable'

    return {
        'stateFips':        stateFips,
        'behaviorId':       behaviorId,
        'behaviorName':     name,
        'trend':            trend,
        'overallDirection': direction,
        'overallPctChange': pct,
    }
