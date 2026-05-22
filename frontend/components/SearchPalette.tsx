'use client';

import { useState, useEffect, useRef } from 'react';
import { Search, Hash, FlaskConical, Route, BookOpen, X } from 'lucide-react';
import { api } from '@/lib/api';

interface SearchResult {
  type: 'disciplina' | 'lab' | 'aula' | 'trilha' | 'tema';
  title: string;
  subtitle: string;
  icon: React.ElementType;
  color: string;
  url: string;
  tags?: string[];
}



function getIconForType(type: string): React.ElementType {
  switch (type) {
    case 'discipline': return Hash;
    case 'lab': return FlaskConical;
    case 'post': return BookOpen;
    case 'trail': return Route;
    default: return Hash;
  }
}

function getColorForType(type: string): string {
  switch (type) {
    case 'discipline': return '#ff008c';
    case 'lab': return '#06b6d4';
    case 'post': return '#8b5cf6';
    case 'trail': return '#ff4db8';
    default: return '#9ca3af';
  }
}

interface SearchPaletteProps {
  open: boolean;
  onClose: () => void;
}

export default function SearchPalette({ open, onClose }: SearchPaletteProps) {
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(0);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [searching, setSearching] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!query) {
      setResults([]);
      setTotalResults(0);
      return;
    }

    setSearching(true);
    api.search.query(query)
      .then(data => {
        if (data.results?.length) {
          const mapped: SearchResult[] = data.results.map(r => ({
            type: (r.type as any) || 'aula',
            title: r.title,
            subtitle: r.subtitle || '',
            url: r.url,
            icon: getIconForType(r.type),
            color: getColorForType(r.type),
            tags: r.tags,
          }));
          setResults(mapped);
          setTotalResults(data.total);
        } else {
          setResults([]);
          setTotalResults(0);
        }
      })
      .catch(() => {
        setResults([]);
        setTotalResults(0);
      })
      .finally(() => setSearching(false));
  }, [query]);

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setQuery('');
      setSelected(0);
    }
  }, [open]);

  useEffect(() => {
    setSelected(0);
  }, [query]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!open) return;
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowDown') setSelected(s => Math.min(s + 1, results.length - 1));
      if (e.key === 'ArrowUp') setSelected(s => Math.max(s - 1, 0));
      if (e.key === 'Enter' && results[selected]) {
        const r = results[selected];
        if (r.url) window.open(r.url, '_blank', 'noopener,noreferrer');
        onClose();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, results, selected, onClose]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        if (!open) {
          // trigger open from parent
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open]);

  if (!open) return null;

  const handleResultClick = (r: SearchResult) => {
    if (r.url) window.open(r.url, '_blank', 'noopener,noreferrer');
    // fallback: just close the palette
    onClose();
  };

  const typeLabel = { disciplina: 'Disciplina', lab: 'Lab', aula: 'Aula', trilha: 'Trilha', tema: 'Tema' };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[12vh]"
      style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(6px)' }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="w-full max-w-xl rounded-xl overflow-hidden"
        style={{
          background: '#0d0d0d',
          border: '1px solid rgba(255,0,140,0.25)',
          boxShadow: '0 0 60px rgba(255,0,140,0.15), 0 24px 80px rgba(0,0,0,0.6)',
        }}
      >
        {/* Input */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-[rgba(255,255,255,0.06)]">
          <Search size={16} className="text-[#ff008c] flex-shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Buscar disciplinas, labs, trilhas, temas..."
            className="flex-1 bg-transparent text-sm text-white placeholder-[#555] outline-none"
          />
          {query && (
            <button onClick={() => setQuery('')} className="text-[#555] hover:text-white transition-colors">
              <X size={14} />
            </button>
          )}
          <kbd
            className="hidden sm:flex items-center gap-1 text-[10px] text-[#444] border border-[#333] rounded px-1.5 py-0.5"
          >
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-[420px] overflow-y-auto py-2">
          {searching ? (
            <div className="text-center py-10 text-[#555] text-sm flex items-center justify-center gap-2">
              <div className="w-3 h-3 border-2 border-[#ff008c] border-t-transparent rounded-full animate-spin" />
              Buscando...
            </div>
          ) : results.length === 0 && query ? (
            <div className="text-center py-10 text-[#555] text-sm">Nenhum resultado encontrado</div>
          ) : results.length === 0 && !query ? (
            <div className="text-center py-10 text-[#555] text-sm">Digite para buscar...</div>
          ) : (
            results.map((r, i) => {
              const Icon = r.icon;
              const isSelected = i === selected;
              return (
                <button
                  key={i}
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors"
                  style={{ background: isSelected ? 'rgba(255,0,140,0.08)' : 'transparent' }}
                  onMouseEnter={() => setSelected(i)}
                  onClick={() => handleResultClick(r)}
                >
                  <div
                    className="w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0"
                    style={{ background: r.color + '18' }}
                  >
                    <Icon size={13} style={{ color: r.color }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-white font-medium truncate">{r.title}</div>
                    <div className="text-xs text-[#555] truncate">{r.subtitle}</div>
                  </div>
                  <span
                    className="text-[10px] px-2 py-0.5 rounded font-medium flex-shrink-0"
                    style={{ background: r.color + '18', color: r.color }}
                  >
                    {typeLabel[r.type]}
                  </span>
                </button>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-[rgba(255,255,255,0.04)] px-4 py-2.5 flex items-center justify-between">
          <div className="flex items-center gap-3 text-[11px] text-[#444]">
            <span className="flex items-center gap-1">
              <kbd className="border border-[#333] rounded px-1">↑↓</kbd> navegar
            </span>
            <span className="flex items-center gap-1">
              <kbd className="border border-[#333] rounded px-1">↵</kbd> abrir
            </span>
          </div>
          <div className="text-[11px] text-[#333]">{results.length} resultado{results.length !== 1 ? 's' : ''}</div>
        </div>
      </div>
    </div>
  );
}
