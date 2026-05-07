"""
ETL loader — reads FARS CSVs, joins accident + acc_aux + person, creates
FatalCrash and CrashPerson records in C3.  Replaces the Flask db/load_fars.py.
"""
import csv
import os

LIGHTING_MAP = {
    '1': 'daylight', '2': 'dark_lighted', '3': 'dark_unlighted',
    '4': 'dawn_dusk', '5': 'dawn_dusk',
}
WEATHER_MAP = {
    '1': 'clear', '2': 'rain', '3': 'sleet', '4': 'snow',
    '5': 'fog', '6': 'rain', '7': 'severe_wind', '10': 'cloudy',
    '11': 'blowing_sand', '12': 'freezing_rain',
}
STATE_ABBR = {
    '01':'AL','02':'AK','04':'AZ','05':'AR','06':'CA','08':'CO','09':'CT','10':'DE',
    '11':'DC','12':'FL','13':'GA','15':'HI','16':'ID','17':'IL','18':'IN','19':'IA',
    '20':'KS','21':'KY','22':'LA','23':'ME','24':'MD','25':'MA','26':'MI','27':'MN',
    '28':'MS','29':'MO','30':'MT','31':'NE','32':'NV','33':'NH','34':'NJ','35':'NM',
    '36':'NY','37':'NC','38':'ND','39':'OH','40':'OK','41':'OR','42':'PA','44':'RI',
    '45':'SC','46':'SD','47':'TN','48':'TX','49':'UT','50':'VT','51':'VA','53':'WA',
    '54':'WV','55':'WI','56':'WY','72':'PR',
}


def _pad2(v):
    try:
        return str(int(v)).zfill(2)
    except Exception:
        return '00'


def _int(v, default=None):
    try:
        return int(v)
    except Exception:
        return default


def _float(v, default=None):
    try:
        f = float(v)
        return f if abs(f) < 1e6 else default
    except Exception:
        return default


def loadFars(cls, year, dataPath):
    crash_csv  = os.path.join(dataPath, f'FARS{year}NationalCSV', 'accident.csv')
    aux_csv    = os.path.join(dataPath, f'FARS{year}NationalAuxiliaryCSV', 'ACC_AUX.CSV')
    person_csv = os.path.join(dataPath, f'FARS{year}NationalCSV', 'person.csv')

    # --- Read acc_aux flags keyed by ST_CASE ---
    flags = {}
    with open(aux_csv, newline='', encoding='latin-1') as f:
        for row in csv.DictReader(f):
            def flag(col):
                return row.get(col, '0').strip() == '1'
            flags[row['ST_CASE'].strip()] = {
                'alcFlag':      flag('A_POSBAC'),
                'speedFlag':    flag('A_SPCRA'),
                'distractFlag': flag('A_DIST'),
                'drowsyFlag':   flag('A_DROWSY'),
                'pedFlag':      flag('A_PED_F'),
                'wrongwayFlag': flag('A_WRONGWAY'),
                'hitrunFlag':   flag('A_HR'),
            }

    # --- Read persons for drug + belt flags keyed by (ST_CASE) ---
    drug_cases = set()
    belt_cases = set()
    with open(person_csv, newline='', encoding='latin-1') as f:
        for row in csv.DictReader(f):
            sc = row.get('ST_CASE', '').strip()
            if row.get('DRUGS', '0').strip() == '1':
                drug_cases.add(sc)
            rest = row.get('REST_USE', '')
            try:
                if int(rest) in (1, 2, 3, 4, 5, 6):
                    pass
                else:
                    belt_cases.add(sc)
            except Exception:
                belt_cases.add(sc)

    # --- Build crash records ---
    crashes  = []
    persons  = []

    with open(crash_csv, newline='', encoding='latin-1') as f:
        for row in csv.DictReader(f):
            sc          = row.get('ST_CASE', '').strip()
            state       = _pad2(row.get('STATE', '0'))
            county      = row.get('COUNTY', '0').zfill(3) if row.get('COUNTY') else '000'
            raw_cname   = row.get('COUNTYNAME', '').strip()
            county_name = raw_cname.split('(')[0].strip() if raw_cname else ''
            city        = row.get('CITY', '0').strip()
            raw_cty     = row.get('CITYNAME', '').strip().upper()
            city_name   = row.get('CITYNAME', '').strip() if raw_cty not in ('NOT APPLICABLE', 'NOT REPORTED', '') else ''
            month       = _int(row.get('MONTH'))
            dow    = _int(row.get('DAY_WEEK'))
            hour   = _int(row.get('HOUR'))
            if hour is not None and hour > 23:
                hour = None
            fatals = _int(row.get('FATALS'), 0)
            lat    = _float(row.get('LATITUDE'))
            lon    = _float(row.get('LONGITUD'))
            if lat is not None and (lat < -90 or lat > 90):
                lat = None
            if lon is not None and (lon < -180 or lon > 180):
                lon = None
            lgt  = LIGHTING_MAP.get(row.get('LGT_COND', '').strip(), '')
            wthr = WEATHER_MAP.get(row.get('WEATHER', '').strip(), '')
            bf   = flags.get(sc, {})

            crashes.append({
                'id':           f'{sc}-{year}',
                'stCase':       sc,
                'stateFips':    state,
                'year':         year,
                'countyFips':   county,
                'countyName':   county_name,
                'cityCode':     city,
                'cityName':     city_name,
                'month':        month,
                'dayWeek':      dow,
                'hour':         hour,
                'fatals':       fatals,
                'latitude':     lat,
                'longitude':    lon,
                'lighting':     lgt,
                'weather':      wthr,
                'alcFlag':      bf.get('alcFlag', False),
                'drugFlag':     sc in drug_cases,
                'speedFlag':    bf.get('speedFlag', False),
                'distractFlag': bf.get('distractFlag', False),
                'drowsyFlag':   bf.get('drowsyFlag', False),
                'beltFlag':     sc in belt_cases,
                'pedFlag':      bf.get('pedFlag', False),
                'wrongwayFlag': bf.get('wrongwayFlag', False),
                'hitrunFlag':   bf.get('hitrunFlag', False),
            })

    # Batch upsert FatalCrash
    BATCH = 500
    for i in range(0, len(crashes), BATCH):
        c3.FatalCrash.upsertBatch({'objs': crashes[i:i + BATCH]})

    # --- Person records ---
    with open(person_csv, newline='', encoding='latin-1') as f:
        for row in csv.DictReader(f):
            sc      = row.get('ST_CASE', '').strip()
            veh_no  = _int(row.get('VEH_NO'), 0)
            per_no  = _int(row.get('PER_NO'), 0)
            state   = _pad2(row.get('STATE', '0'))
            age     = _int(row.get('AGE'))
            if age is not None and (age > 120 or age < 0):
                age = None
            sex_code = _int(row.get('SEX'), 0)
            sex  = 'male' if sex_code == 1 else 'female' if sex_code == 2 else 'unknown'
            inj  = _int(row.get('INJ_SEV'))
            rest = _int(row.get('REST_USE'), 0)
            drink = row.get('DRINKING', '0').strip() == '1'
            drug  = row.get('DRUGS', '0').strip() == '1'
            ptyp  = _int(row.get('PER_TYP'), 0)
            ptype_map = {1:'driver',2:'passenger',5:'pedestrian',6:'cyclist'}
            persons.append({
                'id':           f'{sc}-{veh_no}-{per_no}-{year}',
                'stCase':       sc,
                'vehNo':        veh_no,
                'perNo':        per_no,
                'stateFips':    state,
                'year':         year,
                'age':          age,
                'sex':          sex,
                'injSev':       inj,
                'restraintUsed': rest in (1, 2, 3, 4, 5, 6),
                'drinking':     drink,
                'drugs':        drug,
                'personType':   ptype_map.get(ptyp, 'other'),
            })

    for i in range(0, len(persons), BATCH):
        c3.CrashPerson.upsertBatch({'objs': persons[i:i + BATCH]})

    return {'year': year, 'crashes': len(crashes), 'persons': len(persons)}


def loadFarsVehicles(cls, year, dataPath):
    """Load FARS VEHICLE.csv into Vehicle entity. Uses NHTSA's pre-decoded
    VPICMAKENAME / VPICMODELNAME / VPICBODYCLASS columns as canonical MMMY
    for joining to NHTSA defect datasets."""
    veh_csv = os.path.join(dataPath, f'FARS{year}NationalCSV', 'vehicle.csv')

    vehicles = []
    with open(veh_csv, newline='', encoding='latin-1') as f:
        for row in csv.DictReader(f):
            sc       = row.get('ST_CASE', '').strip()
            veh_no   = _int(row.get('VEH_NO'), 0)
            state    = _pad2(row.get('STATE', '0'))

            mod_year = _int(row.get('MOD_YEAR'))
            if mod_year is not None and (mod_year < 1900 or mod_year > 2100):
                mod_year = None  # 9999 = unknown

            vpic_make  = (row.get('VPICMAKENAME') or '').strip().upper()
            vpic_model = (row.get('VPICMODELNAME') or '').strip().upper()
            vpic_body  = (row.get('VPICBODYCLASS') or '').strip()

            fars_make_name = (row.get('MAKENAME') or '').strip().upper()
            fars_model     = (row.get('MODEL') or '').strip()

            body_type = (row.get('BODY_TYPNAME') or '').strip()
            vin       = (row.get('VIN') or '').strip()

            num_occs    = _int(row.get('NUMOCCS'))
            travel_spd  = _int(row.get('TRAV_SP'))
            if travel_spd is not None and (travel_spd < 0 or travel_spd > 250):
                travel_spd = None  # 997/998/999 = unknown sentinels

            vehicles.append({
                'id':            f'{sc}-{veh_no}-{year}',
                'stCase':        sc,
                'vehNo':         veh_no,
                'year':          year,
                'stateFips':     state,
                'modelYear':     mod_year,
                'vpicMake':      vpic_make,
                'vpicModel':     vpic_model,
                'vpicBodyClass': vpic_body,
                'farsMakeName':  fars_make_name,
                'farsModelCode': fars_model,
                'bodyType':      body_type,
                'vin':           vin,
                'numOccupants':  num_occs,
                'travelSpeed':   travel_spd,
            })

    BATCH = 500
    for i in range(0, len(vehicles), BATCH):
        c3.Vehicle.upsertBatch({'objs': vehicles[i:i + BATCH]})

    return {'year': year, 'vehicles': len(vehicles)}


# ─────────────────────────────────────────────────────────────────────────
# UC5 — NHTSA defect/ratings/SGO loaders (Phase A)
# ─────────────────────────────────────────────────────────────────────────

def _stars(v):
    try:
        n = int(v)
        return n if 0 <= n <= 5 else None
    except Exception:
        return None


def _yr_or_none(v):
    n = _int(v)
    if n is None or n < 1900 or n > 2100:
        return None
    return n


def loadRatings(cls, csvPath):
    """Load NHTSA NCAP / SaferCar safety ratings."""
    records = []
    with open(csvPath, newline='', encoding='latin-1') as f:
        for row in csv.DictReader(f):
            make  = (row.get('MAKE')  or '').strip().upper()
            model = (row.get('MODEL') or '').strip().upper()
            yr    = _yr_or_none(row.get('MODEL_YR'))
            if not make or not model or yr is None:
                continue
            prelease = _int(row.get('PRODUCTION_RELEASE'), 0)
            records.append({
                'id':                f'{make}-{model}-{yr}-{prelease}',
                'make':              make,
                'model':             model,
                'modelYear':         yr,
                'productionRelease': prelease,
                'bodyStyle':         (row.get('BODY_STYLE')    or '').strip(),
                'vehicleType':       (row.get('VEHICLE_TYPE')  or '').strip(),
                'vehicleClass':      (row.get('VEHICLE_CLASS') or '').strip(),
                'overallStars':      _stars(row.get('OVERALL_STARS')),
                'frntDrivStars':     _stars(row.get('FRNT_DRIV_STARS')),
                'frntPassStars':     _stars(row.get('FRNT_PASS_STARS')),
                'sideDrivStars':     _stars(row.get('SIDE_DRIV_STARS')),
                'sidePassStars':     _stars(row.get('SIDE_PASS_STARS')),
                'rolloverStars':     _stars(row.get('ROLLOVER_STARS')),
                'nhtsaFcw':          (row.get('NHTSA_FRNT_COLLISION_WARNING')  or '').strip(),
                'nhtsaLdw':          (row.get('NHTSA_LANE_DEPARTURE_WARNING')  or '').strip(),
                'nhtsaCib':          (row.get('NHTSA_CRASH_IMMINENT_BRAKE')    or '').strip(),
                'nhtsaDbs':          (row.get('NHTSA_DYNAMIC_BRAKE_SUPPORT')   or '').strip(),
            })

    BATCH = 500
    for i in range(0, len(records), BATCH):
        c3.SafetyRating.upsertBatch({'objs': records[i:i + BATCH]})
    return {'records': len(records)}


def loadInvestigations(cls, txtPath):
    """Load NHTSA Office of Defects Investigation flat file (TAB-delimited,
    no header). One row per investigation × MMMY × component."""
    records = []
    seen = set()
    with open(txtPath, encoding='latin-1') as f:
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 11:
                continue
            action_no = parts[0].strip()
            make      = parts[1].strip().upper()
            model     = parts[2].strip().upper()
            yr        = _yr_or_none(parts[3])
            comp_name = parts[4].strip()
            if not action_no or not make:
                continue
            key = (action_no, make, model, yr, comp_name)
            if key in seen:
                continue
            seen.add(key)
            records.append({
                'id':                f'{action_no}-{make}-{model}-{yr or 0}-{comp_name}',
                'nhtsaActionNumber': action_no,
                'make':              make,
                'model':             model,
                'modelYear':         yr,
                'compName':          comp_name,
                'mfrName':           parts[5].strip(),
                'openDate':          parts[6].strip(),
                'closeDate':         parts[7].strip(),
                'campNo':            parts[8].strip() or None,
                'subject':           parts[9].strip(),
                'summary':           parts[10].strip(),
            })

    BATCH = 1000
    for i in range(0, len(records), BATCH):
        c3.Investigation.upsertBatch({'objs': records[i:i + BATCH]})
    return {'records': len(records)}


def loadSgo(cls, defectRoot):
    """Load NHTSA SGO incident reports (ADS, ADAS, OTHER)."""
    files = [
        ('ADS',   'SGO_ADS.csv'),
        ('ADAS',  'SGO_ADAS.csv'),
        ('OTHER', 'SGO_OTHER.csv'),
    ]
    records = []
    for level, fn in files:
        path = os.path.join(defectRoot, 'sgo', fn)
        if not os.path.exists(path):
            continue
        with open(path, newline='', encoding='latin-1') as f:
            for r in csv.DictReader(f):
                rid = (r.get('Report ID') or '').strip()
                rver = _int(r.get('Report Version'), 1)
                if not rid:
                    continue
                make  = (r.get('Make')  or '').strip().upper()
                model = (r.get('Model') or '').strip().upper()
                yr    = _yr_or_none(r.get('Model Year'))
                records.append({
                    'id':               f'{rid}-v{rver}-{level}',
                    'reportId':         rid,
                    'reportVersion':    rver,
                    'automationLevel':  level,
                    'reportingEntity':  (r.get('Reporting Entity')          or '').strip(),
                    'reportSubmission': (r.get('Report Submission Date')   or '').strip(),
                    'make':             make,
                    'model':            model,
                    'modelYear':        yr,
                    'driverOperator':   (r.get('Driver / Operator Type')   or '').strip(),
                    'featureVersion':   (r.get('Automation Feature Version') or '').strip(),
                    'engagedStatus':    (r.get('Automation System Engaged') or
                                         r.get('SV Pre-Crash Movement') or '').strip(),
                    'incidentDate':     (r.get('Incident Date')            or '').strip(),
                    'incidentTime':     (r.get('Incident Time')            or '').strip(),
                    'state':            (r.get('State')                    or '').strip(),
                    'roadwayType':      (r.get('Roadway Type')             or '').strip(),
                    'crashWith':        (r.get('Crash With')               or '').strip(),
                    'narrative':        (r.get('Narrative')
                                         or r.get('Crash Description')
                                         or r.get('Incident Summary')
                                         or '').strip(),
                })

    BATCH = 500
    for i in range(0, len(records), BATCH):
        c3.SgoIncident.upsertBatch({'objs': records[i:i + BATCH]})
    return {'records': len(records)}


_RCL_PDF_BASE = 'https://static.nhtsa.gov/odi/rcl'


def _recall_pdf_url(nhtsa_id, document_name):
    """https://static.nhtsa.gov/odi/rcl/{year}/{document_name} where year
    is derived from the campaign-number prefix (e.g. '24V970' -> 2024)."""
    if not nhtsa_id or not document_name:
        return None
    import re as _re
    m = _re.match(r'^(\d{2})[A-Z]', nhtsa_id)
    if not m:
        return None
    yy = int(m.group(1))
    full = 2000 + yy if yy < 80 else 1900 + yy
    return f'{_RCL_PDF_BASE}/{full}/{document_name}'


def loadRecalls(cls, rclDir):
    """Load NHTSA Recalls. Reads every *.csv chunk in rclDir."""
    rows = []
    seen = set()
    chunks = sorted(f for f in os.listdir(rclDir) if f.endswith('.csv'))
    for chunk in chunks:
        path = os.path.join(rclDir, chunk)
        with open(path, newline='', encoding='latin-1') as f:
            reader = csv.reader(f)
            next(reader, None)  # header
            for r in reader:
                if len(r) < 6:
                    continue
                nhtsa_id = r[0].strip()
                doc_name = r[1].strip()
                make     = r[2].strip().upper()
                model    = r[3].strip().upper()
                yr       = _yr_or_none(r[4])
                if not nhtsa_id or not make:
                    continue
                key = (nhtsa_id, make, model, yr)
                if key in seen:
                    continue
                seen.add(key)
                rows.append({
                    'id':            f'{nhtsa_id}-{make}-{model}-{yr or 0}',
                    'nhtsaId':       nhtsa_id,
                    'make':          make,
                    'model':         model,
                    'modelYear':     yr,
                    'documentName':  doc_name,
                    'pdfUrl':        _recall_pdf_url(nhtsa_id, doc_name),
                    'summary':       r[5].strip()[:1500],
                })

    BATCH = 1000
    for i in range(0, len(rows), BATCH):
        c3.Recall.upsertBatch({'objs': rows[i:i + BATCH]})
    return {'records': len(rows), 'chunks': len(chunks)}


def loadTsbs(cls, tsbDir):
    """Load NHTSA Manufacturer Communications (TSBs). Reads every *.txt
    chunk; deduplicates to one row per (nhtsaId, make, model, modelYear),
    aggregating components into a comma-joined list."""
    chunks = sorted(f for f in os.listdir(tsbDir) if f.endswith('.txt'))
    aggregated = {}

    for chunk in chunks:
        path = os.path.join(tsbDir, chunk)
        with open(path, encoding='latin-1') as f:
            for line in f:
                parts = line.rstrip('\n').split('\t')
                if len(parts) < 14:
                    continue
                try:
                    nhtsa_id = int(parts[0].strip())
                except (ValueError, IndexError):
                    continue
                make  = parts[7].strip().upper()
                model = parts[8].strip().upper()
                yr    = _yr_or_none(parts[9])
                comps = parts[10].strip()
                if not make:
                    continue
                key = (nhtsa_id, make, model, yr)
                if key not in aggregated:
                    aggregated[key] = {
                        'commDate':  parts[4].strip(),
                        'tsbDocId':  parts[3].strip()[:120],
                        'commType':  parts[6].strip(),
                        'summary':   parts[13].strip()[:500],
                        'comps':     set(),
                    }
                if comps:
                    for c in comps.split(','):
                        c = c.strip()
                        if c:
                            aggregated[key]['comps'].add(c)

    rows = []
    for (nhtsa_id, make, model, yr), v in aggregated.items():
        rows.append({
            'id':         f'{nhtsa_id}-{make}-{model}-{yr or 0}',
            'nhtsaId':    nhtsa_id,
            'make':       make,
            'model':      model,
            'modelYear':  yr,
            'commDate':   v['commDate'],
            'tsbDocId':   v['tsbDocId'],
            'commType':   v['commType'],
            'components': ', '.join(sorted(v['comps']))[:600],
            'summary':    v['summary'],
        })

    BATCH = 1000
    for i in range(0, len(rows), BATCH):
        c3.Tsb.upsertBatch({'objs': rows[i:i + BATCH]})
    return {'records': len(rows), 'chunks': len(chunks)}


def loadComplaints(cls, txtPath):
    """Load NHTSA consumer complaints (FLAT_CMPL.txt, TAB-delimited, 51 fields)."""
    F = {
        'cmplid':     0,
        'odino':      1,
        'mfr_name':   2,
        'make':       3,
        'model':      4,
        'year':       5,
        'crash':      6,
        'fail_date':  7,
        'fire':       8,
        'injured':    9,
        'deaths':    10,
        'comp_desc': 11,
        'city':      12,
        'state':     13,
        'recv_date': 16,
        'narrative': 19,
    }

    records = []
    BATCH = 1000
    total = 0

    def flush(buf):
        if buf:
            c3.Complaint.upsertBatch({'objs': buf})
        return []

    with open(txtPath, encoding='latin-1') as f:
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 20:
                continue
            cmplid = parts[F['cmplid']].strip()
            make   = parts[F['make']].strip().upper()
            if not cmplid or not make:
                continue
            yr = _yr_or_none(parts[F['year']])
            records.append({
                'id':        cmplid,
                'cmplid':    cmplid,
                'odino':     parts[F['odino']].strip(),
                'mfrName':   parts[F['mfr_name']].strip(),
                'make':      make,
                'model':     parts[F['model']].strip().upper(),
                'modelYear': yr,
                'compDesc':  parts[F['comp_desc']].strip(),
                'crash':     parts[F['crash']].strip().upper() == 'Y',
                'fire':      parts[F['fire']].strip().upper()  == 'Y',
                'injured':   _int(parts[F['injured']], 0) or 0,
                'deaths':    _int(parts[F['deaths']],  0) or 0,
                'failDate':  parts[F['fail_date']].strip(),
                'recvDate':  parts[F['recv_date']].strip(),
                'city':      parts[F['city']].strip(),
                'state':     parts[F['state']].strip().upper(),
                'narrative': parts[F['narrative']].strip()[:1500],
            })
            total += 1
            if len(records) >= BATCH:
                records = flush(records)

    flush(records)
    return {'records': total}


def loadPopulation(cls, csvPath):
    records = []
    with open(csvPath, newline='', encoding='latin-1') as f:
        for row in csv.DictReader(f):
            fips = _pad2(row.get('STATE', '0'))
            if fips == '00':
                continue
            for yr in [2021, 2022, 2023, 2024]:
                col = f'POPESTIMATE{yr}'
                pop = _int(row.get(col))
                if pop:
                    records.append({
                        'id':         f'{fips}-{yr}',
                        'stateFips':  fips,
                        'year':       yr,
                        'population': pop,
                        'source':     'Census Bureau NST-EST2025',
                    })
    c3.PopulationEstimate.upsertBatch({'objs': records})
    return {'records': len(records)}


def loadVmt(cls, csvPath):
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
    }

    vmt_by_state_year = {}
    with open(csvPath, newline='', encoding='latin-1') as f:
        for row in csv.DictReader(f):
            name = (row.get('State', '') or '').strip().lower()
            yr   = _int(row.get('Year'))
            val  = _float(row.get('Thousands of Vehicle Miles'))
            if name and yr and val is not None and yr in [2021, 2022, 2023, 2024]:
                fips = STATE_NAME_TO_FIPS.get(name)
                if fips:
                    key = (fips, yr)
                    vmt_by_state_year[key] = vmt_by_state_year.get(key, 0) + val

    records = []
    for (fips, yr), vmt_thousands in vmt_by_state_year.items():
        records.append({
            'id':          f'{fips}-{yr}',
            'stateFips':   fips,
            'year':        yr,
            'vmtMillions': round(vmt_thousands / 1_000, 4),
            'source':      'FHWA Highway Statistics VM-2',
        })
    c3.VMTEstimate.upsertBatch({'objs': records})
    return {'records': len(records)}


def loadSvi(cls, csvPath):
    records = []
    with open(csvPath, newline='', encoding='latin-1') as f:
        for row in csv.DictReader(f):
            fips5 = (row.get('FIPS') or '').strip().zfill(5)
            if not fips5 or fips5 == '00000':
                continue
            state_fips = fips5[:2]

            def pct(col):
                v = _float(row.get(col))
                return v if v is not None and v >= 0 else None

            records.append({
                'id':         fips5,
                'countyFips': fips5,
                'stateFips':  state_fips,
                'countyName': row.get('COUNTY', ''),
                'stateName':  row.get('STATE', ''),
                'stateAbbr':  row.get('ST_ABBR', ''),
                'rplThemes':  pct('RPL_THEMES'),
                'rplTheme1':  pct('RPL_THEME1'),
                'rplTheme2':  pct('RPL_THEME2'),
                'rplTheme3':  pct('RPL_THEME3'),
                'rplTheme4':  pct('RPL_THEME4'),
                'epPov150':   pct('EP_POV150'),
                'epUnemp':    pct('EP_UNEMP'),
                'epUninsur':  pct('EP_UNINSUR'),
                'epNohsdp':   pct('EP_NOHSDP'),
                'epMinrty':   pct('EP_MINRTY'),
            })

    BATCH = 500
    for i in range(0, len(records), BATCH):
        c3.CountySvi.upsertBatch({'objs': records[i:i + BATCH]})
    return {'records': len(records)}


def loadAll(cls, dataRoot):
    results = {}

    pop_path = os.path.join(dataRoot, 'NST-EST2025-ALLDATA.csv')
    results['population'] = c3.DotSafetyLoader.loadPopulation(pop_path)

    vmt_path = os.path.join(dataRoot, 'Vehicle_Miles_of_Travel_by_Functional_System_and_State__1980_-_2024__VM-2_.csv')
    results['vmt'] = c3.DotSafetyLoader.loadVmt(vmt_path)

    svi_path = os.path.join(dataRoot, 'SVI_2022_US_county.csv')
    results['svi'] = c3.DotSafetyLoader.loadSvi(svi_path)

    for yr in [2021, 2022, 2023, 2024]:
        results[f'fars_{yr}']          = c3.DotSafetyLoader.loadFars(yr, dataRoot)
        results[f'fars_vehicles_{yr}'] = c3.DotSafetyLoader.loadFarsVehicles(yr, dataRoot)

    # UC5 — NHTSA Phase A defect/ratings/SGO datasets
    defect_root = os.path.join(dataRoot, 'x NHTSA Defect Data')
    if os.path.isdir(defect_root):
        ratings_path = os.path.join(defect_root, 'ratings', 'Safercar_data.csv')
        if os.path.exists(ratings_path):
            results['ratings'] = c3.DotSafetyLoader.loadRatings(ratings_path)
        inv_path = os.path.join(defect_root, 'investigations', 'FLAT_INV.txt')
        if os.path.exists(inv_path):
            results['investigations'] = c3.DotSafetyLoader.loadInvestigations(inv_path)
        results['sgo'] = c3.DotSafetyLoader.loadSgo(defect_root)

        # Phase B
        rcl_dir = os.path.join(defect_root, 'recalls')
        if os.path.isdir(rcl_dir):
            results['recalls'] = c3.DotSafetyLoader.loadRecalls(rcl_dir)
        tsb_dir = os.path.join(defect_root, 'tsbs')
        if os.path.isdir(tsb_dir):
            results['tsbs'] = c3.DotSafetyLoader.loadTsbs(tsb_dir)

        # Phase C
        cmpl_path = os.path.join(defect_root, 'complaints', 'FLAT_CMPL.txt')
        if os.path.exists(cmpl_path):
            results['complaints'] = c3.DotSafetyLoader.loadComplaints(cmpl_path)

    return results
