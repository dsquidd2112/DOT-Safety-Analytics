def _get_state_stats(stateFips, year, month=None):
    f = c3.Filter.eq('stateFips', stateFips).and_(c3.Filter.eq('year', year))
    if month:
        f = f.and_(c3.Filter.eq('month', month))
    crashes = c3.FatalCrash.fetch({'filter': f, 'include': 'this', 'limit': -1}).objs or []
    fatals  = sum(getattr(c, 'fatals', 0) or 0 for c in crashes)

    pop_rec = c3.PopulationEstimate.fetch({
        'filter': c3.Filter.eq('stateFips', stateFips).and_(c3.Filter.eq('year', year)),
        'include': 'this', 'limit': 1,
    }).objs
    pop = pop_rec[0].population if pop_rec else None

    vmt_rec = c3.VMTEstimate.fetch({
        'filter': c3.Filter.eq('stateFips', stateFips).and_(c3.Filter.eq('year', year)),
        'include': 'this', 'limit': 1,
    }).objs
    vmt = vmt_rec[0].vmtMillions if vmt_rec else None

    return {'fatals': fatals, 'population': pop, 'vmtMillions': vmt}


def getAllBenchmarks(cls, year, month=None):
    states = c3.StateRef.fetch({'include': 'this', 'limit': -1}).objs or []

    results = []
    for s in states:
        fips = s.fips
        stats = _get_state_stats(fips, year, month)
        fatals = stats['fatals']
        if fatals == 0:
            continue
        pop = stats['population']
        vmt = stats['vmtMillions']
        results.append({
            'stateFips':   fips,
            'name':        s.name,
            'abbr':        s.abbr,
            'year':        year,
            'fatals':      fatals,
            'population':  pop,
            'vmtMillions': vmt,
            'ratePer100k': round(fatals / pop * 100_000, 2) if pop else None,
            'ratePerVmt':  round(fatals / vmt * 100,     2) if vmt else None,
        })

    total_fatals = sum(r['fatals']       for r in results)
    total_pop    = sum(r['population']   for r in results if r['population'])
    total_vmt    = sum(r['vmtMillions']  for r in results if r['vmtMillions'])
    nat_100k = round(total_fatals / total_pop * 100_000, 2) if total_pop else None
    nat_vmt  = round(total_fatals / total_vmt * 100,     2) if total_vmt else None

    sortable = [r for r in results if r['ratePer100k'] is not None]
    sortable.sort(key=lambda x: x['ratePer100k'], reverse=True)
    for i, r in enumerate(sortable):
        r['rank100k']       = i + 1
        r['vsNational100k'] = round(r['ratePer100k'] - nat_100k, 2)                        if nat_100k else None
        r['vsNationalPct']  = round((r['ratePer100k'] - nat_100k) / nat_100k * 100, 1)     if nat_100k else None

    return {
        'year':     year,
        'national': {'fatals': total_fatals, 'ratePer100k': nat_100k, 'ratePerVmt': nat_vmt},
        'states':   results,
        'nStates':  len(results),
    }


def getStateBenchmark(cls, stateFips, year, month=None):
    stats  = _get_state_stats(stateFips, year, month)
    state  = c3.StateRef.fetch({
        'filter': c3.Filter.eq('fips', stateFips), 'include': 'this', 'limit': 1,
    }).objs
    name = state[0].name if state else stateFips
    abbr = state[0].abbr if state else ''

    fatals = stats['fatals']
    pop    = stats['population']
    vmt    = stats['vmtMillions']
    r100k  = round(fatals / pop * 100_000, 2) if pop else None
    rvmt   = round(fatals / vmt * 100,     2) if vmt else None

    # National average
    all_bm   = c3.DotSafetyBenchmark.getAllBenchmarks(year, month)
    nat_100k = all_bm['national']['ratePer100k']

    return {
        'stateFips':      stateFips,
        'name':           name,
        'abbr':           abbr,
        'year':           year,
        'fatals':         fatals,
        'population':     pop,
        'vmtMillions':    vmt,
        'ratePer100k':    r100k,
        'ratePerVmt':     rvmt,
        'nationalAvg100k': nat_100k,
        'vsNational100k': round(r100k - nat_100k, 2)                    if r100k and nat_100k else None,
        'vsNationalPct':  round((r100k - nat_100k) / nat_100k * 100, 1) if r100k and nat_100k else None,
    }


def getPeerComparison(cls, stateFipsList, year, month=None):
    bm  = c3.DotSafetyBenchmark.getAllBenchmarks(year, month)
    nat = bm['national']

    lookup = {s['stateFips']: s for s in bm['states']}
    peers  = []
    for fips in stateFipsList:
        s = lookup.get(fips)
        if not s:
            continue
        r100k = s.get('ratePer100k')
        peers.append({
            **s,
            'vsNational100k': round(r100k - nat['ratePer100k'], 2)                        if r100k and nat['ratePer100k'] else None,
            'vsNationalPct':  round((r100k - nat['ratePer100k']) / nat['ratePer100k'] * 100, 1) if r100k and nat['ratePer100k'] else None,
        })

    if len(peers) >= 2:
        rates = [p['ratePer100k'] for p in peers if p['ratePer100k'] is not None]
        best  = min(peers, key=lambda p: p['ratePer100k'] or float('inf'))
        worst = max(peers, key=lambda p: p['ratePer100k'] or 0)
        spread = round(max(rates) - min(rates), 2) if len(rates) >= 2 else None
    else:
        best = worst = peers[0] if peers else None
        spread = None

    return {
        'year':     year,
        'national': nat,
        'peers':    peers,
        'summary': {
            'bestRateState':  best['abbr']  if best  else None,
            'worstRateState': worst['abbr'] if worst else None,
            'rateSpread':     spread,
        },
    }
