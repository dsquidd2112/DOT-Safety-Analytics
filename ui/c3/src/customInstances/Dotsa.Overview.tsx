import React, { useState, useEffect, useCallback } from 'react';
import { DropDownList, DropDownListChangeEvent } from '@progress/kendo-react-dropdowns';
import { Card, CardHeader, CardBody } from '@progress/kendo-react-layout';

interface StateOption {
  fips: string;
  name: string;
  abbr: string;
}

interface BehaviorItem {
  id: string;
  name: string;
  crashes: number;
  fatals: number;
  pctCrashes: number;
  rank: number;
  trend: string;
  trendPct: number | null;
}

interface AnalysisData {
  stateFips: string;
  year: number;
  totalCrashes: number;
  totalFatals: number;
  behaviors: BehaviorItem[];
  allBehaviors: BehaviorItem[];
}

interface BenchmarkData {
  ratePer100k: number | null;
  ratePerVmt: number | null;
  vsNationalPct: number | null;
  rank100k: number | null;
}

const YEARS = [2024, 2023, 2022, 2021];

const trendIcon = (t: string) =>
  t === 'increasing' ? '▲' : t === 'decreasing' ? '▼' : t === 'stable' ? '→' : '–';

export default function DotsaOverview() {
  const [states, setStates] = useState<StateOption[]>([]);
  const [selectedState, setSelectedState] = useState<StateOption | null>(null);
  const [selectedYear, setSelectedYear] = useState<number>(2024);
  const [analysis, setAnalysis] = useState<AnalysisData | null>(null);
  const [benchmark, setBenchmark] = useState<BenchmarkData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    c3Action('StateRef', 'getAll', []).then((result: StateOption[]) => {
      setStates(result || []);
      const tx = (result || []).find((s) => s.fips === '48');
      if (tx) setSelectedState(tx);
    });
  }, []);

  const load = useCallback(async () => {
    if (!selectedState) return;
    setLoading(true);
    setError(null);
    try {
      const [a, b] = await Promise.all([
        c3Action('DotSafetyBehavioral', 'getStateAnalysis', [selectedState.fips, selectedYear, 3, null]),
        c3Action('DotSafetyBenchmark', 'getStateBenchmark', [selectedState.fips, selectedYear, null]),
      ]);
      setAnalysis(a);
      setBenchmark(b);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [selectedState, selectedYear]);

  useEffect(() => { load(); }, [load]);

  const stateItems = states.map((s) => ({ text: s.name, value: s }));
  const yearItems  = YEARS.map((y) => ({ text: String(y), value: y }));

  return (
    <div className="c3-kendo-wrapper" style={{ padding: '1.5rem' }}>
      {/* Controls */}
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', alignItems: 'center' }}>
        <DropDownList
          data={stateItems}
          textField="text"
          dataItemKey="value"
          value={stateItems.find((i) => i.value?.fips === selectedState?.fips) || null}
          onChange={(e: DropDownListChangeEvent) => setSelectedState(e.value.value)}
          style={{ width: 220 }}
        />
        <DropDownList
          data={yearItems}
          textField="text"
          dataItemKey="value"
          value={yearItems.find((i) => i.value === selectedYear) || null}
          onChange={(e: DropDownListChangeEvent) => setSelectedYear(e.value.value)}
          style={{ width: 100 }}
        />
      </div>

      {error && <div style={{ color: 'red', marginBottom: '1rem' }}>{error}</div>}
      {loading && <div>Loading…</div>}

      {!loading && analysis && benchmark && (
        <>
          {/* KPI Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
            {[
              { label: 'Fatal Crashes', value: analysis.totalCrashes.toLocaleString() },
              { label: 'Fatalities', value: analysis.totalFatals.toLocaleString() },
              { label: 'Rate / 100K Pop', value: benchmark.ratePer100k != null ? benchmark.ratePer100k.toFixed(2) : '–' },
              { label: 'vs National', value: benchmark.vsNationalPct != null ? `${benchmark.vsNationalPct > 0 ? '+' : ''}${benchmark.vsNationalPct.toFixed(1)}%` : '–' },
            ].map((kpi) => (
              <Card key={kpi.label}>
                <CardHeader><strong>{kpi.label}</strong></CardHeader>
                <CardBody><span style={{ fontSize: '1.6rem', fontWeight: 700 }}>{kpi.value}</span></CardBody>
              </Card>
            ))}
          </div>

          {/* Top Behaviors */}
          <Card>
            <CardHeader><strong>Top Behavioral Contributors</strong></CardHeader>
            <CardBody>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    {['Rank', 'Behavior', 'Fatal Crashes', '% of Total', 'Trend'].map((h) => (
                      <th key={h} style={{ textAlign: 'left', padding: '0.5rem', borderBottom: '1px solid #ddd' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {analysis.allBehaviors.slice(0, 9).map((b) => (
                    <tr key={b.id}>
                      <td style={{ padding: '0.4rem 0.5rem' }}>#{b.rank}</td>
                      <td style={{ padding: '0.4rem 0.5rem' }}>{b.name}</td>
                      <td style={{ padding: '0.4rem 0.5rem' }}>{b.crashes.toLocaleString()}</td>
                      <td style={{ padding: '0.4rem 0.5rem' }}>{b.pctCrashes.toFixed(1)}%</td>
                      <td style={{ padding: '0.4rem 0.5rem' }}>
                        {trendIcon(b.trend)}{' '}
                        {b.trendPct != null ? `${b.trendPct > 0 ? '+' : ''}${b.trendPct}%` : ''}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardBody>
          </Card>
        </>
      )}
    </div>
  );
}
