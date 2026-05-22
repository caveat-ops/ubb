'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import {
  Shield, Crosshair, Brain, Globe, Hash,
  ArrowRight, BookOpen, FlaskConical, ChevronDown,
} from 'lucide-react';

interface Discipline {
  id: string;
  numericId: number;
  title: string;
  desc: string;
  icon: string;
  tags: string[];
  lessons: number;
  labs: number;
  color: string;
  category: string;
}



const CATEGORIES = [
  { id: 'all', label: 'Todas', icon: Hash, color: '#9ca3af' },
  { id: 'defensive', label: 'Defensive', icon: Shield, color: '#06b6d4' },
  { id: 'offensive', label: 'Offensive', icon: Crosshair, color: '#ff008c' },
  { id: 'ai', label: 'AI & Threats', icon: Brain, color: '#f97316' },
  { id: 'reality', label: 'Cyber Reality', icon: Globe, color: '#cbd5e1' },
  { id: 'others', label: 'Others', icon: Hash, color: '#555' },
];

interface DisciplinesViewProps {
  onSelectLesson: (disciplineId: number, disciplineName: string) => void;
}

export default function DisciplinesView({ onSelectLesson }: DisciplinesViewProps) {
  const [activeCategory, setActiveCategory] = useState('all');
  const [disciplines, setDisciplines] = useState<Discipline[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.disciplines.list()
      .then(data => {
        if (data?.length) {
          setDisciplines(data.map(d => ({
            id: d.slug,
            numericId: (d as any).id || 0,
            title: d.name,
            desc: d.description || '',
            icon: d.icon || '📚',
            tags: [],
            lessons: d.post_count || 0,
            labs: d.lab_count || 0,
            color: d.color || '#8b5cf6',
            category: ({
              'Defensive Security': 'defensive',
              'Security Operations': 'defensive',
              'Offensive Security': 'offensive',
              'AI & Emerging Threats': 'ai',
              'Cyber Reality': 'reality',
              'Fundamentals': 'others',
            } as Record<string, string>)[d.school_name || ''] || 'others',
          })));
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const filtered = activeCategory === 'all'
    ? disciplines
    : disciplines.filter(d => d.category === activeCategory);

  return (
    <div className="pb-24">
      <div className="mb-10">
        <h1 className="text-3xl font-bold text-white mb-2">Disciplinas</h1>
        <p className="text-[#555] text-sm">
          {disciplines.length > 0
            ? `${disciplines.length} disciplinas · ${disciplines.reduce((a, d) => a + d.lessons, 0)} aulas · ${disciplines.reduce((a, d) => a + d.labs, 0)} labs`
            : loading ? 'Carregando...' : 'Nenhuma disciplina cadastrada'}
        </p>
      </div>

      {/* Category filter */}
      <div className="flex flex-wrap gap-2 mb-8">
        {CATEGORIES.map(cat => {
          const Icon = cat.icon;
          const isActive = activeCategory === cat.id;
          return (
            <button
              key={cat.id}
              onClick={() => setActiveCategory(cat.id)}
              className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all duration-150"
              style={{
                background: isActive ? cat.color + '18' : 'rgba(255,255,255,0.03)',
                border: `1px solid ${isActive ? cat.color + '50' : 'rgba(255,255,255,0.06)'}`,
                color: isActive ? cat.color : '#555',
              }}
            >
              <Icon size={13} />
              {cat.label}
            </button>
          );
        })}
      </div>

      {/* Grid */}
      <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {loading ? (
          <div className="col-span-full flex items-center justify-center py-16">
            <div className="w-6 h-6 border-2 border-[#ff008c] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : disciplines.length === 0 ? (
          <div className="col-span-full text-center py-16">
            <p className="text-[#555] text-sm">Nenhuma disciplina cadastrada. Use o SYNC para importar posts.</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="col-span-full text-center py-16">
            <p className="text-[#555] text-sm">Nenhuma disciplina nesta categoria.</p>
          </div>
        ) : filtered.map(d => (
          <button
            key={d.id}
            onClick={() => onSelectLesson(d.numericId, d.title)}
            className="group relative flex flex-col text-left rounded-xl border p-5 transition-all duration-200"
            style={{
              background: 'rgba(13,13,13,0.8)',
              borderColor: 'rgba(255,255,255,0.06)',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLButtonElement).style.borderColor = d.color + '40';
              (e.currentTarget as HTMLButtonElement).style.background = d.color + '06';
              (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(-2px)';
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,255,255,0.06)';
              (e.currentTarget as HTMLButtonElement).style.background = 'rgba(13,13,13,0.8)';
              (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(0)';
            }}
          >
            {/* Top bar color accent */}
            <div
              className="absolute top-0 left-6 right-6 h-px rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
              style={{ background: `linear-gradient(90deg, transparent, ${d.color}, transparent)` }}
            />

            <div className="flex items-start justify-between mb-4">
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center text-xl"
                style={{
                  background: d.color + '15',
                  boxShadow: `0 0 20px ${d.color}10`,
                }}
              >
                {d.icon}
              </div>
              <ArrowRight size={14} className="text-[#333] group-hover:text-white transition-colors mt-1" />
            </div>

            <h3 className="text-base font-bold text-white mb-2">{d.title}</h3>
            <p className="text-xs text-[#666] leading-relaxed flex-1 line-clamp-2">{d.desc}</p>

            <div className="flex flex-wrap gap-1.5 mt-3">
              {d.tags.slice(0, 3).map(t => (
                <span key={t} className="text-[10px] text-[#444] bg-[#1a1a1a] px-1.5 py-0.5 rounded">#{t}</span>
              ))}
            </div>

            <div className="flex items-center gap-4 mt-4 pt-3 border-t border-[rgba(255,255,255,0.05)]">
              <span className="flex items-center gap-1.5 text-[11px] text-[#555]">
                <BookOpen size={11} style={{ color: d.color }} />
                {d.lessons} aulas
              </span>
              {d.labs > 0 && (
                <span className="flex items-center gap-1.5 text-[11px] text-[#555]">
                  <FlaskConical size={11} style={{ color: '#8b5cf6' }} />
                  {d.labs} labs
                </span>
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
