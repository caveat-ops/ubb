'use client';

import { useState, useEffect, useMemo } from 'react';
import { api, Post } from '@/lib/api';
import { Search, FlaskConical, Wrench, Hash, ArrowRight, Clock } from 'lucide-react';

const TYPE_FILTERS = [
  { id: 'all', label: 'Todos', icon: Hash, color: '#9ca3af' },
  { id: 'lab', label: 'Lab', icon: FlaskConical, color: '#8b5cf6' },
  { id: 'hands_on', label: 'Hands-on', icon: Wrench, color: '#06b6d4' },
];

const DIFFICULTY_COLOR: Record<string, string> = {
  'iniciante': '#28c840',
  'intermediário': '#febc2e',
  'avançado': '#ff4db8',
};

function typeMeta(contentType: string | null) {
  return TYPE_FILTERS.find(t => t.id === contentType) || TYPE_FILTERS[1];
}

interface LabsViewProps {
  onSelectPost: (postId: number) => void;
}

export default function LabsView({ onSelectPost }: LabsViewProps) {
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeType, setActiveType] = useState('all');
  const [query, setQuery] = useState('');

  useEffect(() => {
    api.posts.list({ contentType: 'lab,hands_on', perPage: 200 })
      .then(d => setPosts(d.items))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    let list = posts;
    if (activeType !== 'all') {
      list = list.filter(p => p.content_type === activeType);
    }
    if (query.trim()) {
      const needle = query.trim().toLowerCase();
      list = list.filter(p =>
        p.title?.toLowerCase().includes(needle) ||
        p.summary?.toLowerCase().includes(needle) ||
        p.discipline_name?.toLowerCase().includes(needle) ||
        p.tags?.some(t => t.toLowerCase().includes(needle))
      );
    }
    return list;
  }, [posts, activeType, query]);

  const labCount = posts.filter(p => p.content_type === 'lab').length;
  const handsOnCount = posts.filter(p => p.content_type === 'hands_on').length;

  return (
    <div className="pb-24">
      <div className="mb-10">
        <h1 className="text-3xl font-bold text-white mb-2">Lab</h1>
        <p className="text-[#555] text-sm">
          {posts.length > 0
            ? `${labCount} labs · ${handsOnCount} hands-on`
            : loading ? 'Carregando...' : 'Nenhum lab identificado ainda'}
        </p>
      </div>

      {/* Search + filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-8">
        <div
          className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg flex-1"
          style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}
        >
          <Search size={14} className="text-[#555] flex-shrink-0" />
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Buscar por título, disciplina ou tag..."
            className="flex-1 bg-transparent text-sm text-white placeholder-[#555] outline-none"
          />
        </div>

        <div className="flex gap-2">
          {TYPE_FILTERS.map(t => {
            const Icon = t.icon;
            const isActive = activeType === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setActiveType(t.id)}
                className="flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all duration-150 whitespace-nowrap"
                style={{
                  background: isActive ? t.color + '18' : 'rgba(255,255,255,0.03)',
                  border: `1px solid ${isActive ? t.color + '50' : 'rgba(255,255,255,0.06)'}`,
                  color: isActive ? t.color : '#555',
                }}
              >
                <Icon size={13} />
                {t.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Grid */}
      <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {loading ? (
          <div className="col-span-full flex items-center justify-center py-16">
            <div className="w-6 h-6 border-2 border-[#8b5cf6] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : posts.length === 0 ? (
          <div className="col-span-full text-center py-16">
            <p className="text-[#555] text-sm">Nenhum lab identificado ainda. Use o SYNC para importar e classificar posts.</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="col-span-full text-center py-16">
            <p className="text-[#555] text-sm">Nenhum lab encontrado para essa busca.</p>
          </div>
        ) : filtered.map(p => {
          const meta = typeMeta(p.content_type);
          const Icon = meta.icon;
          const diffColor = DIFFICULTY_COLOR[(p.difficulty || '').toLowerCase()] || '#9ca3af';
          return (
            <button
              key={p.id}
              onClick={() => onSelectPost(p.id)}
              className="group relative flex flex-col text-left rounded-xl border p-5 transition-all duration-200"
              style={{ background: 'rgba(13,13,13,0.8)', borderColor: 'rgba(255,255,255,0.06)' }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = meta.color + '40';
                (e.currentTarget as HTMLButtonElement).style.background = meta.color + '06';
                (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(-2px)';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,255,255,0.06)';
                (e.currentTarget as HTMLButtonElement).style.background = 'rgba(13,13,13,0.8)';
                (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(0)';
              }}
            >
              <div
                className="absolute top-0 left-6 right-6 h-px rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ background: `linear-gradient(90deg, transparent, ${meta.color}, transparent)` }}
              />

              <div className="flex items-start justify-between mb-3 gap-2">
                <span
                  className="flex items-center gap-1.5 text-[10px] font-bold px-2 py-0.5 rounded flex-shrink-0"
                  style={{ background: meta.color + '18', color: meta.color }}
                >
                  <Icon size={10} />
                  {meta.label}
                </span>
                {p.difficulty && (
                  <span
                    className="text-[10px] font-bold px-2 py-0.5 rounded flex-shrink-0"
                    style={{ background: diffColor + '18', color: diffColor }}
                  >
                    {p.difficulty}
                  </span>
                )}
              </div>

              <h3 className="text-sm font-bold text-white mb-2 line-clamp-2">{p.title}</h3>
              <p className="text-xs text-[#666] leading-relaxed flex-1 line-clamp-3">
                {p.summary || p.subtitle}
              </p>

              {p.discipline_name && (
                <div className="flex items-center gap-1.5 mt-3 text-[11px] text-[#555]">
                  <span className="w-1 h-1 rounded-full" style={{ background: meta.color }} />
                  {p.discipline_name}
                </div>
              )}

              <div className="flex flex-wrap gap-1.5 mt-3">
                {(p.tags || []).slice(0, 3).map(t => (
                  <span key={t} className="text-[10px] text-[#444] bg-[#1a1a1a] px-1.5 py-0.5 rounded">#{t}</span>
                ))}
              </div>

              <div className="mt-4 pt-3 border-t border-[rgba(255,255,255,0.05)] flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-[11px] text-[#555]">
                  <Clock size={11} />
                  {p.post_date ? new Date(p.post_date).toLocaleDateString('pt-BR') : '—'}
                </span>
                <ArrowRight size={13} className="text-[#333] group-hover:text-white transition-colors" />
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
