'use client';

import { useEffect, useState } from 'react';
import { ArrowRight, Compass, Github } from 'lucide-react';
import dynamic from 'next/dynamic';
import { api } from '@/lib/api';

const KnowledgeGraph = dynamic(() => import('./KnowledgeGraph'), { ssr: false });

function buildTerminalLines(posts: number, disciplines: number, schools: number) {
  return [
    '> iniciando sistema...',
    '> carregando base de conhecimento...',
    `> ${posts} publicações indexadas`,
    `> ${disciplines} disciplinas ativas`,
    `> ${schools} escolas de conhecimento`,
    '> knowledge graph online',
    '> bem-vindo, bebê.',
  ];
}

interface HeroSectionProps {
  onNavigate: (id: string) => void;
  onSearchOpen: () => void;
  onGraphNavigate?: (view: string, disciplineId: number, disciplineName: string) => void;
}

export default function HeroSection({ onNavigate, onSearchOpen, onGraphNavigate }: HeroSectionProps) {
  const [terminalLines, setTerminalLines] = useState<string[]>([]);
  const [lineIndex, setLineIndex] = useState(0);
  const [charIndex, setCharIndex] = useState(0);
  const [stats, setStats] = useState({ total_posts: 0, total_disciplines: 0, total_schools: 0 });
  const [rawPostsCount, setRawPostsCount] = useState(0);
  const [about, setAbout] = useState({ name: '', url: '' });

  useEffect(() => {
    api.stats.get()
      .then(s => setStats(s))
      .catch(() => {});
  }, []);

  useEffect(() => {
    api.about.get()
      .then(a => setAbout(a))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const fetchRawCount = () => {
      api.rawPosts.list()
        .then(posts => setRawPostsCount(posts.length))
        .catch(() => {});
    };
    fetchRawCount();
    const interval = setInterval(fetchRawCount, 30000);
    return () => clearInterval(interval);
  }, []);

  const effectivePosts = rawPostsCount > 0 ? rawPostsCount : stats.total_posts;

  const terminalData = buildTerminalLines(effectivePosts, stats.total_disciplines, stats.total_schools);

  useEffect(() => {
    if (lineIndex >= terminalData.length) return;
    const line = terminalData[lineIndex];
    if (charIndex < line.length) {
      const t = setTimeout(() => setCharIndex(c => c + 1), 28);
      return () => clearTimeout(t);
    } else {
      const t = setTimeout(() => {
        setTerminalLines(prev => [...prev, line]);
        setLineIndex(i => i + 1);
        setCharIndex(0);
      }, 180);
      return () => clearTimeout(t);
    }
  }, [lineIndex, charIndex, terminalData]);

  const currentTyping = lineIndex < terminalData.length
    ? terminalData[lineIndex].slice(0, charIndex)
    : '';

  return (
    <section className="relative flex overflow-hidden">
      <div
        className="absolute inset-0 opacity-40"
        style={{
          backgroundImage: `
            linear-gradient(rgba(255, 0, 140, 0.04) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255, 0, 140, 0.04) 1px, transparent 1px)
          `,
          backgroundSize: '40px 40px',
        }}
      />
      <div
        className="absolute top-0 left-0 w-96 h-96 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 0% 0%, rgba(255,0,140,0.08) 0%, transparent 70%)' }}
      />
      <div
        className="absolute bottom-0 right-0 w-96 h-96 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 100% 100%, rgba(139,92,246,0.06) 0%, transparent 70%)' }}
      />

      <div className="relative z-10 w-full max-w-screen-xl mx-auto px-6 lg:px-10 grid lg:grid-cols-2 gap-16 items-center pt-8 pb-12">
        <div className="space-y-8">
          <div className="space-y-4">
            <div
              className="text-[11px] font-semibold tracking-widest uppercase"
              style={{ color: '#ff008c', letterSpacing: '0.2em' }}
            >
              Knowledge Graph · Cybersecurity
            </div>
            <h1 className="text-4xl lg:text-5xl font-bold leading-tight text-white">
              Vem cá bebê,
              <br />
              <span
                style={{
                  background: 'linear-gradient(135deg, #ff008c, #ff66c4)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text',
                }}
              >
                deixa eu te ensinar.
              </span>
            </h1>
            <p className="text-base text-[#9ca3af] leading-relaxed max-w-md">
              Curadoria viva de cybersegurança organizada por disciplinas,
              trilhas e conhecimento conectado. O conteúdo{about.name ? (
                <> de{' '}
                  <a
                    href={about.url || '#'}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:underline"
                    style={{ color: '#ff008c' }}
                  >
                    {about.name}
                  </a>
                </>
              ) : ''},
              estruturado como um sistema neural.
            </p>
          </div>

          <div
            className="inline-flex flex-col rounded-lg overflow-hidden text-xs font-mono"
            style={{
              background: 'rgba(13,13,13,0.9)',
              border: '1px solid rgba(255,0,140,0.15)',
              minWidth: 320,
              maxWidth: 380,
            }}
          >
            <div className="flex items-center gap-1.5 px-3 py-2 border-b border-[rgba(255,255,255,0.05)]">
              <div className="w-2.5 h-2.5 rounded-full bg-[#ff5f57]" />
              <div className="w-2.5 h-2.5 rounded-full bg-[#febc2e]" />
              <div className="w-2.5 h-2.5 rounded-full bg-[#28c840]" />
              <span className="ml-2 text-[#444] text-[10px]">universidade.bebê ~ terminal</span>
            </div>
            <div className="px-3 py-3 space-y-0.5">
              {terminalLines.map((l, i) => (
                <div key={i} className="text-[#cfcfcf]">
                  {l.startsWith('>') ? (
                    <><span style={{ color: '#ff008c' }}>{l.slice(0, 1)}</span>{l.slice(1)}</>
                  ) : l}
                </div>
              ))}
              {lineIndex < terminalData.length && (
                <div className="text-[#cfcfcf]">
                  {currentTyping.startsWith('>') ? (
                    <><span style={{ color: '#ff008c' }}>&gt;</span>{currentTyping.slice(1)}</>
                  ) : currentTyping}
                  <span className="inline-block w-1.5 h-3.5 bg-[#ff008c] ml-0.5 cursor-blink" />
                </div>
              )}
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              onClick={() => onNavigate('home')}
              className="group flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold text-white transition-all duration-200"
              style={{
                background: 'linear-gradient(135deg, #ff008c, #ff4db8)',
                boxShadow: '0 0 20px rgba(255,0,140,0.3)',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 0 30px rgba(255,0,140,0.5), 0 0 60px rgba(255,0,140,0.2)';
                (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(-1px)';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 0 20px rgba(255,0,140,0.3)';
                (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(0)';
              }}
            >
              Entrar na Universidade
              <ArrowRight size={15} className="group-hover:translate-x-1 transition-transform" />
            </button>
            <button
              onClick={() => onNavigate('disciplines')}
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition-all duration-200"
              style={{
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,0,140,0.2)',
                color: '#cfcfcf',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,0,140,0.08)';
                (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,0,140,0.5)';
                (e.currentTarget as HTMLButtonElement).style.color = '#fff';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.04)';
                (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,0,140,0.2)';
                (e.currentTarget as HTMLButtonElement).style.color = '#cfcfcf';
              }}
            >
              <Compass size={15} />
              Explorar Disciplinas
            </button>
            <a
              href="https://github.com/caveat-ops/ubb"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition-all duration-200"
              style={{
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
                color: '#777',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLAnchorElement).style.background = 'rgba(255,255,255,0.06)';
                (e.currentTarget as HTMLAnchorElement).style.borderColor = 'rgba(255,255,255,0.15)';
                (e.currentTarget as HTMLAnchorElement).style.color = '#cfcfcf';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLAnchorElement).style.background = 'rgba(255,255,255,0.04)';
                (e.currentTarget as HTMLAnchorElement).style.borderColor = 'rgba(255,255,255,0.08)';
                (e.currentTarget as HTMLAnchorElement).style.color = '#777';
              }}
            >
              <Github size={15} />
              GitHub
            </a>
          </div>

          <div className="flex gap-8">
            {[
              { value: effectivePosts > 0 ? String(effectivePosts) : '—', label: 'Publicações' },
              { value: stats.total_disciplines > 0 ? String(stats.total_disciplines) : '—', label: 'Disciplinas' },
              { value: stats.total_schools > 0 ? String(stats.total_schools) : '—', label: 'Trilhas' },
            ].map(s => (
              <div key={s.label}>
                <div className="text-2xl font-bold" style={{ color: '#ff008c' }}>{s.value}</div>
                <div className="text-xs text-[#555] mt-0.5">{s.label}</div>
              </div>
            ))}
          </div>
        </div>

        <div
          className="relative h-[500px] lg:h-[560px] rounded-2xl overflow-hidden"
          style={{
            background: 'rgba(13,13,13,0.6)',
            border: '1px solid rgba(255,0,140,0.1)',
            boxShadow: 'inset 0 0 60px rgba(255,0,140,0.03)',
          }}
        >
          <div
            className="absolute top-3 left-3 z-10 text-[10px] font-mono flex items-center gap-2"
            style={{ color: '#ff008c' }}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-[#ff008c] animate-pulse" />
            knowledge graph · live
          </div>
          <KnowledgeGraph onNavigate={onGraphNavigate} />
        </div>
      </div>
    </section>
  );
}
