// Maps SourceVMTEstimate → VMTEstimate  (thousands → millions)
function transform(source) {
  if (!source.year || [2021, 2022, 2023, 2024].indexOf(source.year) === -1) return [];
  return [{
    id: source.stateFips + '-' + source.year,
    stateFips: source.stateFips,
    year: source.year,
    vmtMillions: Math.round((source.vmtThousands / 1000) * 10000) / 10000,
    source: 'FHWA Highway Statistics VM-2',
  }];
}
