function getAll() {
  return StateRef.fetch({
    limit: -1,
    include: 'this',
    order: 'ascending(name)',
  }).objs;
}

function getByFips(fips) {
  return StateRef.fetch({
    filter: Filter.eq('fips', fips),
    include: 'this',
    limit: 1,
  }).objs[0] || null;
}
