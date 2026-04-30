function getByBehavior(behaviorId, minEvidence) {
  var f = Filter.eq('behaviorId', behaviorId);
  var results = Countermeasure.fetch({
    filter: f,
    include: 'this',
    limit: -1,
  }).objs || [];

  if (!minEvidence) return results;

  var order = { high: 3, moderate: 2, low: 1 };
  var threshold = order[minEvidence] || 0;
  return results.filter(function (c) {
    return (order[c.evidenceLevel] || 0) >= threshold;
  });
}
