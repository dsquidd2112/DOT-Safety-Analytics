import React, { useState, useEffect, useCallback } from 'react';
import { DropDownList, DropDownListChangeEvent } from '@progress/kendo-react-dropdowns';
import { Card, CardHeader, CardBody } from '@progress/kendo-react-layout';
import { Button } from '@progress/kendo-react-buttons';

interface StateOption { fips: string; name: string; abbr: string; }

interface DefectRow {
  make: string;
  model: string;
  modelYear: number;
  fatalCrashes: number;
  recalls: number;
  investigations: number;
  tsbs: number;
  complaints: number;
  ncapOverall: number | null;
  sgoIncidents: number;
}

interface VehicleProfile {
  make: string;
  model: string;
  modelYear: number;
  fatalCrashes: number;
  ratings: any[];
  investigations: any[];
  recalls: any[];
  tsbs: any[];
  complaintCount: number;
  complaints: any[];
  sgo: any[];
}

interface SgoSummary {
  level: string | null;
  totals: { total: number; ads: number; adas: number; other: number };
  topEntities: { reportingEntity: string; n: number }[];
  topMakes:    { make: string; n: number }[];
  note: string;
}

const YEARS = [2024, 2023, 2022, 2021];
const SGO_LEVELS = ['ALL', 'ADS', 'ADAS', 'OTHER'];

export default function DotsaVehicleDefects() {
  const [view, setView] = useState<'defects' | 'sgo'>('defects');
  const [states, setStates] = useState<StateOption[]>([]);
  const [selectedState, setSelectedState] = useState<StateOption | null>(null);
  const [selectedYear, setSelectedYear] = useState<number>(2024);

  const [rows, setRows] = useState<DefectRow[] | null>(null);
  const [picked, setPicked] = useState<DefectRow | null>(null);
  const [profile, setProfile] = useState<VehicleProfile | null>(null);
  const [loading, setLoading] = useState(false);

  const [sgoLevel, setSgoLevel] = useState<string>('ALL');
  const [sgo, setSgo] = useState<SgoSummary | null>(null);

  // Load states once
  useEffect(() => {
    c3Action('StateRef', 'getAll', []).then((result: StateOption[]) => {
      setStates(result || []);
      const tx = (result || []).find((s) => s.fips === '48');
      if (tx) setSelectedState(tx);
    });
  }, []);

  // Defects view: load top MMMYs
  const loadDefects = useCallback(async () => {
    if (!selectedState) return;
    setLoading(true);
    setRows(null);
    setPicked(null);
    setProfile(null);
    try {
      const r = await c3Action(
        'DotSafetyVehicleDefects',
        'topDefectVehicles',
        [selectedState.fips, selectedYear, 30],
      );
      setRows(r?.rows || []);
    } finally {
      setLoading(false);
    }
  }, [selectedState, selectedYear]);

  useEffect(() => { if (view === 'defects') loadDefects(); }, [view, loadDefects]);

  // Profile lookup on row pick
  useEffect(() => {
    if (!picked) return;
    setProfile(null);
    c3Action(
      'DotSafetyVehicleDefects',
      'vehicleProfile',
      [picked.make, picked.model, picked.modelYear],
    ).then(setProfile);
  }, [picked]);

  // SGO summary
  useEffect(() => {
    if (view !== 'sgo') return;
    setSgo(null);
    c3Action(
      'DotSafetyVehicleDefects',
      'sgoSummary',
      [sgoLevel === 'ALL' ? null : sgoLevel],
    ).then(setSgo);
  }, [view, sgoLevel]);

  const stateItems = states.map((s) => ({ text: s.name, value: s }));
  const yearItems  = YEARS.map((y) => ({ text: String(y), value: y }));

  return (
    <div className="c3-kendo-wrapper" style={{ padding: '1.5rem' }}>
      {/* Sub-toggle + state/year picker */}
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <Button
          themeColor={view === 'defects' ? 'primary' : 'base'}
          onClick={() => setView('defects')}>
          Vehicle Defects (FARS-linked)
        </Button>
        <Button
          themeColor={view === 'sgo' ? 'primary' : 'base'}
          onClick={() => setView('sgo')}>
          Automated Vehicle Incidents (SGO)
        </Button>
        <span style={{ flex: 1 }} />
        {view === 'defects' && (
          <>
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
          </>
        )}
      </div>

      {view === 'defects' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.6fr) minmax(0, 1fr)', gap: '1rem' }}>
          <Card>
            <CardHeader>
              <strong>Top vehicles in fatal crashes — {selectedState?.name || 'National'} · {selectedYear}</strong>
              <div style={{ fontSize: '0.75rem', color: '#666', marginTop: 4 }}>
                Joined to NHTSA Recalls, Investigations, TSBs, Complaints, NCAP, and SGO via vPIC-canonical MMMY.
              </div>
            </CardHeader>
            <CardBody>
              {loading && <div>Loading…</div>}
              {!loading && rows && rows.length === 0 && (
                <div style={{ color: '#666' }}>No FARS-fatal vehicles meeting the threshold for this state/year.</div>
              )}
              {!loading && rows && rows.length > 0 && (
                <div style={{ maxHeight: 540, overflow: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                    <thead>
                      <tr>
                        {['Make', 'Model', 'Yr', 'Crashes', 'Recalls', 'Investig.', 'TSBs', 'Cmplts', 'NCAP', 'SGO'].map((h) => (
                          <th key={h} style={{ textAlign: ['Make', 'Model'].includes(h) ? 'left' : 'right', padding: '0.4rem 0.5rem', borderBottom: '1px solid #ddd' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((r, i) => {
                        const isPicked = picked && picked.make === r.make && picked.model === r.model && picked.modelYear === r.modelYear;
                        return (
                          <tr key={i}
                              onClick={() => setPicked(r)}
                              style={{ cursor: 'pointer', background: isPicked ? '#e0f2fe' : undefined }}>
                            <td style={{ padding: '0.3rem 0.5rem' }}>{r.make}</td>
                            <td style={{ padding: '0.3rem 0.5rem' }}>{r.model}</td>
                            <td style={{ padding: '0.3rem 0.5rem', textAlign: 'right' }}>{r.modelYear}</td>
                            <td style={{ padding: '0.3rem 0.5rem', textAlign: 'right', fontWeight: 600 }}>{r.fatalCrashes}</td>
                            <td style={{ padding: '0.3rem 0.5rem', textAlign: 'right', color: r.recalls > 0 ? '#b91c1c' : '#999' }}>{r.recalls || '—'}</td>
                            <td style={{ padding: '0.3rem 0.5rem', textAlign: 'right', color: r.investigations > 0 ? '#b45309' : '#999' }}>{r.investigations || '—'}</td>
                            <td style={{ padding: '0.3rem 0.5rem', textAlign: 'right', color: r.tsbs > 0 ? '#0c4a6e' : '#999' }}>{r.tsbs || '—'}</td>
                            <td style={{ padding: '0.3rem 0.5rem', textAlign: 'right', color: r.complaints > 0 ? '#7c3aed' : '#999' }}>{r.complaints ? r.complaints.toLocaleString() : '—'}</td>
                            <td style={{ padding: '0.3rem 0.5rem', textAlign: 'right', color: r.ncapOverall != null ? '#06A7E0' : '#999' }}>{r.ncapOverall != null ? `${r.ncapOverall}★` : '—'}</td>
                            <td style={{ padding: '0.3rem 0.5rem', textAlign: 'right', color: r.sgoIncidents > 0 ? '#b91c1c' : '#999' }}>{r.sgoIncidents || '—'}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <strong>{picked ? `${picked.make} ${picked.model} · ${picked.modelYear}` : 'Vehicle detail'}</strong>
              <div style={{ fontSize: '0.75rem', color: '#666', marginTop: 4 }}>
                {picked ? 'NHTSA records joined on canonical MMMY' : 'Click a vehicle on the left'}
              </div>
            </CardHeader>
            <CardBody style={{ maxHeight: 540, overflow: 'auto' }}>
              {!picked && <div style={{ color: '#666' }}>Select a vehicle from the table.</div>}
              {picked && !profile && <div style={{ color: '#666' }}>Loading…</div>}
              {profile && (
                <div style={{ fontSize: 12 }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6, marginBottom: 12 }}>
                    {[
                      { label: 'Crashes',    value: profile.fatalCrashes.toLocaleString(), color: '#222'    },
                      { label: 'Recalls',    value: profile.recalls.length,                color: '#b91c1c' },
                      { label: 'Investig.',  value: profile.investigations.length,         color: '#b45309' },
                      { label: 'TSBs',       value: profile.tsbs.length,                   color: '#0c4a6e' },
                      { label: 'Complaints', value: (profile.complaintCount || 0).toLocaleString(), color: '#7c3aed' },
                    ].map((kpi) => (
                      <div key={kpi.label} style={{ padding: '8px', background: '#f8fafc', borderRadius: 6 }}>
                        <div style={{ fontSize: 10, color: '#666' }}>{kpi.label}</div>
                        <div style={{ fontSize: 16, fontWeight: 600, color: kpi.color }}>{kpi.value}</div>
                      </div>
                    ))}
                  </div>

                  {profile.ratings.length > 0 && (
                    <SectionList
                      title="NCAP Safety Ratings"
                      titleColor="#06A7E0"
                      items={profile.ratings.slice(0, 3).map((r: any, i: number) => ({
                        key: `r${i}`,
                        primary: `${r.bodyStyle || '—'} · Overall ${r.overallStars ?? '—'}★`,
                        secondary: `Frontal-D ${r.frntDrivStars ?? '—'}★ · Side-D ${r.sideDrivStars ?? '—'}★ · Rollover ${r.rolloverStars ?? '—'}★`,
                      }))}
                    />
                  )}

                  {profile.recalls.length > 0 && (
                    <SectionList
                      title="NHTSA Recall Campaigns"
                      titleColor="#b91c1c"
                      items={profile.recalls.slice(0, 8).map((rcl: any, i: number) => ({
                        key: rcl.nhtsaId || `rc${i}`,
                        primary: rcl.nhtsaId,
                        secondary: rcl.summary?.slice(0, 240),
                      }))}
                    />
                  )}

                  {profile.investigations.length > 0 && (
                    <SectionList
                      title="NHTSA Defect Investigations"
                      titleColor="#b45309"
                      items={profile.investigations.slice(0, 8).map((inv: any, i: number) => ({
                        key: inv.nhtsaActionNumber || `i${i}`,
                        primary: `${inv.nhtsaActionNumber} · ${inv.subject || '(no subject)'} ${inv.closeDate ? `(closed ${inv.closeDate})` : '(OPEN)'}${inv.campNo ? ` → recall ${inv.campNo}` : ''}`,
                        secondary: `Component: ${inv.compName} — ${(inv.summary || '').slice(0, 200)}`,
                      }))}
                    />
                  )}

                  {profile.tsbs.length > 0 && (
                    <SectionList
                      title="Manufacturer Service Bulletins"
                      titleColor="#0c4a6e"
                      items={profile.tsbs.slice(0, 8).map((t: any, i: number) => ({
                        key: t.nhtsaId || `t${i}`,
                        primary: `${t.tsbDocId || t.nhtsaId} · ${t.commType} · ${t.commDate}`,
                        secondary: `${t.components || ''} — ${(t.summary || '').slice(0, 180)}`,
                      }))}
                    />
                  )}

                  {profile.complaints && profile.complaints.length > 0 && (
                    <SectionList
                      title={`Consumer Complaints${profile.complaintCount > profile.complaints.length ? ` (showing ${profile.complaints.length} of ${profile.complaintCount.toLocaleString()})` : ''}`}
                      titleColor="#7c3aed"
                      items={profile.complaints.slice(0, 8).map((c: any, i: number) => ({
                        key: c.cmplid || `c${i}`,
                        primary: `[${c.cmplid}] ${c.recvDate} · ${c.state || '—'} · ${c.compDesc || ''}${c.crash ? ' · CRASH' : ''}${c.fire ? ' · FIRE' : ''}${c.deaths ? ` · ${c.deaths} fatalities` : ''}`,
                        secondary: (c.narrative || '').slice(0, 220),
                      }))}
                    />
                  )}
                </div>
              )}
            </CardBody>
          </Card>
        </div>
      )}

      {view === 'sgo' && (
        <div>
          <div style={{ marginBottom: '1rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <span style={{ fontSize: 12, color: '#666' }}>Filter:</span>
            {SGO_LEVELS.map((l) => (
              <Button key={l} size="small"
                themeColor={sgoLevel === l ? 'primary' : 'base'}
                onClick={() => setSgoLevel(l)}>{l}</Button>
            ))}
            <span style={{ flex: 1 }} />
            <span style={{ fontSize: 11, color: '#666' }}>SGO is national, all dates · siloed from FARS by design</span>
          </div>

          {!sgo && <div>Loading…</div>}
          {sgo && (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '1rem' }}>
                {[
                  { label: 'Total incidents',       value: sgo.totals.total },
                  { label: 'ADS (driverless)',      value: sgo.totals.ads },
                  { label: 'ADAS (Level 2)',        value: sgo.totals.adas },
                  { label: 'Other',                 value: sgo.totals.other },
                ].map((kpi) => (
                  <Card key={kpi.label}>
                    <CardHeader><strong>{kpi.label}</strong></CardHeader>
                    <CardBody><span style={{ fontSize: '1.6rem', fontWeight: 700 }}>{kpi.value.toLocaleString()}</span></CardBody>
                  </Card>
                ))}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <SimpleTable
                  title="Top reporting entities"
                  rows={sgo.topEntities.map((e) => [e.reportingEntity || '—', e.n.toLocaleString()])}
                  headers={['Reporting Entity', 'Reports']}
                />
                <SimpleTable
                  title="Top makes"
                  rows={sgo.topMakes.map((m) => [m.make || '—', m.n.toLocaleString()])}
                  headers={['Make', 'Reports']}
                />
              </div>

              <div style={{ marginTop: '1rem', fontSize: 11, color: '#666', fontStyle: 'italic' }}>{sgo.note}</div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ─── helper sub-components ──────────────────────────────────────────────────
function SectionList({ title, titleColor, items }: { title: string; titleColor: string; items: { key: string | number; primary: string; secondary?: string }[] }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: titleColor }}>{title}</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {items.map((it) => (
          <div key={it.key} style={{ padding: 8, border: '1px solid #ddd', borderRadius: 4, fontSize: 11 }}>
            <div style={{ fontWeight: 500, marginBottom: 2 }}>{it.primary}</div>
            {it.secondary && <div style={{ color: '#555', lineHeight: 1.4 }}>{it.secondary}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

function SimpleTable({ title, headers, rows }: { title: string; headers: string[]; rows: (string | number)[][] }) {
  return (
    <Card>
      <CardHeader><strong>{title}</strong></CardHeader>
      <CardBody>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr>{headers.map((h) => (
              <th key={h} style={{ textAlign: 'left', padding: '0.4rem 0.5rem', borderBottom: '1px solid #ddd' }}>{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {r.map((c, j) => (
                  <td key={j} style={{ padding: '0.3rem 0.5rem', textAlign: j === 0 ? 'left' : 'right' }}>{c}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </CardBody>
    </Card>
  );
}
