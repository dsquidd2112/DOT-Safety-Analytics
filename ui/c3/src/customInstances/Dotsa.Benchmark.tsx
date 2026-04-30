import React, { useState, useEffect, useCallback } from 'react';
import { Grid, GridColumn, GridSortChangeEvent } from '@progress/kendo-react-grid';
import { DropDownList, DropDownListChangeEvent, MultiSelect, MultiSelectChangeEvent } from '@progress/kendo-react-dropdowns';
import { Button } from '@progress/kendo-react-buttons';
import { orderBy, SortDescriptor } from '@progress/kendo-data-query';

interface StateRow {
  stateFips: string; name: string; abbr: string;
  fatals: number;
  ratePer100k: number | null; ratePerVmt: number | null;
  rank100k: number | null; vsNationalPct: number | null;
}
interface BenchmarkResult {
  year: number;
  national: { fatals: number; ratePer100k: number | null };
  states: StateRow[]; nStates: number;
}
interface PeerResult {
  peers: StateRow[];
  national: { fatals: number; ratePer100k: number | null };
  summary: { bestRateState: string; worstRateState: string; rateSpread: number | null };
}

const YEARS = [2024, 2023, 2022, 2021];

// Simplified SVG polygon approximations — all 51 jurisdictions
const STATE_PATHS: Record<string, string> = {
  AL: 'M520,340 L540,340 L545,370 L535,410 L520,415 L510,380 L510,345Z',
  AK: 'M120,420 L180,430 L200,410 L180,390 L150,385 L130,395Z',
  AZ: 'M195,310 L255,320 L255,390 L215,395 L190,375 L185,330Z',
  AR: 'M490,310 L540,310 L545,340 L520,340 L490,345 L480,325Z',
  CA: 'M130,230 L185,225 L195,310 L185,330 L155,360 L130,350 L120,290Z',
  CO: 'M245,260 L345,260 L345,305 L245,305Z',
  CT: 'M630,195 L650,192 L652,210 L630,212Z',
  DE: 'M618,225 L630,222 L633,240 L618,243Z',
  DC: 'M600,248 L607,244 L610,252 L603,255Z',
  FL: 'M530,415 L545,370 L580,370 L590,390 L575,430 L555,445 L535,440Z',
  GA: 'M535,370 L575,370 L580,400 L560,420 L535,415 L530,400Z',
  HI: 'M220,460 L240,455 L245,465 L230,470Z',
  ID: 'M175,165 L215,160 L225,185 L220,225 L195,230 L180,210Z',
  IL: 'M490,245 L515,242 L520,275 L510,305 L490,310 L485,280Z',
  IN: 'M515,242 L540,240 L543,275 L520,275Z',
  IA: 'M450,220 L490,215 L495,250 L455,255 L445,240Z',
  KS: 'M355,300 L455,295 L458,330 L355,330Z',
  KY: 'M515,290 L575,285 L580,305 L545,315 L510,315Z',
  LA: 'M480,380 L520,375 L520,415 L500,425 L475,410Z',
  ME: 'M660,155 L685,150 L690,175 L665,182Z',
  MD: 'M590,242 L618,238 L620,255 L607,258 L590,255Z',
  MA: 'M640,185 L672,180 L675,197 L640,200Z',
  MI: 'M510,195 L540,190 L550,215 L530,225 L510,220Z',
  MN: 'M440,160 L490,155 L495,215 L450,220 L435,195Z',
  MS: 'M500,345 L520,340 L520,415 L500,415 L490,380Z',
  MO: 'M455,295 L515,290 L520,315 L490,345 L455,345Z',
  MT: 'M215,155 L330,150 L335,205 L215,210Z',
  NE: 'M345,255 L455,250 L455,295 L345,300Z',
  NV: 'M155,235 L195,230 L195,310 L155,310 L140,270Z',
  NH: 'M645,170 L660,168 L660,192 L645,195Z',
  NJ: 'M618,225 L638,220 L643,247 L618,252Z',
  NM: 'M245,305 L305,305 L305,380 L245,380Z',
  NY: 'M575,185 L640,182 L643,225 L618,228 L580,230 L568,210Z',
  NC: 'M553,310 L630,302 L635,325 L555,330Z',
  ND: 'M340,155 L440,152 L440,190 L340,192Z',
  OH: 'M543,240 L575,238 L580,275 L545,280 L542,258Z',
  OK: 'M355,330 L490,325 L492,365 L355,368Z',
  OR: 'M130,185 L215,178 L215,230 L185,230 L130,240Z',
  PA: 'M570,218 L630,213 L633,245 L575,248Z',
  RI: 'M650,200 L660,198 L662,215 L650,216Z',
  SC: 'M555,330 L595,325 L598,355 L560,358Z',
  SD: 'M340,192 L440,190 L440,250 L345,255 L338,228Z',
  TN: 'M490,310 L575,305 L580,328 L490,335Z',
  TX: 'M305,330 L460,325 L465,395 L390,430 L330,420 L300,390Z',
  UT: 'M200,255 L245,255 L245,310 L200,310Z',
  VT: 'M632,168 L645,167 L645,193 L632,195Z',
  VA: 'M565,265 L630,258 L633,285 L595,300 L555,300Z',
  WA: 'M130,155 L215,150 L215,178 L130,182Z',
  WV: 'M565,265 L595,262 L598,290 L570,295Z',
  WI: 'M470,175 L510,172 L513,218 L470,222Z',
  WY: 'M220,210 L335,205 L338,258 L222,260Z',
};

const LABEL_STATES = [
  'TX','CA','MT','NM','AZ','NV','CO','WY','OR','WA','ID','UT','KS','NE',
  'SD','ND','MN','OK','MO','AR','LA','MS','AL','GA','FL','TN','KY','OH',
  'IN','IL','MI','WI','IA','PA','NY','NC','VA','SC','ME',
];

function choroplethFill(rate: number | null, maxRate: number): string {
  if (rate == null || maxRate === 0) return '#e0e0e0';
  const t = rate / maxRate;
  if (t < 0.33) return `rgba(46,125,50,${(0.3 + t * 0.9).toFixed(2)})`;
  if (t < 0.66) return `rgba(230,81,0,${(0.35 + t * 0.5).toFixed(2)})`;
  return `rgba(198,40,40,${(0.45 + t * 0.45).toFixed(2)})`;
}

function rateColor(rate: number | null, national: number | null): string {
  if (rate == null || national == null) return '#9e9e9e';
  const r = rate / national;
  if (r > 1.3) return '#c62828';
  if (r > 1.0) return '#e65100';
  if (r > 0.7) return '#f9a825';
  return '#2e7d32';
}

function downloadCsv(rows: StateRow[], year: number) {
  const header = 'State,Abbr,Fatalities,Rate/100K,Rate/VMT,Rank,vs National %';
  const body   = rows.map((r) =>
    [r.name, r.abbr, r.fatals, r.ratePer100k ?? '', r.ratePerVmt ?? '', r.rank100k ?? '', r.vsNationalPct ?? ''].join(',')
  ).join('\n');
  const blob = new Blob([header + '\n' + body], { type: 'text/csv' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = `dotsa_benchmark_${year}.csv`; a.click();
  URL.revokeObjectURL(url);
}

// ─────────────────────────────────────────────────────────────────────────────
// Choropleth map component
// ─────────────────────────────────────────────────────────────────────────────
interface ChoroplethProps {
  states: StateRow[]; maxRate: number; national: number | null;
  selected: string | null; onSelect: (abbr: string) => void;
}

function USChoropleth({ states, maxRate, national, selected, onSelect }: ChoroplethProps) {
  const [tip, setTip] = useState<{ x: number; y: number; abbr: string } | null>(null);
  const byAbbr = Object.fromEntries(states.map((s) => [s.abbr, s]));

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <svg viewBox="100 140 625 345" style={{ width: '100%', height: 'auto', display: 'block' }}>
        {Object.entries(STATE_PATHS).map(([abbr, d]) => {
          const s    = byAbbr[abbr];
          const fill = choroplethFill(s?.ratePer100k ?? null, maxRate);
          const isSel = selected === abbr;
          return (
            <path
              key={abbr} d={d} fill={fill}
              stroke={isSel ? '#1565c0' : '#ffffff'}
              strokeWidth={isSel ? 2 : 0.5}
              style={{ cursor: 'pointer' }}
              onMouseEnter={(e) => setTip({ x: e.clientX, y: e.clientY, abbr })}
              onMouseLeave={() => setTip(null)}
              onClick={() => onSelect(abbr)}
            />
          );
        })}
        {LABEL_STATES.map((abbr) => {
          const d = STATE_PATHS[abbr];
          if (!d) return null;
          const nums = d.match(/[\d.]+/g)!.map(Number);
          const xs = nums.filter((_, i) => i % 2 === 0);
          const ys = nums.filter((_, i) => i % 2 === 1);
          const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
          const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
          return (
            <text key={abbr} x={cx} y={cy} textAnchor="middle" dominantBaseline="middle"
              style={{ fontSize: 6, fill: 'rgba(255,255,255,0.8)', fontWeight: 700, fontFamily: 'monospace', pointerEvents: 'none', userSelect: 'none' }}>
              {abbr}
            </text>
          );
        })}
      </svg>

      {/* Legend */}
      <div style={{ position: 'absolute', bottom: 4, right: 4, display: 'flex', alignItems: 'center', gap: 3, background: 'rgba(255,255,255,0.92)', padding: '3px 8px', border: '1px solid #e0e0e0', borderRadius: 2 }}>
        <span style={{ fontSize: 9, color: '#777' }}>Low</span>
        {[0.1, 0.3, 0.5, 0.7, 0.9].map((t) => (
          <div key={t} style={{ width: 14, height: 8, background: choroplethFill(t * maxRate, maxRate) }} />
        ))}
        <span style={{ fontSize: 9, color: '#777' }}>High  Rate/100K</span>
      </div>

      {/* Tooltip */}
      {tip && (() => {
        const s   = byAbbr[tip.abbr];
        if (!s) return null;
        const clr = rateColor(s.ratePer100k, national);
        return (
          <div style={{ position: 'fixed', left: tip.x + 14, top: tip.y - 56, background: '#fff', border: `1px solid ${clr}`, padding: '6px 10px', fontSize: 11, pointerEvents: 'none', zIndex: 9999, boxShadow: '0 2px 8px rgba(0,0,0,0.15)', borderRadius: 2, whiteSpace: 'nowrap' }}>
            <strong style={{ color: '#212121' }}>{s.name}</strong>
            <span style={{ color: '#9e9e9e' }}> · </span>
            <span style={{ color: clr, fontWeight: 700 }}>{s.ratePer100k?.toFixed(2) ?? '–'} per 100K</span>
            {s.vsNationalPct != null && (
              <span style={{ color: '#9e9e9e' }}> ({s.vsNationalPct > 0 ? '+' : ''}{s.vsNationalPct.toFixed(1)}% vs nat'l)</span>
            )}
            <div style={{ fontSize: 10, color: '#bbb', marginTop: 2 }}>Click to view details</div>
          </div>
        );
      })()}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────────────────────
export default function DotsaBenchmark() {
  const [view, setView]             = useState<'map' | 'table'>('map');
  const [year, setYear]             = useState(2024);
  const [bm, setBm]                 = useState<BenchmarkResult | null>(null);
  const [peers, setPeers]           = useState<PeerResult | null>(null);
  const [peerFips, setPeerFips]     = useState<string[]>([]);
  const [sort, setSort]             = useState<SortDescriptor[]>([{ field: 'rank100k', dir: 'asc' }]);
  const [loading, setLoading]       = useState(false);
  const [allStates, setAllStates]   = useState<{ text: string; value: string }[]>([]);
  const [mapSelected, setMapSelected] = useState<string | null>(null);

  useEffect(() => {
    c3Action('StateRef', 'getAll', []).then((r: { fips: string; name: string }[]) => {
      setAllStates((r || []).map((s) => ({ text: s.name, value: s.fips })));
    });
  }, []);

  const loadBenchmarks = useCallback(async () => {
    setLoading(true);
    try {
      const result: BenchmarkResult = await c3Action('DotSafetyBenchmark', 'getAllBenchmarks', [year, null]);
      setBm(result);
    } finally {
      setLoading(false);
    }
  }, [year]);

  useEffect(() => { loadBenchmarks(); }, [loadBenchmarks]);

  const loadPeers = useCallback(async () => {
    if (peerFips.length < 2) return;
    const result: PeerResult = await c3Action('DotSafetyBenchmark', 'getPeerComparison', [peerFips, year, null]);
    setPeers(result);
  }, [peerFips, year]);

  useEffect(() => { if (peerFips.length >= 2) loadPeers(); }, [loadPeers]);

  const tableData = bm ? orderBy(bm.states, sort) : [];
  const maxRate   = bm ? Math.max(...bm.states.map((s) => s.ratePer100k ?? 0)) : 1;
  const mapRanked = bm ? [...bm.states].sort((a, b) => (a.rank100k ?? 999) - (b.rank100k ?? 999)) : [];
  const selState  = (mapSelected && bm) ? bm.states.find((s) => s.abbr === mapSelected) ?? null : null;
  const natRate   = bm?.national.ratePer100k ?? null;

  function addToPeers(fips: string) {
    if (!peerFips.includes(fips) && peerFips.length < 4) setPeerFips((p) => [...p, fips]);
    setView('table');
  }

  const btnStyle = (active: boolean): React.CSSProperties => ({
    padding: '6px 18px', border: '1px solid #ccc', cursor: 'pointer', fontSize: '0.85rem',
    background: active ? '#1565c0' : '#f5f5f5',
    color:      active ? '#fff'    : '#555',
    fontWeight: active ? 700       : 400,
    transition: 'all .15s',
  });

  return (
    <div className="c3-kendo-wrapper" style={{ padding: '1.5rem' }}>

      {/* ── Controls ── */}
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <DropDownList
          data={YEARS.map((y) => ({ text: String(y), value: y }))}
          textField="text" dataItemKey="value"
          value={{ text: String(year), value: year }}
          onChange={(e: DropDownListChangeEvent) => setYear(e.value.value)}
          style={{ width: 100 }}
        />
        <div style={{ display: 'flex', borderRadius: 2, overflow: 'hidden' }}>
          <button style={btnStyle(view === 'map')}   onClick={() => setView('map')}>Map View</button>
          <button style={btnStyle(view === 'table')} onClick={() => setView('table')}>Table View</button>
        </div>
        {view === 'table' && bm && (
          <Button onClick={() => downloadCsv(bm.states, year)}>Export CSV</Button>
        )}
      </div>

      {/* ── National summary ── */}
      {bm && (
        <div style={{ marginBottom: '1rem', color: '#555', fontSize: '0.875rem' }}>
          National avg: <strong>{bm.national.ratePer100k?.toFixed(2)} per 100K</strong>
          &nbsp;|&nbsp;{bm.national.fatals.toLocaleString()} total fatalities
          &nbsp;|&nbsp;{bm.nStates} states ranked
        </div>
      )}

      {loading ? <div>Loading…</div> : (
        <>
          {/* ══ MAP VIEW ══ */}
          {view === 'map' && bm && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 256px', gap: '1.25rem' }}>

              {/* Left: choropleth + drill-down */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div style={{ border: '1px solid #e0e0e0', padding: '0.75rem', borderRadius: 4 }}>
                  <div style={{ fontSize: '0.78rem', color: '#888', marginBottom: '0.4rem' }}>
                    Fatality rate per 100K population · {year} · Click any state for details
                  </div>
                  <USChoropleth
                    states={bm.states} maxRate={maxRate} national={natRate}
                    selected={mapSelected} onSelect={setMapSelected}
                  />
                </div>

                {selState ? (
                  <div style={{ border: '1px solid #e0e0e0', padding: '1rem', borderRadius: 4, borderTop: `3px solid ${rateColor(selState.ratePer100k, natRate)}` }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                      <div>
                        <div style={{ fontSize: '1.15rem', fontWeight: 700 }}>{selState.name}</div>
                        <div style={{ fontSize: '0.8rem', color: '#777' }}>
                          Rank #{selState.rank100k} of {bm.nStates}&nbsp;·&nbsp;
                          <span style={{ color: rateColor(selState.ratePer100k, natRate), fontWeight: 600 }}>
                            {(selState.vsNationalPct ?? 0) > 0 ? '+' : ''}{selState.vsNationalPct?.toFixed(1) ?? '–'}% vs national
                          </span>
                        </div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: '2.2rem', fontWeight: 900, color: rateColor(selState.ratePer100k, natRate), lineHeight: 1 }}>
                          {selState.ratePer100k?.toFixed(2) ?? '–'}
                        </div>
                        <div style={{ fontSize: '0.68rem', color: '#aaa', letterSpacing: 1 }}>PER 100K</div>
                      </div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem', marginBottom: '0.75rem' }}>
                      {[
                        { label: 'Fatalities',  value: selState.fatals.toLocaleString() },
                        { label: 'Rate / VMT',  value: selState.ratePerVmt?.toFixed(2) ?? '–' },
                        { label: 'vs National', value: selState.vsNationalPct != null ? `${selState.vsNationalPct > 0 ? '+' : ''}${selState.vsNationalPct.toFixed(1)}%` : '–' },
                      ].map((item, i) => (
                        <div key={i} style={{ padding: '0.5rem', background: '#f5f5f5', textAlign: 'center', borderRadius: 2 }}>
                          <div style={{ fontSize: '0.68rem', color: '#999', textTransform: 'uppercase', letterSpacing: 1 }}>{item.label}</div>
                          <div style={{ fontSize: '1rem', fontWeight: 700, marginTop: 2, color: i === 2 ? rateColor(selState.ratePer100k, natRate) : '#212121' }}>
                            {item.value}
                          </div>
                        </div>
                      ))}
                    </div>
                    <button
                      onClick={() => addToPeers(selState.stateFips)}
                      disabled={peerFips.includes(selState.stateFips) || peerFips.length >= 4}
                      style={{ padding: '6px 14px', background: '#1565c0', color: '#fff', border: 'none', cursor: 'pointer', fontSize: '0.8rem', borderRadius: 2, opacity: (peerFips.includes(selState.stateFips) || peerFips.length >= 4) ? 0.45 : 1 }}>
                      + Add to Peer Comparison →
                    </button>
                  </div>
                ) : (
                  <div style={{ border: '1px dashed #e0e0e0', padding: '1.5rem', textAlign: 'center', color: '#bbb', borderRadius: 4 }}>
                    Click any state on the map to view detailed benchmark data
                  </div>
                )}
              </div>

              {/* Right: ranked sidebar */}
              <div style={{ border: '1px solid #e0e0e0', padding: '0.75rem', borderRadius: 4, maxHeight: 620, overflowY: 'auto' }}>
                <div style={{ fontWeight: 700, fontSize: '0.75rem', color: '#777', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: 1 }}>
                  Rankings — Rate/100K
                </div>
                {mapRanked.map((s, i) => {
                  const isSel  = mapSelected === s.abbr;
                  const clr    = rateColor(s.ratePer100k, natRate);
                  const barPct = maxRate > 0 ? ((s.ratePer100k ?? 0) / maxRate) * 100 : 0;
                  return (
                    <div key={s.stateFips} onClick={() => setMapSelected(s.abbr)}
                      style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '4px 3px', cursor: 'pointer', background: isSel ? `${clr}18` : 'transparent', borderLeft: isSel ? `2px solid ${clr}` : '2px solid transparent', borderRadius: 1, marginBottom: 1 }}>
                      <span style={{ width: 18, fontSize: 9, color: '#bbb', textAlign: 'right', fontFamily: 'monospace' }}>{i + 1}</span>
                      <span style={{ width: 28, fontSize: 10, fontWeight: 700, color: '#333', fontFamily: 'monospace' }}>{s.abbr}</span>
                      <div style={{ flex: 1, height: 4, background: '#eeeeee', borderRadius: 2, overflow: 'hidden' }}>
                        <div style={{ height: '100%', width: `${barPct}%`, background: clr, borderRadius: 2 }} />
                      </div>
                      <span style={{ width: 32, fontSize: 10, fontWeight: 700, color: clr, textAlign: 'right', fontFamily: 'monospace' }}>
                        {s.ratePer100k?.toFixed(1) ?? '–'}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ══ TABLE VIEW ══ */}
          {view === 'table' && (
            <>
              <Grid
                data={tableData} sort={sort}
                onSortChange={(e: GridSortChangeEvent) => setSort(e.sort)}
                sortable style={{ height: 500 }}
                onRowClick={(e) => {
                  const fips = (e.dataItem as StateRow).stateFips;
                  if (!peerFips.includes(fips) && peerFips.length < 4) setPeerFips([...peerFips, fips]);
                }}
              >
                <GridColumn field="rank100k"      title="Rank"        width={70} />
                <GridColumn field="name"          title="State"       width={160} />
                <GridColumn field="abbr"          title="Abbr"        width={60} />
                <GridColumn field="fatals"        title="Fatalities"  width={110} />
                <GridColumn field="ratePer100k"   title="Rate/100K"   width={110} />
                <GridColumn field="ratePerVmt"    title="Rate/VMT"    width={110} />
                <GridColumn field="vsNationalPct" title="vs Nat'l %"  width={110} />
              </Grid>

              <div style={{ marginTop: '2rem' }}>
                <h3>Peer State Comparison</h3>
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', marginBottom: '1rem' }}>
                  <MultiSelect
                    data={allStates} textField="text" dataItemKey="value"
                    value={allStates.filter((s) => peerFips.includes(s.value))}
                    onChange={(e: MultiSelectChangeEvent) => setPeerFips(e.value.map((v: { value: string }) => v.value))}
                    placeholder="Select up to 4 states…" style={{ width: 360 }}
                  />
                  <Button onClick={loadPeers} disabled={peerFips.length < 2}>Compare</Button>
                  <Button onClick={() => { setPeerFips([]); setPeers(null); }}>Clear</Button>
                </div>
                {peers && (
                  <Grid data={peers.peers} style={{ height: 220 }}>
                    <GridColumn field="abbr"          title="State"     width={80} />
                    <GridColumn field="name"          title="Name"      width={160} />
                    <GridColumn field="fatals"        title="Fatals"    width={100} />
                    <GridColumn field="ratePer100k"   title="Rate/100K" width={110} />
                    <GridColumn field="vsNationalPct" title="vs Nat'l %" width={110} />
                  </Grid>
                )}
                {peers?.summary && (
                  <div style={{ marginTop: '0.75rem', color: '#555' }}>
                    Best: <strong>{peers.summary.bestRateState}</strong>
                    &nbsp;|&nbsp;Worst: <strong>{peers.summary.worstRateState}</strong>
                    &nbsp;|&nbsp;Spread: <strong>{peers.summary.rateSpread?.toFixed(2)}</strong> per 100K
                  </div>
                )}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
