function getAll() {
  return BehavioralFactor.fetch({
    limit: -1,
    include: 'this',
    order: 'ascending(name)',
  }).objs;
}
