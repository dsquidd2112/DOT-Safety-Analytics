import React, { useState, useEffect, useCallback } from 'react';
import { DropDownList, DropDownListChangeEvent } from '@progress/kendo-react-dropdowns';
import { Card, CardHeader, CardBody } from '@progress/kendo-react-layout';
import { Grid, GridColumn } from '@progress/kendo-react-grid';

interface StateOption { fips: string; name: string; abbr: string; }

interface HeatCell { crashes: number; fatals: number; sig: boolean; z: number; }
interface HourRow  { hour: number; label: string; crashes: number; fatals: number; }
interface DowRow   { dow: number; label: string; crashes: number; fatals: number; }
interface Window   { startLabel: string; endLabel: string; crashes: number; }
interface SigWin   { dowLabel: string; hourLabel: string; crashes: number; z: number; }
interface LocationRow { name: string; crashes: number; fatals: number; }

interface EnforcementData {
  totalCrashes: number; totalFatals: number;
  byHour: HourRow[]; byDow: DowRow[]; heatmap: HeatCell[][];
  bestWindow: Window; nightPct: number; sigWindows: SigWin[];
}

const BEHAVIORS = [
  { text: 'All Behaviors', value: null },
  { text: 'Alcohol', value: 'alcohol' },
  { text: 'Speeding', value: 'speeding' },
  { text: 'Distracted Driving', value: 'distracted_driving' },
  { text: 'Drowsy Driving', value: 'drowsy_driving' },
  { text: 'Pedestrian', value: 'pedestrian_fatality' },
  { text: 'Wrong Way', value: 'wrong_way' },
  { text: 'Hit-and-Run', value: 'hit_run' },
];
const YEARS  = [2024, 2023, 2022, 2021];
const DAYS   = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];

function heatColor(crashes: number, max: number) {
  if (max === 0 || crashes === 0) return '#f5f5f5';
  const ratio = crashes / max;
  const r = Math.round(255 * ratio);
  const g = Math.round(255 * (1 - ratio * 0.8));
  return `rgb(${r},${g},60)`;
}

export default function DotsaEnforcement() {
  const [states, setStates]       = useState<StateOption[]>([]);
  const [selected, setSelected]   = useState<StateOption | null>(null);
  const [year, setYear]           = useState(2024);
  const [behavior, setBehavior]   = useState<string | null>(null);
  const [data, setData]           = useState<EnforcementData | null>(null);
  const [locations, setLocations] = useState<{ counties: LocationRow[]; cities: LocationRow[] } | null>(null);
  const [loading, setLoading]     = useState(false);

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
      const [d, l] = await Promise.all([
        c3Action('DotSafetyEnforcement', 'getEnforcementWindows', [selected.fips, year, behavior, null, null]),
        c3Action('DotSafetyEnforcement', 'getLocationBreakdown',  [selected.fips, year, behavior, null, null, null, null, 15]),
      ]);
      setData(d);
      setLocations(l);
    } finally {
      setLoading(false);
    }
  }, [selected, year, behavior]);

  useEffect(() => { load(); }, [load]);

  const maxCrashes = data
    ? Math.max(...data.heatmap.flatMap((row) => row.map((c) => c.crashes)), 1)
    : 1;

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
          data={BEHAVIORS} textField="text" dataItemKey="value"
          value={BEHAVIORS.find((b) => b.value === behavior) || BEHAVIORS[0]}
          onChange={(e: DropDownListChangeEvent) => setBehavior(e.value.value)}
          style={{ width: 180 }}
        />
      </div>

      {loading && <div>Loading…</div>}

      {!loading && data && (
        <>
          {/* KPIs + best window */}
          <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
            <Card style={{ minWidth: 160 }}>
              <CardHeader><strong>Total Crashes</strong></CardHeader>
              <CardBody><span style={{ fontSize: '1.4rem', fontWeight: 700 }}>{data.totalCrashes.toLocaleString()}</span></CardBody>
            </Card>
            <Card style={{ minWidth: 160 }}>
              <CardHeader><strong>Night-time %</strong></CardHeader>
              <CardBody><span style={{ fontSize: '1.4rem', fontWeight: 700 }}>{data.nightPct}%</span></CardBody>
            </Card>
            <Card style={{ minWidth: 220 }}>
              <CardHeader><strong>Best 3-hr Enforcement Window</strong></CardHeader>
              <CardBody>
                {data.bestWindow.startLabel}–{data.bestWindow.endLabel}
                {' '}({data.bestWindow.crashes.toLocaleString()} crashes)
              </CardBody>
            </Card>
          </div>

          {/* Heatmap */}
          <Card style={{ marginBottom: '1.5rem', overflowX: 'auto' }}>
            <CardHeader><strong>Day × Hour Heatmap</strong></CardHeader>
            <CardBody>
              <table style={{ borderCollapse: 'collapse', fontSize: '0.75rem' }}>
                <thead>
                  <tr>
                    <th style={{ width: 40 }}></th>
                    {Array.from({ length: 24 }, (_, h) => (
                      <th key={h} style={{ width: 28, textAlign: 'center', padding: '2px' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {DAYS.map((day, di) => (
                    <tr key={day}>
                      <td style={{ fontWeight: 600, paddingRight: 8 }}>{day}</td>
                      {data.heatmap[di].map((cell, h) => (
                        <td
                          key={h}
                          title={`${day} ${h}:00 — ${cell.crashes} crashes${cell.sig ? ' ★' : ''}`}
                          style={{
                            background: heatColor(cell.crashes, maxCrashes),
                            border: cell.sig ? '1px solid #333' : '1px solid #eee',
                            width: 28, height: 22, textAlign: 'center',
                          }}
                        />
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardBody>
          </Card>

          {/* Location breakdown */}
          {locations && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <Card>
                <CardHeader><strong>Top Counties</strong></CardHeader>
                <CardBody>
                  <Grid data={locations.counties} style={{ height: 300 }}>
                    <GridColumn field="name"    title="County"     />
                    <GridColumn field="crashes" title="Crashes" width={90} />
                    <GridColumn field="fatals"  title="Fatals"  width={80} />
                  </Grid>
                </CardBody>
              </Card>
              <Card>
                <CardHeader><strong>Top Cities</strong></CardHeader>
                <CardBody>
                  <Grid data={locations.cities} style={{ height: 300 }}>
                    <GridColumn field="name"    title="City"       />
                    <GridColumn field="crashes" title="Crashes" width={90} />
                    <GridColumn field="fatals"  title="Fatals"  width={80} />
                  </Grid>
                </CardBody>
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  );
}
