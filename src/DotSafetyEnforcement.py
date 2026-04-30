import math

DAYS_SHORT = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

BEHAVIORS = {
    'alcohol':             'alcFlag',
    'drugs':               'drugFlag',
    'speeding':            'speedFlag',
    'distracted_driving':  'distractFlag',
    'drowsy_driving':      'drowsyFlag',
    'seatbelt_nonuse':     'beltFlag',
    'pedestrian_fatality': 'pedFlag',
    'wrong_way':           'wrongwayFlag',
    'hit_run':             'hitrunFlag',
}

BEHAVIOR_NAMES = {
    'alcohol':             'Alcohol-Impaired Driving',
    'drugs':               'Drug-Impaired Driving',
    'speeding':            'Speeding-Related',
    'distracted_driving':  'Distracted Driving',
    'drowsy_driving':      'Drowsy/Fatigued Driving',
    'seatbelt_nonuse':     'Seatbelt Non-Use',
    'pedestrian_fatality': 'Pedestrian Fatality',
    'wrong_way':           'Wrong-Way Driving',
    'hit_run':             'Hit-and-Run',
}


def _fmt_hour(h):
    if h == 0:   return '12am'
    if h < 12:   return f'{h}am'
    if h == 12:  return '12pm'
    return f'{h - 12}pm'


def _add_significance(heatmap):
    total = sum(cell['crashes'] for row in heatmap for cell in row)
    if total < 30:
        for row in heatmap:
            for cell in row:
                cell['sig'] = False
                cell['z']   = 0.0
        return
    expected = total / 168.0
    for row in heatmap:
        for cell in row:
            c = cell['crashes']
            z = (c - expected) / math.sqrt(expected)
            cell['z']   = round(z, 2)
            cell['sig'] = z >= 1.96


def _best_window(by_hour):
    best_count, best_start = 0, 0
    for start in range(24):
        count = sum(by_hour[(start + i) % 24]['crashes'] for i in range(3))
        if count > best_count:
            best_count, best_start = count, start
    return {
        'startHour':  best_start,
        'endHour':    (best_start + 2) % 24,
        'startLabel': _fmt_hour(best_start),
        'endLabel':   _fmt_hour((best_start + 2) % 24),
        'crashes':    best_count,
    }


def _build_filter(stateFips, year, behaviorId=None, month=None, city=None):
    f = c3.Filter.eq('stateFips', stateFips).and_(c3.Filter.eq('year', year))
    if behaviorId and behaviorId in BEHAVIORS:
        f = f.and_(c3.Filter.eq(BEHAVIORS[behaviorId], True))
    if month:
        f = f.and_(c3.Filter.eq('month', month))
    if city:
        f = f.and_(c3.Filter.eq('cityName', city))
    return f


def getEnforcementWindows(cls, stateFips, year, behaviorId=None, month=None, city=None):
    crashes = c3.FatalCrash.fetch({
        'filter':  _build_filter(stateFips, year, behaviorId, month, city),
        'include': 'this',
        'limit':   -1,
    }).objs or []

    total_crashes = len(crashes)
    total_fatals  = sum(getattr(c, 'fatals', 0) or 0 for c in crashes)

    by_hour = [{'hour': h, 'label': _fmt_hour(h), 'crashes': 0, 'fatals': 0} for h in range(24)]
    by_dow  = [{'dow': i + 1, 'label': DAYS_SHORT[i], 'crashes': 0, 'fatals': 0} for i in range(7)]
    heatmap = [[{'crashes': 0, 'fatals': 0} for _ in range(24)] for _ in range(7)]

    for c in crashes:
        h   = getattr(c, 'hour', -1)
        dow = getattr(c, 'dayWeek', 0)
        f   = getattr(c, 'fatals', 0) or 0
        if 0 <= h <= 23:
            by_hour[h]['crashes'] += 1
            by_hour[h]['fatals']  += f
        if 1 <= dow <= 7:
            by_dow[dow - 1]['crashes'] += 1
            by_dow[dow - 1]['fatals']  += f
        if 0 <= h <= 23 and 1 <= dow <= 7:
            heatmap[dow - 1][h]['crashes'] += 1
            heatmap[dow - 1][h]['fatals']  += f

    _add_significance(heatmap)

    sig_windows = []
    for di, row in enumerate(heatmap):
        for h, cell in enumerate(row):
            if cell.get('sig'):
                sig_windows.append({
                    'dow': di + 1, 'dowLabel': DAYS_SHORT[di],
                    'hour': h, 'hourLabel': _fmt_hour(h),
                    'crashes': cell['crashes'], 'fatals': cell['fatals'],
                    'z': cell['z'],
                })
    sig_windows.sort(key=lambda x: x['z'], reverse=True)

    known = sum(h['crashes'] for h in by_hour)
    night = sum(h['crashes'] for h in by_hour if h['hour'] >= 21 or h['hour'] <= 2)
    night_pct = round(night / known * 100, 1) if known else 0

    return {
        'stateFips':    stateFips,
        'year':         year,
        'behaviorId':   behaviorId,
        'behaviorName': BEHAVIOR_NAMES.get(behaviorId, 'All Behaviors') if behaviorId else 'All Behaviors',
        'cityFilter':   city,
        'totalCrashes': total_crashes,
        'totalFatals':  total_fatals,
        'byHour':       by_hour,
        'byDow':        by_dow,
        'heatmap':      heatmap,
        'peakHours':    sorted(by_hour, key=lambda x: x['crashes'], reverse=True)[:3],
        'peakDays':     sorted(by_dow,  key=lambda x: x['crashes'], reverse=True)[:3],
        'bestWindow':   _best_window(by_hour),
        'nightPct':     night_pct,
        'sigWindows':   sig_windows,
    }


def getLocationBreakdown(cls, stateFips, year, behaviorId=None, month=None,
                         hourFrom=None, hourTo=None, dow=None, topN=15):
    f = c3.Filter.eq('stateFips', stateFips).and_(c3.Filter.eq('year', year))
    if behaviorId and behaviorId in BEHAVIORS:
        f = f.and_(c3.Filter.eq(BEHAVIORS[behaviorId], True))
    if month is not None:
        f = f.and_(c3.Filter.eq('month', month))
    if dow is not None:
        f = f.and_(c3.Filter.eq('dayWeek', dow))

    crashes = c3.FatalCrash.fetch({'filter': f, 'include': 'this', 'limit': -1}).objs or []

    # Hour filter applied in Python (range can wrap midnight)
    if hourFrom is not None and hourTo is not None:
        if hourFrom <= hourTo:
            crashes = [c for c in crashes if hourFrom <= (getattr(c, 'hour', -1) or -1) <= hourTo]
        else:
            crashes = [c for c in crashes if (getattr(c, 'hour', -1) or -1) >= hourFrom
                       or (getattr(c, 'hour', -1) or -1) <= hourTo]

    county_map = {}
    city_map   = {}
    skip = {'', 'NOT REPORTED', 'NOT APPLICABLE'}

    for c in crashes:
        cfips = getattr(c, 'countyFips', '') or ''
        cname = getattr(c, 'countyName', '') or ''
        f_val = getattr(c, 'fatals', 0) or 0

        if cfips and cfips != '000' and cname:
            key = (cfips, cname)
            if key not in county_map:
                county_map[key] = {'name': cname, 'fips': cfips, 'crashes': 0, 'fatals': 0}
            county_map[key]['crashes'] += 1
            county_map[key]['fatals']  += f_val

        city = (getattr(c, 'cityName', '') or '').strip()
        code = getattr(c, 'cityCode', '0') or '0'
        if city.upper() not in skip and code != '0':
            if city not in city_map:
                city_map[city] = {'name': city, 'crashes': 0, 'fatals': 0}
            city_map[city]['crashes'] += 1
            city_map[city]['fatals']  += f_val

    counties = sorted(county_map.values(), key=lambda x: (x['fatals'], x['crashes']), reverse=True)[:topN]
    cities   = sorted(city_map.values(),   key=lambda x: (x['fatals'], x['crashes']), reverse=True)[:topN]

    return {
        'stateFips':    stateFips,
        'year':         year,
        'behaviorId':   behaviorId,
        'behaviorName': BEHAVIOR_NAMES.get(behaviorId, 'All Behaviors') if behaviorId else 'All Behaviors',
        'filters': {'month': month, 'hourFrom': hourFrom, 'hourTo': hourTo, 'dow': dow},
        'totalCrashes': len(crashes),
        'totalFatals':  sum(getattr(c, 'fatals', 0) or 0 for c in crashes),
        'counties':     counties,
        'cities':       cities,
    }
