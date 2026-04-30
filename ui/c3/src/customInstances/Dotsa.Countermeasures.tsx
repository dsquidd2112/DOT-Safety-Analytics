import React, { useState, useEffect, useCallback } from 'react';
import { DropDownList, DropDownListChangeEvent } from '@progress/kendo-react-dropdowns';
import { Card, CardHeader, CardBody } from '@progress/kendo-react-layout';
import { Button } from '@progress/kendo-react-buttons';

interface StateOption { fips: string; name: string; abbr: string; }
interface CMItem {
  id: string; title: string; summary: string; evidenceLevel: string;
  effectivenessNote: string; programType: string; chapter: string; resourceUrl: string;
}
interface BehaviorRec { behaviorId: string; countermeasures: CMItem[]; }

const EVIDENCE_LEVELS = [
  { text: 'All Evidence', value: null },
  { text: 'High',         value: 'high' },
  { text: 'Moderate+',    value: 'moderate' },
];
const PROGRAM_TYPES = [
  { text: 'All Programs', value: null },
  { text: '402',   value: '402' },
  { text: '405b',  value: '405b' },
  { text: '405d',  value: '405d' },
  { text: '405h',  value: '405h' },
  { text: 'HSIP',  value: 'HSIP' },
];
const YEARS = [2024, 2023, 2022, 2021];

const BADGE_COLOR: Record<string, string> = {
  high:     '#2e7d32',
  moderate: '#f57c00',
  low:      '#c62828',
};

export default function DotsaCountermeasures() {
  const [states, setStates]       = useState<StateOption[]>([]);
  const [selected, setSelected]   = useState<StateOption | null>(null);
  const [year, setYear]           = useState(2024);
  const [evidence, setEvidence]   = useState<string | null>(null);
  const [program, setProgram]     = useState<string | null>(null);
  const [recs, setRecs]           = useState<BehaviorRec[]>([]);
  const [summaries, setSummaries] = useState<Record<string, string>>({});
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
      const result: BehaviorRec[] = await c3Action('DotSafetyCountermeasures', 'getRecommendations',
        [selected.fips, year, null, evidence, program, null]);
      setRecs(result || []);
      setSummaries({});
    } finally {
      setLoading(false);
    }
  }, [selected, year, evidence, program]);

  useEffect(() => { load(); }, [load]);

  const loadSummary = useCallback(async (bid: string) => {
    if (!selected || summaries[bid]) return;
    const s: string = await c3Action('DotSafetyCountermeasures', 'getBehaviorSummary',
      [selected.fips, year, bid]);
    if (s) setSummaries((prev) => ({ ...prev, [bid]: s }));
  }, [selected, year, summaries]);

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
          data={EVIDENCE_LEVELS} textField="text" dataItemKey="value"
          value={EVIDENCE_LEVELS.find((e) => e.value === evidence) || EVIDENCE_LEVELS[0]}
          onChange={(e: DropDownListChangeEvent) => setEvidence(e.value.value)}
          style={{ width: 140 }}
        />
        <DropDownList
          data={PROGRAM_TYPES} textField="text" dataItemKey="value"
          value={PROGRAM_TYPES.find((p) => p.value === program) || PROGRAM_TYPES[0]}
          onChange={(e: DropDownListChangeEvent) => setProgram(e.value.value)}
          style={{ width: 140 }}
        />
      </div>

      {loading && <div>Loading…</div>}

      {!loading && recs.map((rec) => (
        <Card key={rec.behaviorId} style={{ marginBottom: '1.5rem' }}>
          <CardHeader>
            <strong style={{ textTransform: 'capitalize' }}>
              {rec.behaviorId.replace(/_/g, ' ')}
            </strong>
            <Button
              fillMode="flat"
              style={{ marginLeft: 'auto', fontSize: '0.8rem' }}
              onClick={() => loadSummary(rec.behaviorId)}
            >
              AI Summary
            </Button>
          </CardHeader>
          <CardBody>
            {summaries[rec.behaviorId] && (
              <div style={{
                background: '#f0f7ff', borderLeft: '3px solid #1976d2',
                padding: '0.75rem', marginBottom: '1rem', borderRadius: 4,
              }}>
                {summaries[rec.behaviorId]}
              </div>
            )}
            {rec.countermeasures.length === 0 && (
              <div style={{ color: '#888' }}>No countermeasures match the selected filters.</div>
            )}
            {rec.countermeasures.map((cm) => (
              <div key={cm.id} style={{ borderBottom: '1px solid #eee', paddingBottom: '1rem', marginBottom: '1rem' }}>
                <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'baseline', marginBottom: '0.25rem' }}>
                  <strong>{cm.title}</strong>
                  <span style={{
                    background: BADGE_COLOR[cm.evidenceLevel] || '#666',
                    color: '#fff', borderRadius: 4, padding: '1px 6px', fontSize: '0.75rem',
                  }}>
                    {cm.evidenceLevel}
                  </span>
                  <span style={{ fontSize: '0.8rem', color: '#555' }}>§{cm.programType}</span>
                </div>
                <p style={{ margin: '0 0 0.4rem', color: '#444', fontSize: '0.9rem' }}>{cm.summary}</p>
                {cm.effectivenessNote && (
                  <div style={{ fontSize: '0.8rem', color: '#555', fontStyle: 'italic' }}>{cm.effectivenessNote}</div>
                )}
                {cm.resourceUrl && (
                  <a href={cm.resourceUrl} target="_blank" rel="noreferrer" style={{ fontSize: '0.8rem' }}>NHTSA Reference →</a>
                )}
              </div>
            ))}
          </CardBody>
        </Card>
      ))}
    </div>
  );
}
