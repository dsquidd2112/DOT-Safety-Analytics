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
        results[f'fars_{yr}'] = c3.DotSafetyLoader.loadFars(yr, dataRoot)

    return results
