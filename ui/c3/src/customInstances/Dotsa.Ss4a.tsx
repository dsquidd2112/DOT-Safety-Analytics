import React, { useState, useEffect, useCallback } from 'react';
import { DropDownList, DropDownListChangeEvent } from '@progress/kendo-react-dropdowns';
import { Card, CardHeader, CardBody } from '@progress/kendo-react-layout';

interface StateOption { fips: string; name: string; abbr: string; }

interface BehaviorAlignment {
  id: string;
  name: string;
  crashes: number;
  pctCrashes: number;
  rank: number;
  ss4aCategories: string[];
  programs: string[];
  ss4aEligible: boolean;
  projectType: string;
  strategy: string;
}

interface Narrative {
  stateName: string; stateAbbr: string; year: number;
  totalFatals: number; rate100k: number | null;
  natRate100k: number | null; pctVsNational: number | null;
}

interface AlignmentData {
  stateFips: string; stateName: string; year: number;
  narrative: Narrative;
  behaviors: BehaviorAlignment[];
  catScores: Record<string, number>;
}

const YEARS = [2024, 2023, 2022, 2021];

const SAFE_SYSTEM_CATEGORIES = ['Safe People', 'Safe Roads', 'Safe Speeds', 'Safe Vehicles', 'Safe System'];

const CAT_COLOR: Record<string, string> = {
  'Safe People': '#1565c0',
  'Safe Roads':  '#2e7d32',
  'Safe Speeds': '#6a1b9a',
  'Safe Vehicles': '#bf360c',
  'Safe System': '#37474f',
};

const ELIGIBLE_BADGE = (eligible: boolean) =>
  eligible
    ? <span style={{ background: '#2e7d32', color: '#fff', borderRadius: 4, padding: '2px 8px', fontSize: '0.75rem' }}>SS4A Eligible</span>
    : <span style={{ background: '#bdbdbd', color: '#fff', borderRadius: 4, padding: '2px 8px', fontSize: '0.75rem' }}>Not SS4A</span>;

export default function DotsaSs4a() {
  const [states, setStates]     = useState<StateOption[]>([]);
  const [selected, setSelected] = useState<StateOption | null>(null);
  const [year, setYear]         = useState(2024);
  const [data, setData]         = useState<AlignmentData | null>(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);

  useEffect(() => {
    c3Action('StateRef', 'getAll', []).then((r: StateOption[]) => {
      setStates(r || []);
      const tx = (r || []).find((s) => s.fips === '48');
      if (tx) setSelected(tx);
    });
  }, []);

  const load = useCallback(async () => {
    if (!selected) return;
    setLoading(true);
    setError(null);
    try {
      const result: AlignmentData = await c3Action('DotSafetySs4a', 'getSs4aAlignment',
        [selected.fips, year, null]);
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [selected, year]);

  useEffect(() => { load(); }, [load]);

  const stateItems = states.map((s) => ({ text: s.name, value: s }));

  return (
    <div className="c3-kendo-wrapper" style={{ padding: '1.5rem' }}>
      {/* Controls */}
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', alignItems: 'center' }}>
        <DropDownList
          data={stateItems} textField="text" dataItemKey="value"
          value={stateItems.find((i) => i.value?.fips === selected?.fips) || null}
          onChange={(e: DropDownListChangeEvent) => setSelected(e.value.value)}
          style={{ width: 220 }}
        />
        <DropDownList
          data={YEARS.map((y) => ({ text: String(y), value: y }))} textField="text" dataItemKey="value"
          value={{ text: String(year), value: year }}
          onChange={(e: DropDownListChangeEvent) => setYear(e.value.value)}
          style={{ width: 100 }}
        />
      </div>

      {error && <div style={{ color: 'red', marginBottom: '1rem' }}>{error}</div>}
      {loading && <div>Loading…</div>}

      {!loading && data && (
        <>
          {/* State narrative */}
          <Card style={{ marginBottom: '1.5rem' }}>
            <CardHeader>
              <strong>{data.narrative.stateName} — Safe System Alignment ({data.year})</strong>
            </CardHeader>
            <CardBody>
              <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
                <div>
                  <div style={{ color: '#555', fontSize: '0.85rem' }}>Total Fatalities</div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 700 }}>{data.narrative.totalFatals.toLocaleString()}</div>
                </div>
                <div>
                  <div style={{ color: '#555', fontSize: '0.85rem' }}>Rate / 100K</div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 700 }}>{data.narrative.rate100k?.toFixed(2) ?? '–'}</div>
                </div>
                <div>
                  <div style={{ color: '#555', fontSize: '0.85rem' }}>vs National</div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 700, color: (data.narrative.pctVsNational ?? 0) > 0 ? '#c62828' : '#2e7d32' }}>
                    {data.narrative.pctVsNational != null
                      ? `${data.narrative.pctVsNational > 0 ? '+' : ''}${data.narrative.pctVsNational.toFixed(1)}%`
                      : '–'}
                  </div>
                </div>
              </div>
            </CardBody>
          </Card>

          {/* Category score summary */}
          <Card style={{ marginBottom: '1.5rem' }}>
            <CardHeader><strong>Safe System Category Distribution (% of fatal crashes)</strong></CardHeader>
            <CardBody>
              <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
                {Object.entries(data.catScores)
                  .sort((a, b) => b[1] - a[1])
                  .map(([cat, pct]) => (
                    <div key={cat} style={{ textAlign: 'center' }}>
                      <div
                        style={{
                          width: 64, height: 64, borderRadius: '50%',
                          background: CAT_COLOR[cat] || '#607d8b',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          margin: '0 auto',
                        }}
                      >
                        <span style={{ color: '#fff', fontWeight: 700 }}>{pct}%</span>
                      </div>
                      <div style={{ fontSize: '0.8rem', marginTop: '0.4rem', maxWidth: 72, textAlign: 'center' }}>{cat}</div>
                    </div>
                  ))}
              </div>
            </CardBody>
          </Card>

          {/* Behavior alignment table */}
          {data.behaviors.map((b) => (
            <Card key={b.id} style={{ marginBottom: '1rem' }}>
              <CardHeader>
                <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
                  <strong>#{b.rank} {b.name}</strong>
                  {ELIGIBLE_BADGE(b.ss4aEligible)}
                  {b.ss4aCategories.map((cat) => (
                    <span
                      key={cat}
                      style={{
                        background: CAT_COLOR[cat] || '#607d8b',
                        color: '#fff', borderRadius: 4, padding: '2px 8px', fontSize: '0.75rem',
                      }}
                    >
                      {cat}
                    </span>
                  ))}
                </div>
              </CardHeader>
              <CardBody>
                <div style={{ display: 'flex', gap: '3rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
                  <div>
                    <span style={{ color: '#555', fontSize: '0.85rem' }}>Fatal Crashes: </span>
                    <strong>{b.crashes.toLocaleString()}</strong>
                    <span style={{ color: '#888', fontSize: '0.85rem' }}> ({b.pctCrashes.toFixed(1)}%)</span>
                  </div>
                  <div>
                    <span style={{ color: '#555', fontSize: '0.85rem' }}>Project Type: </span>
                    <strong>{b.projectType}</strong>
                  </div>
                  <div>
                    <span style={{ color: '#555', fontSize: '0.85rem' }}>Programs: </span>
                    <strong>{b.programs.join(', ')}</strong>
                  </div>
                </div>
                <div style={{ fontSize: '0.9rem', color: '#444', borderLeft: '3px solid #90caf9', paddingLeft: '0.75rem' }}>
                  {b.strategy}
                </div>
              </CardBody>
            </Card>
          ))}
        </>
      )}
    </div>
  );
}
