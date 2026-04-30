import React, { useState, useEffect, useCallback } from 'react';
import { DropDownList, DropDownListChangeEvent } from '@progress/kendo-react-dropdowns';
import { Card, CardHeader, CardBody } from '@progress/kendo-react-layout';
import { Button } from '@progress/kendo-react-buttons';

interface StateOption { fips: string; name: string; abbr: string; }
interface BehaviorItem {
  id: string; name: string; crashes: number; fatals: number;
  pctCrashes: number; rank: number; trend: string; trendPct: number | null;
  counties?: CountyRow[]; demographics?: Demographics;
}
interface CountyRow { name: string; fips: string; crashes: number; fatals: number; }
interface AgeRow    { segment: string; count: number; pct: number; }
interface Demographics { age: AgeRow[]; sex: AgeRow[]; personType: AgeRow[]; }
interface TrendPoint  { year: number; crashes: number; fatals: number; }
interface TrendResult {
  behaviorName: string; overallDirection: string; overallPctChange: number | null;
  trend: TrendPoint[];
}

const YEARS    = [2024, 2023, 2022, 2021];
const MONTHS   = [
  { text: 'All Months', value: null },
  ...['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    .map((m, i) => ({ text: m, value: i + 1 })),
];
const trendBadge = (t: string) =>
  ({ increasing: '▲ Increasing', decreasing: '▼ Decreasing', stable: '→ Stable', no_prior_data: '–' }[t] ?? '–');

export default function DotsaBehaviors() {
  const [states, setStates]           = useState<StateOption[]>([]);
  const [selected, setSelected]       = useState<StateOption | null>(null);
  const [year, setYear]               = useState(2024);
  const [month, setMonth]             = useState<number | null>(null);
  const [behaviors, setBehaviors]     = useState<BehaviorItem[]>([]);
  const [trendBid, setTrendBid]       = useState<string | null>(null);
  const [trendData, setTrendData]     = useState<TrendResult | null>(null);
  const [loading, setLoading]         = useState(false);

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
    try {
      const result = await c3Action('DotSafetyBehavioral', 'getStateAnalysis', [selected.fips, year, 3, month]);
      setBehaviors(result?.allBehaviors || []);
    } finally {
      setLoading(false);
    }
  }, [selected, year, month]);

  useEffect(() => { load(); }, [load]);

  const loadTrend = useCallback(async (bid: string) => {
    if (!selected) return;
    setTrendBid(bid);
    const r = await c3Action('DotSafetyBehavioral', 'getYoyTrend', [selected.fips, bid]);
    setTrendData(r);
  }, [selected]);

  const stateItems = states.map((s) => ({ text: s.name, value: s }));

  return (
    <div className="c3-kendo-wrapper" style={{ padding: '1.5rem' }}>
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
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
        <DropDownList
          data={MONTHS} textField="text" dataItemKey="value"
          value={MONTHS.find((m) => m.value === month) || MONTHS[0]}
          onChange={(e: DropDownListChangeEvent) => setMonth(e.value.value)}
          style={{ width: 130 }}
        />
      </div>

      {loading && <div>Loading…</div>}

      {!loading && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          {behaviors.map((b) => (
            <Card key={b.id}>
              <CardHeader>
                <strong>#{b.rank} {b.name}</strong>
                <span style={{ marginLeft: '1rem', color: '#666' }}>{trendBadge(b.trend)}</span>
              </CardHeader>
              <CardBody>
                <div style={{ display: 'flex', gap: '2rem', marginBottom: '0.75rem' }}>
                  <div><strong>{b.crashes.toLocaleString()}</strong> crashes ({b.pctCrashes.toFixed(1)}%)</div>
                  <div><strong>{b.fatals.toLocaleString()}</strong> fatalities</div>
                </div>
                {b.counties && b.counties.length > 0 && (
                  <div style={{ fontSize: '0.85rem', color: '#555' }}>
                    <strong>Top counties:</strong>{' '}
                    {b.counties.slice(0, 3).map((c) => `${c.name} (${c.fatals})`).join(', ')}
                  </div>
                )}
                <Button
                  fillMode="flat"
                  style={{ marginTop: '0.5rem', fontSize: '0.8rem' }}
                  onClick={() => loadTrend(b.id)}
                >
                  View trend →
                </Button>
              </CardBody>
            </Card>
          ))}
        </div>
      )}

      {trendData && (
        <Card style={{ marginTop: '2rem' }}>
          <CardHeader>
            <strong>{trendData.behaviorName} — Year-over-Year Trend</strong>
            <span style={{ marginLeft: '1rem', color: '#555' }}>
              {trendBadge(trendData.overallDirection)}
              {trendData.overallPctChange != null && ` (${trendData.overallPctChange > 0 ? '+' : ''}${trendData.overallPctChange}% overall)`}
            </span>
          </CardHeader>
          <CardBody>
            <div style={{ display: 'flex', gap: '2rem' }}>
              {trendData.trend.map((pt) => (
                <div key={pt.year} style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '1.4rem', fontWeight: 700 }}>{pt.crashes.toLocaleString()}</div>
                  <div style={{ color: '#666', fontSize: '0.85rem' }}>crashes</div>
                  <div style={{ fontWeight: 600 }}>{pt.year}</div>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
