'use client';

import { useState, useEffect, useRef } from 'react';
import { Flame, FlaskConical, Coffee, TriangleAlert as AlertTriangle, Brain, ExternalLink, ArrowRight, Clock, TrendingUp, BookOpen, Eye } from 'lucide-react';
import { api } from '@/lib/api';



// ── Helpers ───────────────────────────────────────────────────────────────
function SectionHeader({ icon: Icon, title, color, action, onAction }: {
  icon: React.ElementType; title: string; color: string; action?: string; onAction?: () => void;
}) {
  return (
    <div className="flex items-center justify-between mb-6">
      <div className="flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: color + '20' }}>
          <Icon size={14} style={{ color }} />
        </div>
        <h2 className="text-base font-bold text-white">{title}</h2>
      </div>
      {action && (
        <button
          onClick={onAction}
          className="flex items-center gap-1.5 text-xs transition-colors"
          style={{ color: '#555' }}
          onMouseEnter={e => ((e.currentTarget as HTMLButtonElement).style.color = color)}
          onMouseLeave={e => ((e.currentTarget as HTMLButtonElement).style.color = '#555')}
        >
          {action}<ArrowRight size={12} />
        </button>
      )}
    </div>
  );
}

// ── Live stats ticker — MELHORIA 10 ──────────────────────────────────────
function LiveTicker() {
  const items = [
    '↑ OSINT · +4 posts esta semana',
    '🔴 Voice Cloning · novo conteúdo',
    '↑ Threat Hunt · ativo agora',
    '↑ Deepfake · trending',
    '🔴 AI Security · novo',
  ];
  const [idx, setIdx] = useState(0);
  const [fade, setFade] = useState(false);

  useEffect(() => {
    const t = setInterval(() => {
      setFade(true);
      setTimeout(() => { setIdx(i => (i + 1) % items.length); setFade(false); }, 400);
    }, 3500);
    return () => clearInterval(t);
  }, []);

  return (
    <div
      className="flex items-center gap-2 px-3 py-1.5 rounded-lg mb-6 text-xs font-mono overflow-hidden"
      style={{ background: 'rgba(255,0,140,0.05)', border: '1px solid rgba(255,0,140,0.1)' }}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-[#ff008c] animate-pulse flex-shrink-0" />
      <span
        className="transition-all duration-400"
        style={{ color: '#888', opacity: fade ? 0 : 1, transform: fade ? 'translateY(-4px)' : 'translateY(0)' }}
      >
        {items[idx]}
      </span>
    </div>
  );
}

interface HomeSectionsProps {
  onNavigate: (id: string) => void;
}

export default function HomeSections({ onNavigate }: HomeSectionsProps) {
  const [trendOffset, setTrendOffset] = useState(0);
  const [trendFade, setTrendFade] = useState(false);
  const [trending, setTrending] = useState<{label: string; posts: number; delta: string; color: string; isNew?: boolean}[]>([]);
  const [labs, setLabs] = useState<{title: string; desc: string; tags: string[]; difficulty: string; diffColor: string; time: string; url: string}[]>([]);
  const [cafe, setCafe] = useState<{title: string; excerpt: string; tags: string[]; readTime: string}[]>([]);
  const [threats, setThreats] = useState<{title: string; severity: string; severityColor: string; desc: string; tags: string[]}[]>([]);
  const [fundamentos, setFundamentos] = useState<{label: string; posts: number; icon: string; desc: string}[]>([]);

  useEffect(() => {
    api.stats.get()
      .then(stats => {
        // Stats available if needed
      })
      .catch(() => {});
    api.posts.trending()
      .then(data => {
        if (data?.length) {
          const colors = ['#ff008c', '#06b6d4', '#ff4db8', '#f97316', '#28c840'];
          setTrending(data.slice(0, 8).map((post, i) => ({
            label: post.title || post.tags?.[0] || `Topic ${i + 1}`,
            posts: 1,
            delta: 'novo',
            color: colors[i % colors.length],
            isNew: true,
          })));
        }
      })
      .catch(() => {});
    api.posts.list({ contentType: 'lab,hands_on', perPage: 6 })
      .then(data => {
        if (data.items?.length) {
          const diffColors: Record<string, string> = {
            'iniciante': '#28c840',
            'intermediário': '#febc2e',
            'avançado': '#ff4db8',
          };
          setLabs(data.items.map(post => ({
            title: post.title || '',
            desc: post.summary || post.subtitle || '',
            tags: post.tags || [],
            difficulty: post.difficulty || 'Todos os níveis',
            diffColor: diffColors[(post.difficulty || '').toLowerCase()] || '#9ca3af',
            time: post.post_date ? new Date(post.post_date).toLocaleDateString('pt-BR') : '',
            url: post.linkedin_url || '',
          })));
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (trending.length === 0) return;
    const t = setInterval(() => {
      setTrendFade(true);
      setTimeout(() => {
        setTrendOffset(o => (o + 1) % trending.length);
        setTrendFade(false);
      }, 500);
    }, 7000);
    return () => clearInterval(t);
  }, [trending.length]);

  const visibleTrending = trending.length > 0
    ? Array.from({ length: Math.min(5, trending.length) }, (_, i) => trending[(trendOffset + i) % trending.length])
    : [];

  return (
    <div className="w-full space-y-16 pb-24">

      {/* MELHORIA 10: Live ticker */}
      <LiveTicker />

      {/* Trending Topics */}
      <section>
        <SectionHeader icon={Flame} title="Trending Topics" color="#ff008c" action="Ver todos" onAction={() => onNavigate('disciplines')} />
        <div
          className="flex flex-wrap gap-3 transition-opacity duration-500"
          style={{ opacity: trendFade ? 0.3 : 1 }}
        >
          {visibleTrending.length === 0 ? (
            <div className="w-full text-center py-6 text-xs text-[#555]">
              Nenhum post encontrado. Use o botão SYNC para importar posts do LinkedIn.
            </div>
          ) : visibleTrending.map((t, i) => (
            <button
              key={t.label + i}
              className="group relative flex items-center gap-3 px-4 py-3 rounded-xl border transition-all duration-200"
              style={{ background: 'rgba(13,13,13,0.8)', borderColor: 'rgba(255,255,255,0.06)' }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = t.color + '40';
                (e.currentTarget as HTMLButtonElement).style.background = t.color + '0a';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,255,255,0.06)';
                (e.currentTarget as HTMLButtonElement).style.background = 'rgba(13,13,13,0.8)';
              }}
            >
              {t.isNew && (
                <span className="absolute -top-2 -right-2 text-[9px] font-bold px-1.5 py-0.5 rounded" style={{ background: '#ff008c', color: '#fff' }}>
                  NEW
                </span>
              )}
              <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: t.color, boxShadow: `0 0 8px ${t.color}` }} />
              <div className="text-left">
                <div className="text-sm font-semibold text-white">{t.label}</div>
                <div className="text-[11px] text-[#555]">{t.posts} posts · <span style={{ color: t.color }}>{t.delta}</span></div>
              </div>
              <TrendingUp size={13} style={{ color: t.color, opacity: 0.6 }} />
            </button>
          ))}
        </div>
      </section>

      {/* Labs */}
      <section>
        <SectionHeader icon={FlaskConical} title="Labs" color="#06b6d4" action="Todos os labs" onAction={() => onNavigate('labs')} />
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {labs.length === 0 ? (
            <div className="col-span-full text-center py-6 text-xs text-[#555]">
              Nenhum lab disponível no momento.
            </div>
          ) : labs.map(lab => (
            <div
              key={lab.title}
              onClick={() => lab.url && window.open(lab.url, '_blank', 'noopener,noreferrer')}
              className="group relative flex flex-col rounded-xl border p-5 cursor-pointer transition-all duration-200"
              style={{ background: 'rgba(13,13,13,0.8)', borderColor: 'rgba(255,255,255,0.06)' }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLElement).style.borderColor = 'rgba(6,182,212,0.3)';
                (e.currentTarget as HTMLElement).style.background = 'rgba(6,182,212,0.04)';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.06)';
                (e.currentTarget as HTMLElement).style.background = 'rgba(13,13,13,0.8)';
              }}
            >
              <div className="flex items-start justify-between mb-3">
                <span className="text-[10px] font-bold px-2 py-0.5 rounded" style={{ background: lab.diffColor + '18', color: lab.diffColor }}>
                  {lab.difficulty}
                </span>
                <span className="flex items-center gap-1 text-[11px] text-[#555]"><Clock size={10} /> {lab.time}</span>
              </div>
              <div className="w-8 h-8 rounded-lg flex items-center justify-center mb-3" style={{ background: 'rgba(6,182,212,0.12)' }}>
                <FlaskConical size={15} style={{ color: '#06b6d4' }} />
              </div>
              <h3 className="text-sm font-bold text-white mb-2 line-clamp-2">{lab.title}</h3>
              <p className="text-xs text-[#666] leading-relaxed flex-1 line-clamp-3">{lab.desc}</p>
              <div className="flex flex-wrap gap-1.5 mt-3">
                {lab.tags.map(t => <span key={t} className="text-[10px] px-1.5 py-0.5 rounded text-[#555] bg-[#1a1a1a]">#{t}</span>)}
              </div>
              <div className="mt-4 flex items-center gap-1.5 text-xs text-[#555] group-hover:text-[#06b6d4] transition-colors">
                <ExternalLink size={11} /> Abrir no LinkedIn
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Café Requentado + Threats */}
      <div className="grid lg:grid-cols-2 gap-10">
        <section>
          <SectionHeader icon={Coffee} title="Café Requentado" color="#ff66c4" action="Ver mais" />
          <div className="space-y-3">
            {cafe.length === 0 ? (
              <div className="text-center py-6 text-xs text-[#555]">
                Nenhum conteúdo disponível.
              </div>
            ) : cafe.map(post => (
              <div
                key={post.title}
                className="group rounded-xl border p-4 cursor-pointer transition-all duration-200"
                style={{ background: 'rgba(13,13,13,0.8)', borderColor: 'rgba(255,255,255,0.06)' }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,102,196,0.28)';
                  (e.currentTarget as HTMLElement).style.background = 'rgba(255,102,196,0.04)';
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.06)';
                  (e.currentTarget as HTMLElement).style.background = 'rgba(13,13,13,0.8)';
                }}
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <h3 className="text-sm font-semibold text-white line-clamp-2 leading-snug">{post.title}</h3>
                  <span className="flex items-center gap-1 text-[10px] text-[#444] flex-shrink-0"><BookOpen size={9} /> {post.readTime}</span>
                </div>
                <p className="text-xs text-[#666] leading-relaxed line-clamp-2">{post.excerpt}</p>
                <div className="flex items-center justify-between mt-3">
                  <div className="flex flex-wrap gap-1">
                    {post.tags.map(t => <span key={t} className="text-[10px] text-[#444] bg-[#1a1a1a] px-1.5 py-0.5 rounded">#{t}</span>)}
                  </div>
                  <ExternalLink size={11} className="text-[#333] group-hover:text-[#ff66c4] transition-colors flex-shrink-0" />
                </div>
              </div>
            ))}
          </div>
        </section>

        <section>
          <SectionHeader icon={AlertTriangle} title="Threats Modernas" color="#ff5f57" action="Ver todas" />
          <div className="space-y-3">
            {threats.length === 0 ? (
              <div className="text-center py-6 text-xs text-[#555]">
                Nenhuma ameaça registrada.
              </div>
            ) : threats.map(threat => (
              <div
                key={threat.title}
                className="group rounded-xl border p-4 cursor-pointer transition-all duration-200"
                style={{ background: 'rgba(13,13,13,0.8)', borderColor: 'rgba(255,255,255,0.06)' }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLElement).style.borderColor = threat.severityColor + '30';
                  (e.currentTarget as HTMLElement).style.background = threat.severityColor + '06';
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.06)';
                  (e.currentTarget as HTMLElement).style.background = 'rgba(13,13,13,0.8)';
                }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[9px] font-bold px-2 py-0.5 rounded tracking-wider" style={{ background: threat.severityColor + '18', color: threat.severityColor }}>
                    {threat.severity}
                  </span>
                  <h3 className="text-sm font-semibold text-white">{threat.title}</h3>
                </div>
                <p className="text-xs text-[#666] leading-relaxed line-clamp-2">{threat.desc}</p>
                <div className="flex items-center justify-between mt-3">
                  <div className="flex flex-wrap gap-1">
                    {threat.tags.map(t => <span key={t} className="text-[10px] text-[#444] bg-[#1a1a1a] px-1.5 py-0.5 rounded">#{t}</span>)}
                  </div>
                  <Eye size={11} className="text-[#333] group-hover:text-[#ff5f57] transition-colors flex-shrink-0" />
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* Fundamentos */}
      <section>
        <SectionHeader icon={Brain} title="Fundamentos" color="#06b6d4" action="Ver todos" />
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {fundamentos.length === 0 ? (
            <div className="col-span-full text-center py-6 text-xs text-[#555]">
              Nenhum fundamento disponível.
            </div>
          ) : fundamentos.map(f => (
            <button
              key={f.label}
              className="group flex flex-col items-start p-4 rounded-xl border text-left transition-all duration-200"
              style={{ background: 'rgba(13,13,13,0.8)', borderColor: 'rgba(255,255,255,0.06)' }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(6,182,212,0.3)';
                (e.currentTarget as HTMLButtonElement).style.background = 'rgba(6,182,212,0.04)';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,255,255,0.06)';
                (e.currentTarget as HTMLButtonElement).style.background = 'rgba(13,13,13,0.8)';
              }}
            >
              <div className="text-2xl mb-3">{f.icon}</div>
              <div className="text-sm font-semibold text-white mb-1">{f.label}</div>
              <div className="text-xs text-[#555] leading-snug">{f.desc}</div>
              <div className="text-[11px] mt-3" style={{ color: '#06b6d4' }}>{f.posts} aulas</div>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
