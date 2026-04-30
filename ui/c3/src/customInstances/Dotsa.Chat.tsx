import React, { useState, useRef, useEffect } from 'react';
import { Button } from '@progress/kendo-react-buttons';
import { Input } from '@progress/kendo-react-inputs';

interface Citation { source: string; year: number | string; field: string; value: string; note?: string; }
interface Message {
  role: 'user' | 'bot';
  text: string;
  intent?: string;
  explanation?: string;
  citations?: Citation[];
  suggestedQuestions?: string[];
  showMethod?: boolean;
}

const STARTERS = [
  'What are the top safety issues in Texas?',
  'How does California compare to the national average?',
  'Which counties have the most alcohol-related crashes in Florida?',
  'Is speeding getting better or worse in Ohio?',
  'What countermeasures are recommended for distracted driving?',
];

export default function DotsaChat() {
  const [messages, setMessages]   = useState<Message[]>([]);
  const [input, setInput]         = useState('');
  const [loading, setLoading]     = useState(false);
  const bottomRef                 = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = async (query: string) => {
    if (!query.trim() || loading) return;
    const userMsg: Message = { role: 'user', text: query };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);
    try {
      const result = await c3Action('DotSafetyChat', 'chat', [query, null]);
      const botMsg: Message = {
        role: 'bot',
        text: result?.answer || 'No response.',
        intent: result?.intent,
        explanation: result?.explanation,
        citations: result?.citations,
        suggestedQuestions: result?.suggestedQuestions,
        showMethod: false,
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (e) {
      setMessages((prev) => [...prev, { role: 'bot', text: 'Error: could not reach the analytics service.' }]);
    } finally {
      setLoading(false);
    }
  };

  const toggleMethod = (idx: number) => {
    setMessages((prev) =>
      prev.map((m, i) => (i === idx ? { ...m, showMethod: !m.showMethod } : m))
    );
  };

  return (
    <div className="c3-kendo-wrapper" style={{ display: 'flex', flexDirection: 'column', height: '80vh', padding: '1rem' }}>
      {/* Starter prompts */}
      {messages.length === 0 && (
        <div style={{ marginBottom: '1rem' }}>
          <div style={{ color: '#666', marginBottom: '0.5rem', fontSize: '0.85rem' }}>Try asking:</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            {STARTERS.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                style={{
                  background: '#f0f4ff', border: '1px solid #c5cae9', borderRadius: 16,
                  padding: '4px 12px', cursor: 'pointer', fontSize: '0.85rem',
                }}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Message thread */}
      <div style={{ flex: 1, overflowY: 'auto', marginBottom: '1rem' }}>
        {messages.map((msg, idx) => (
          <div
            key={idx}
            style={{
              display: 'flex',
              justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
              marginBottom: '0.75rem',
            }}
          >
            <div
              style={{
                maxWidth: '75%',
                background: msg.role === 'user' ? '#1976d2' : '#f5f5f5',
                color: msg.role === 'user' ? '#fff' : '#222',
                borderRadius: 12,
                padding: '0.75rem 1rem',
              }}
            >
              <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>{msg.text}</div>

              {msg.role === 'bot' && (
                <>
                  {msg.explanation && (
                    <div style={{ marginTop: '0.5rem' }}>
                      <button
                        onClick={() => toggleMethod(idx)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#555', fontSize: '0.8rem', padding: 0 }}
                      >
                        {msg.showMethod ? '▾' : '▸'} How we calculated this
                      </button>
                      {msg.showMethod && (
                        <div style={{ marginTop: '0.4rem', fontSize: '0.82rem', color: '#444', borderLeft: '3px solid #90caf9', paddingLeft: '0.5rem' }}>
                          {msg.explanation}
                        </div>
                      )}
                    </div>
                  )}

                  {msg.citations && msg.citations.length > 0 && (
                    <details style={{ marginTop: '0.4rem', fontSize: '0.8rem' }}>
                      <summary style={{ cursor: 'pointer', color: '#555' }}>Sources ({msg.citations.length})</summary>
                      <ul style={{ marginTop: '0.3rem', paddingLeft: '1rem', color: '#555' }}>
                        {msg.citations.map((c, ci) => (
                          <li key={ci}><strong>{c.source}</strong> — {c.field}: {c.value}{c.note ? ` (${c.note})` : ''}</li>
                        ))}
                      </ul>
                    </details>
                  )}

                  {msg.suggestedQuestions && msg.suggestedQuestions.length > 0 && (
                    <div style={{ marginTop: '0.6rem', display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                      {msg.suggestedQuestions.map((q) => (
                        <button
                          key={q}
                          onClick={() => send(q)}
                          style={{
                            background: '#e3f2fd', border: '1px solid #90caf9', borderRadius: 12,
                            padding: '2px 10px', cursor: 'pointer', fontSize: '0.78rem',
                          }}
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  )}

                  <div style={{ marginTop: '0.4rem', fontSize: '0.75rem', color: '#999' }}>
                    Correlation does not imply causation · Source: NHTSA FARS
                  </div>
                </>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ color: '#888', fontStyle: 'italic', padding: '0.5rem' }}>Analyzing…</div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        <Input
          value={input}
          onChange={(e) => setInput(e.value as string)}
          onKeyDown={(e) => { if (e.key === 'Enter') send(input); }}
          placeholder="Ask about crash data, trends, or countermeasures…"
          style={{ flex: 1 }}
        />
        <Button themeColor="primary" onClick={() => send(input)} disabled={loading || !input.trim()}>
          Send
        </Button>
      </div>
    </div>
  );
}
