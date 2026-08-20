'use client';

import { useState, useEffect } from 'react';
import { ExternalLink, ArrowLeft, Tag, Clock, ChartBar as BarChart2, BookOpen, FlaskConical, Wrench, TriangleAlert as AlertTriangle, Brain, Coffee } from 'lucide-react';
import { api, Post } from '@/lib/api';

const CONTENT_TYPES = [
  { id: 'aula', icon: BookOpen, label: 'Aula', color: '#8b5cf6' },
  { id: 'lab', icon: FlaskConical, label: 'Lab', color: '#8b5cf6' },
  { id: 'hands_on', icon: Wrench, label: 'Hands-on', color: '#06b6d4' },
  { id: 'awareness', icon: AlertTriangle, label: 'Awareness', color: '#febc2e' },
  { id: 'fundamento', icon: Brain, label: 'Fundamento', color: '#6d28d9' },
  { id: 'cafe', icon: Coffee, label: 'Café Requentado', color: '#ff66c4' },
];



interface LessonViewProps {
  onBack: () => void;
  postId?: number;
}

export default function LessonView({ onBack, postId }: LessonViewProps) {
  const [post, setPost] = useState<Post | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (postId) {
      setLoading(true);
      setPost(null);
      api.posts.get(postId)
        .then(data => setPost(data.post))
        .catch(() => {})
        .finally(() => setLoading(false));
    }
  }, [postId]);

  const lesson = post ? {
    id: post.id,
    type: post.content_type || 'aula',
    title: post.title || '',
    subtitle: post.subtitle || post.discipline_name || '',
    summary: post.summary || '',
    quote: post.quote || '',
    mariana: post.mariana_take || '',
    tags: post.tags || [],
    difficulty: post.difficulty || 'Iniciante',
    diffColor: ({
      'iniciante': '#28c840',
      'intermediário': '#febc2e',
      'avançado': '#ff4db8',
    } as Record<string, string>)[(post.difficulty || '').toLowerCase()] || '#9ca3af',
    readTime: '5 min',
    linkedinUrl: post.linkedin_url || '#',
    related: [],
  } : null;
  if (!postId && !loading) {
    return (
      <div className="pb-24 max-w-3xl">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-sm text-[#555] hover:text-white transition-colors mb-8"
        >
          <ArrowLeft size={14} />
          Voltar às disciplinas
        </button>
        <div className="flex flex-col items-center justify-center min-h-[40vh] text-center">
          <p className="text-[#555] text-sm">Selecione um post para visualizar.</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="pb-24 max-w-3xl">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-sm text-[#555] hover:text-white transition-colors mb-8"
        >
          <ArrowLeft size={14} />
          Voltar às disciplinas
        </button>
        <div className="flex items-center justify-center min-h-[40vh]">
          <div className="w-6 h-6 border-2 border-[#ff008c] border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  if (!lesson) {
    return (
      <div className="pb-24 max-w-3xl">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-sm text-[#555] hover:text-white transition-colors mb-8"
        >
          <ArrowLeft size={14} />
          Voltar às disciplinas
        </button>
        <div className="flex flex-col items-center justify-center min-h-[40vh] text-center">
          <div
            className="w-16 h-16 rounded-2xl flex items-center justify-center mb-6 text-3xl"
            style={{ background: 'rgba(255,0,140,0.1)', border: '1px solid rgba(255,0,140,0.15)' }}
          >
            🔍
          </div>
          <h2 className="text-xl font-bold text-white mb-2">Post não encontrado</h2>
          <p className="text-[#555] text-sm max-w-xs">
            O post que você está procurando não está disponível.
          </p>
        </div>
      </div>
    );
  }

  const typeInfo = CONTENT_TYPES.find(t => t.id === lesson.type) || CONTENT_TYPES[0];
  const TypeIcon = typeInfo.icon;

  return (
    <div className="pb-24 max-w-3xl">
      {/* Back */}
      <button
        onClick={onBack}
        className="flex items-center gap-2 text-sm text-[#555] hover:text-white transition-colors mb-8"
      >
        <ArrowLeft size={14} />
        Voltar às disciplinas
      </button>

      {/* Header */}
      <div className="mb-8">
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <span
            className="flex items-center gap-1.5 text-[11px] font-bold px-2.5 py-1 rounded"
            style={{ background: typeInfo.color + '18', color: typeInfo.color }}
          >
            <TypeIcon size={11} />
            {typeInfo.label}
          </span>
          <span
            className="text-[11px] font-bold px-2.5 py-1 rounded"
            style={{ background: lesson.diffColor + '18', color: lesson.diffColor }}
          >
            {lesson.difficulty}
          </span>
          <span className="flex items-center gap-1 text-[11px] text-[#444]">
            <Clock size={10} /> {lesson.readTime}
          </span>
        </div>

        <div className="text-xs text-[#555] mb-3">{lesson.subtitle}</div>
        <h1 className="text-2xl sm:text-3xl font-bold text-white leading-tight mb-4">{lesson.title}</h1>

        <div className="flex flex-wrap gap-1.5">
          {lesson.tags.map(t => (
            <span key={t} className="text-[11px] text-[#444] bg-[#1a1a1a] px-2 py-0.5 rounded">#{t}</span>
          ))}
        </div>
      </div>

      {/* Quote */}
      <div
        className="relative rounded-xl p-6 mb-8"
        style={{
          background: 'rgba(255,0,140,0.04)',
          border: '1px solid rgba(255,0,140,0.15)',
          borderLeft: '3px solid #ff008c',
        }}
      >
        <div
          className="text-5xl font-serif leading-none mb-3 select-none"
          style={{ color: '#ff008c', opacity: 0.4 }}
        >
          "
        </div>
        <p
          className="text-lg font-semibold leading-relaxed whitespace-pre-line"
          style={{ color: '#f5f5f5' }}
        >
          {lesson.quote}
        </p>
      </div>

      {/* Summary */}
      <div
        className="rounded-xl p-6 mb-8"
        style={{
          background: 'rgba(13,13,13,0.8)',
          border: '1px solid rgba(255,255,255,0.06)',
        }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Brain size={14} style={{ color: '#8b5cf6' }} />
          <span className="text-xs font-semibold text-[#8b5cf6] uppercase tracking-wider">Resumo IA</span>
        </div>
        <p className="text-sm text-[#cfcfcf] leading-relaxed">{lesson.summary}</p>
      </div>

      {/* Mariana's take */}
      <div
        className="rounded-xl p-6 mb-8"
        style={{
          background: 'rgba(255,0,140,0.03)',
          border: '1px solid rgba(255,0,140,0.1)',
        }}
      >
        <div className="flex items-start gap-3">
          <div
            className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-sm font-bold"
            style={{
              background: 'linear-gradient(135deg, #ff008c, #8b5cf6)',
              boxShadow: '0 0 12px rgba(255,0,140,0.4)',
            }}
          >
            M
          </div>
          <div>
            <div className="text-xs font-semibold mb-2" style={{ color: '#ff008c' }}>Mariana diz:</div>
            <p className="text-sm text-[#cfcfcf] leading-relaxed italic">"{lesson.mariana}"</p>
          </div>
        </div>
      </div>

      {/* Related */}
      <div className="mb-8">
        <div className="text-xs font-semibold text-[#555] uppercase tracking-wider mb-3">Disciplinas relacionadas</div>
        <div className="flex flex-wrap gap-2">
          {lesson.related.map(r => (
            <button
              key={r}
              className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-150"
              style={{
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
                color: '#9ca3af',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,0,140,0.4)';
                (e.currentTarget as HTMLButtonElement).style.color = '#ff4db8';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,255,255,0.08)';
                (e.currentTarget as HTMLButtonElement).style.color = '#9ca3af';
              }}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      {/* CTA */}
      <a
        href={lesson.linkedinUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="group flex items-center justify-center gap-3 w-full py-4 rounded-xl text-sm font-bold transition-all duration-200"
        style={{
          background: 'linear-gradient(135deg, #ff008c18, #8b5cf618)',
          border: '1px solid rgba(255,0,140,0.3)',
          color: '#ff4db8',
        }}
        onMouseEnter={e => {
          (e.currentTarget as HTMLAnchorElement).style.background = 'linear-gradient(135deg, #ff008c25, #8b5cf625)';
          (e.currentTarget as HTMLAnchorElement).style.borderColor = 'rgba(255,0,140,0.55)';
          (e.currentTarget as HTMLAnchorElement).style.boxShadow = '0 0 30px rgba(255,0,140,0.15)';
        }}
        onMouseLeave={e => {
          (e.currentTarget as HTMLAnchorElement).style.background = 'linear-gradient(135deg, #ff008c18, #8b5cf618)';
          (e.currentTarget as HTMLAnchorElement).style.borderColor = 'rgba(255,0,140,0.3)';
          (e.currentTarget as HTMLAnchorElement).style.boxShadow = 'none';
        }}
      >
        <ExternalLink size={16} />
        Abrir publicação original no LinkedIn
        <ArrowLeft size={14} className="rotate-180 group-hover:translate-x-1 transition-transform" />
      </a>


    </div>
  );
}
