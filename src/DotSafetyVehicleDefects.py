"""
UC5 — Vehicle Defect Surveillance service for C3 SDL.

Mirrors the Flask POC's services/vehicle_defects.py.  Uses C3 type
filters and aggregations against Vehicle, Recall, Investigation, Tsb,
SafetyRating, Complaint, and SgoIncident.  Make/Model joins use the
canonical vPIC fields populated on Vehicle by DotSafetyLoader.
"""


def _filter(field, value):
    return c3.Filter.eq(field, value)


def _filter_mmy(field_make, field_model, field_year, make, model, year):
    f = c3.Filter.eq(field_make, make).and_(c3.Filter.eq(field_model, model))
    if year is None:
        return f
    return f.and_(c3.Filter.eq(field_year, year))


def topDefectVehicles(cls, stateFips, year, limit=30):
    """Top vehicle MMMYs in fatal crashes for a state-year, with overlay
    of recall / investigation / TSB / complaint / NCAP / SGO counts."""
    # Step 1 — fetch FARS vehicle records for the state-year
    veh_filter = c3.Filter.eq('year', year)
    if stateFips and stateFips != '00':
        veh_filter = veh_filter.and_(c3.Filter.eq('stateFips', stateFips))
    veh_filter = veh_filter \
        .and_(c3.Filter.ne('vpicMake', '')) \
        .and_(c3.Filter.ne('vpicMake', 'UNKNOWN')) \
        .and_(c3.Filter.notNull('modelYear')) \
        .and_(c3.Filter.notNull('vpicModel'))

    vehicles = c3.Vehicle.fetch({
        'filter':  veh_filter,
        'include': 'stCase, vpicMake, vpicModel, modelYear',
        'limit':   -1,
    }).objs or []

    # Aggregate fatal-crash count per MMMY (each row is a vehicle in a crash)
    by_mmy = {}
    for v in vehicles:
        k = (v.vpicMake, v.vpicModel, v.modelYear)
        agg = by_mmy.setdefault(k, {
            'make': v.vpicMake, 'model': v.vpicModel, 'modelYear': v.modelYear,
            'crashes': set(), 'vehicleRecords': 0,
        })
        agg['crashes'].add(f'{v.stCase}-{year}')
        agg['vehicleRecords'] += 1

    rows = [{
        'make':           a['make'],
        'model':          a['model'],
        'modelYear':      a['modelYear'],
        'fatalCrashes':   len(a['crashes']),
        'vehicleRecords': a['vehicleRecords'],
    } for a in by_mmy.values() if len(a['crashes']) >= 2]
    rows.sort(key=lambda r: (-r['fatalCrashes'], -r['vehicleRecords']))
    rows = rows[:limit]

    # Step 2 — for each top MMMY, fetch overlay counts
    for r in rows:
        mk, md, my = r['make'], r['model'], r['modelYear']

        r['recalls'] = len(c3.Recall.fetch({
            'filter': _filter_mmy('make', 'model', 'modelYear', mk, md, my),
            'include': 'nhtsaId',
            'limit': -1,
        }).objs or [])

        r['investigations'] = len(set(
            i.nhtsaActionNumber for i in (c3.Investigation.fetch({
                'filter': _filter_mmy('make', 'model', 'modelYear', mk, md, my),
                'include': 'nhtsaActionNumber',
                'limit': -1,
            }).objs or [])
        ))

        r['tsbs'] = len(set(
            t.nhtsaId for t in (c3.Tsb.fetch({
                'filter': _filter_mmy('make', 'model', 'modelYear', mk, md, my),
                'include': 'nhtsaId',
                'limit': -1,
            }).objs or [])
        ))

        r['complaints'] = len(c3.Complaint.fetch({
            'filter': _filter_mmy('make', 'model', 'modelYear', mk, md, my),
            'include': 'cmplid',
            'limit': -1,
        }).objs or [])

        ratings = c3.SafetyRating.fetch({
            'filter': _filter_mmy('make', 'model', 'modelYear', mk, md, my),
            'include': 'overallStars',
            'limit': -1,
        }).objs or []
        r['ncapOverall'] = max(
            (rt.overallStars for rt in ratings if rt.overallStars is not None),
            default=None,
        )

        r['sgoIncidents'] = len(c3.SgoIncident.fetch({
            'filter': _filter_mmy('make', 'model', 'modelYear', mk, md, my),
            'include': 'reportId',
            'limit': -1,
        }).objs or [])

    return {
        'stateFips': stateFips,
        'year':      year,
        'rows':      rows,
        'source':    'NHTSA FARS Vehicle joined to NHTSA ODI Recalls, Investigations, '
                     'TSBs, Complaints, NCAP Ratings, and SGO incident reports via '
                     'FARS-supplied vPIC canonical Make/Model/Model Year.',
    }


def vehicleProfile(cls, make, model, modelYear):
    mk, md, my = make.upper(), model.upper(), int(modelYear)

    fatal_count = len(set(
        v.stCase + '-' + str(v.year)
        for v in (c3.Vehicle.fetch({
            'filter': _filter_mmy('vpicMake', 'vpicModel', 'modelYear', mk, md, my),
            'include': 'stCase, year',
            'limit': -1,
        }).objs or [])
    ))

    ratings = c3.SafetyRating.fetch({
        'filter':  _filter_mmy('make', 'model', 'modelYear', mk, md, my),
        'limit':   -1,
        'order':   'descending(productionRelease)',
    }).objs or []

    investigations = c3.Investigation.fetch({
        'filter':  _filter_mmy('make', 'model', 'modelYear', mk, md, my),
        'limit':   50,
        'order':   'descending(openDate)',
    }).objs or []

    recalls = c3.Recall.fetch({
        'filter':  _filter_mmy('make', 'model', 'modelYear', mk, md, my),
        'limit':   25,
        'order':   'descending(nhtsaId)',
    }).objs or []

    tsbs = c3.Tsb.fetch({
        'filter':  _filter_mmy('make', 'model', 'modelYear', mk, md, my),
        'limit':   25,
        'order':   'descending(commDate)',
    }).objs or []

    complaint_count = len(c3.Complaint.fetch({
        'filter':  _filter_mmy('make', 'model', 'modelYear', mk, md, my),
        'include': 'cmplid',
        'limit':   -1,
    }).objs or [])

    complaints = c3.Complaint.fetch({
        'filter':  _filter_mmy('make', 'model', 'modelYear', mk, md, my),
        'limit':   20,
        'order':   'descending(recvDate)',
    }).objs or []

    sgo = c3.SgoIncident.fetch({
        'filter':  _filter_mmy('make', 'model', 'modelYear', mk, md, my),
        'limit':   25,
        'order':   'descending(reportSubmission)',
    }).objs or []

    return {
        'make':           mk,
        'model':          md,
        'modelYear':      my,
        'fatalCrashes':   fatal_count,
        'ratings':        [rt.toJson() for rt in ratings],
        'investigations': [i.toJson()  for i in investigations],
        'recalls':        [r.toJson()  for r in recalls],
        'tsbs':           [t.toJson()  for t in tsbs],
        'complaintCount': complaint_count,
        'complaints':     [c.toJson()  for c in complaints],
        'sgo':            [s.toJson()  for s in sgo],
    }


def searchComplaints(cls, query, make=None, model=None, modelYear=None, limit=20):
    """Full-text search over Complaint.narrative.

    Resolution order at runtime:
      1. C3 platform full-text index (preferred) — uses Complaint.narrative
         marked indexed in production deployment configuration.
      2. Per-term LIKE filter chain (fallback) — works without a configured
         FTS index; tokenizes the query into AND-chained substring filters
         so multi-word queries don't require literal phrase match.

    For production C3 deployments, configure FullTextIndex on Complaint
    and/or wire a vector backend; the call below resolves to the platform's
    FTS implementation when available."""
    if not query or not query.strip():
        return {'results': []}
    q = query.strip()

    # Build structured filters first
    f = None
    def _and(g):
        nonlocal f
        f = g if f is None else f.and_(g)

    # Try platform FTS first.  c3.Type.findText() / matchPhrase() exist on
    # types with a configured FullTextIndex.  Fall back gracefully.
    try:
        if hasattr(c3.Complaint, 'matchPhrase'):
            f = c3.Complaint.matchPhrase('narrative', q)
        else:
            raise AttributeError
    except (AttributeError, Exception):
        # Fallback: per-term LIKE chain.  Whitespace-tokenize and AND.
        for term in [t for t in q.split() if t.strip()]:
            _and(c3.Filter.like('narrative', '%' + term + '%'))

    if make:
        _and(c3.Filter.eq('make', make.upper()))
    if model:
        _and(c3.Filter.eq('model', model.upper()))
    if modelYear:
        _and(c3.Filter.eq('modelYear', int(modelYear)))

    results = c3.Complaint.fetch({
        'filter': f,
        'limit':  int(limit),
        'order':  'descending(recvDate)',
    }).objs or []

    return {
        'query':   q,
        'results': [c.toJson() for c in results],
    }


def sgoSummary(cls, level=None):
    f = None
    if level in ('ADS', 'ADAS', 'OTHER'):
        f = c3.Filter.eq('automationLevel', level)

    incidents = c3.SgoIncident.fetch({
        'filter': f,
        'limit':  -1,
    }).objs or []

    totals = {'total': len(incidents), 'ads': 0, 'adas': 0, 'other': 0}
    by_entity = {}
    by_make   = {}

    for i in incidents:
        lvl = (i.automationLevel or '').upper()
        if   lvl == 'ADS':   totals['ads']   += 1
        elif lvl == 'ADAS':  totals['adas']  += 1
        elif lvl == 'OTHER': totals['other'] += 1
        ent = i.reportingEntity or ''
        by_entity[ent] = by_entity.get(ent, 0) + 1
        mk = i.make or ''
        by_make[mk] = by_make.get(mk, 0) + 1

    top_entities = sorted(by_entity.items(), key=lambda kv: -kv[1])[:10]
    top_makes    = sorted(by_make.items(),   key=lambda kv: -kv[1])[:10]

    return {
        'level':        level,
        'totals':       totals,
        'topEntities':  [{'reportingEntity': k, 'n': v} for k, v in top_entities],
        'topMakes':     [{'make': k, 'n': v}            for k, v in top_makes],
        'note':         'SGO data covers automated and assisted-driving incidents '
                        'reported under NHTSA Standing General Order 2021-01. Per '
                        'UC5 design, SGO is presented as a siloed subview and is '
                        'not blended with FARS fatal-crash analytics.',
    }
