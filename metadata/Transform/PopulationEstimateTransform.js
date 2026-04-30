// Maps SourcePopulationEstimate → PopulationEstimate (one row → four records, 2021–2024)
function transform(source) {
  var records = [];
  var years = [2021, 2022, 2023, 2024];
  years.forEach(function (yr) {
    var pop = source['pop' + yr];
    if (pop) {
      records.push({
        id: source.stateFips + '-' + yr,
        stateFips: source.stateFips,
        year: yr,
        population: pop,
        source: 'Census Bureau NST-EST2025',
      });
    }
  });
  return records;
}
