/*
 * Maps SourceFarsCrash → FatalCrash base record.
 * Behavioral flags are NOT set here (they come from ACC_AUX via DotSafetyLoader.loadFars).
 * This transform handles simple field mapping only.
 */
var LIGHTING = { '1': 'daylight', '2': 'dark_lighted', '3': 'dark_unlighted', '4': 'dawn_dusk', '5': 'dawn_dusk' };
var WEATHER  = { '1': 'clear', '2': 'rain', '3': 'sleet', '4': 'snow', '5': 'fog', '10': 'cloudy' };

function transform(source, year) {
  var sc    = (source.stCase || '').trim();
  var state = String(parseInt(source.stateFips || '0')).padStart(2, '0');
  var hour  = source.hour;
  if (hour !== null && hour > 23) hour = null;

  return [{
    id:        sc + '-' + year,
    stCase:    sc,
    stateFips: state,
    year:      year,
    countyFips: String(parseInt(source.countyFips || '0')).padStart(3, '0'),
    countyName: (source.countyName || '').trim(),
    cityCode:   String(source.cityCode || '0'),
    cityName:   (source.cityName || '').trim(),
    month:     source.month,
    dayWeek:   source.dayWeek,
    hour:      hour,
    fatals:    source.fatals || 0,
    latitude:  (source.latitude && Math.abs(source.latitude) <= 90)  ? source.latitude  : null,
    longitude: (source.longitude && Math.abs(source.longitude) <= 180) ? source.longitude : null,
    lighting:  LIGHTING[String(source.lighting)] || '',
    weather:   WEATHER[String(source.weather)]   || '',
    alcFlag:   false,
    drugFlag:  false,
    speedFlag: false,
    distractFlag: false,
    drowsyFlag:   false,
    beltFlag:     false,
    pedFlag:      false,
    wrongwayFlag: false,
    hitrunFlag:   false,
  }];
}
