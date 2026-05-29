'use client';

import { useState, useEffect } from 'react';
import Sidebar from '@/components/Sidebar';
import HeroSection from '@/components/HeroSection';
import DisciplinesView from '@/components/DisciplinesView';
import LessonView from '@/components/LessonView';
import SearchPalette from '@/components/SearchPalette';
import SyncButton from '@/components/SyncButton';
import { Search, ArrowLeft, ExternalLink } from 'lucide-react';
import { api, Post as PostType } from '@/lib/api';

type View = 'home' | 'disciplines' | 'lesson' | 'posts' | 'labs' | 'trails';

export default function Home() {
  const [view, setView] = useState<View>('home');
  const [disciplineId, setDisciplineId] = useState<number | null>(null);
  const [disciplineName, setDisciplineName] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [showHero, setShowHero] = useState(true);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setSearchOpen(s => !s);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const handleNavigate = (id: string) => {
    setView(id as View);
    if (id !== 'home') setShowHero(false);
    if (id === 'home') setShowHero(true);
  };

  const handleGraphNavigate = (view: string, discId: number, discName: string) => {
    setDisciplineId(discId);
    setDisciplineName(discName);
    setView(view as View);
    setShowHero(false);
  };

  function DisciplinePosts({ disciplineId, disciplineName, onBack, onSelectPost }: { disciplineId: number; disciplineName: string; onBack: () => void; onSelectPost: (id: number) => void }) {
    const [posts, setPosts] = useState<PostType[]>([]);
    const [loading, setLoading] = useState(true);
    useEffect(() => {
      api.posts.list(1, 50, disciplineId)
        .then(d => setPosts(d.items))
        .catch(() => {})
        .finally(() => setLoading(false));
    }, [disciplineId]);
    return (
      <div className="max-w-screen-xl mx-auto px-6 lg:px-10 pt-10 pb-24">
        <button onClick={onBack} className="flex items-center gap-2 text-sm text-[#555] hover:text-white transition-colors mb-6">
          <ArrowLeft size={14} /> Voltar às disciplinas
        </button>
        <h1 className="text-2xl font-bold text-white mb-2">{disciplineName}</h1>
        <p className="text-sm text-[#555] mb-8">{posts.length} aulas</p>
        {loading ? (
          <div className="flex justify-center py-16"><div className="w-6 h-6 border-2 border-[#ff008c] border-t-transparent rounded-full animate-spin" /></div>
        ) : posts.length === 0 ? (
          <p className="text-[#555] text-sm">Nenhuma aula nesta disciplina ainda.</p>
        ) : (
          <div className="space-y-3">
            {posts.map(p => (
              <a
                key={p.id}
                href={p.linkedin_url || '#'}
                target="_blank"
                rel="noopener noreferrer"
                className="block rounded-xl p-4 transition-all duration-200 hover:translate-y-[-2px]"
                style={{ background: 'rgba(13,13,13,0.8)', border: '1px solid rgba(255,255,255,0.06)' }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-semibold text-white mb-1 line-clamp-2">{p.title}</h3>
                    {p.subtitle && <p className="text-xs text-[#555] line-clamp-1">{p.subtitle}</p>}
                  </div>
                  <ExternalLink size={14} className="text-[#444] flex-shrink-0 mt-1" />
                </div>
              </a>
            ))}
          </div>
        )}
      </div>
    );
  }

  const renderMain = () => {
    if (view === 'home') {
      return (
        <>
          {showHero && (
            <HeroSection
              onNavigate={handleNavigate}
              onSearchOpen={() => setSearchOpen(true)}
              onGraphNavigate={handleGraphNavigate}
            />
          )}

        </>
      );
    }

    if (view === 'lesson') {
      return (
        <div className="max-w-screen-xl mx-auto px-6 lg:px-10 pt-10">
          <LessonView onBack={() => setView('disciplines')} />
        </div>
      );
    }

    if (view === 'disciplines') {
      return (
        <div className="max-w-screen-xl mx-auto px-6 lg:px-10 pt-10">
          <DisciplinesView onSelectLesson={(id, name) => { setDisciplineId(id); setDisciplineName(name); setView('posts'); }} />
        </div>
      );
    }

    if (view === 'posts' && disciplineId) {
      return <DisciplinePosts disciplineId={disciplineId} disciplineName={disciplineName} onBack={() => setView('disciplines')} onSelectPost={(postId) => { setView('lesson'); }} />;
    }

    // Placeholder views
    return (
      <div className="max-w-screen-xl mx-auto px-6 lg:px-10 pt-10">
        <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
          <div
            className="w-16 h-16 rounded-2xl flex items-center justify-center mb-6 text-3xl"
            style={{ background: 'rgba(255,0,140,0.1)', border: '1px solid rgba(255,0,140,0.15)' }}
          >
            🔒
          </div>
          <h2 className="text-xl font-bold text-white mb-2">Em breve</h2>
          <p className="text-[#555] text-sm max-w-xs">
            Esta seção está sendo construída. O sistema está aprendendo.
          </p>
          <span
            className="mt-4 text-xs font-mono px-3 py-1.5 rounded"
            style={{ background: 'rgba(255,0,140,0.08)', color: '#ff4db8', border: '1px solid rgba(255,0,140,0.15)' }}
          >
            coming_soon.exe
          </span>
        </div>
      </div>
    );
  };

  return (
    <div className="flex min-h-screen bg-[#070707]">
      <Sidebar
        activeView={view}
        onNavigate={handleNavigate}
        onSearchOpen={() => setSearchOpen(true)}
      />

      <main className="flex-1 min-w-0 overflow-x-hidden">
        {/* Header com search box — visível em todas as views */}
        <header
          className="sticky top-0 z-30 flex items-center justify-end px-6 lg:px-10 h-12"
          style={{
            background: 'rgba(7,7,7,0.85)',
            backdropFilter: 'blur(8px)',
            borderBottom: '1px solid rgba(255,0,140,0.06)',
          }}
        >
          <button
            onClick={() => setSearchOpen(true)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-all duration-200"
            style={{
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.08)',
              color: '#555',
            }}
            onMouseEnter={e => {
              const el = e.currentTarget as HTMLButtonElement;
              el.style.borderColor = 'rgba(255,0,140,0.3)';
              el.style.color = '#cfcfcf';
            }}
            onMouseLeave={e => {
              const el = e.currentTarget as HTMLButtonElement;
              el.style.borderColor = 'rgba(255,255,255,0.08)';
              el.style.color = '#555';
            }}
          >
            <Search size={14} />
            <span className="hidden sm:inline">Buscar...</span>
            <kbd className="hidden sm:flex items-center gap-0.5 text-[10px] text-[#444] border border-[#333] rounded px-1 py-0.5 ml-2">
              <span className="text-[11px]">⌘</span>K
            </kbd>
          </button>
        </header>
        {renderMain()}
      </main>

      <SearchPalette open={searchOpen} onClose={() => setSearchOpen(false)} />
      <SyncButton />
    </div>
  );
}
