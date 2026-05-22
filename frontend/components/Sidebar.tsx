'use client';

import { useState } from 'react';
import Image from 'next/image';
import { Chrome as Home, BookOpen, FlaskConical, Route, Search, Bookmark, User, ChevronRight } from 'lucide-react';

interface NavItem {
  icon: React.ElementType;
  label: string;
  id: string;
  badge?: string;
  color?: string;
}

const navItems: NavItem[] = [
  { icon: Home, label: 'Home', id: 'home' },
  { icon: BookOpen, label: 'Disciplinas', id: 'disciplines', color: '#ff008c' },
  { icon: FlaskConical, label: 'Lab', id: 'labs', color: '#8b5cf6' },
  { icon: Route, label: 'Trilhas', id: 'trails' },
];

const bottomItems: NavItem[] = [
  { icon: Search, label: 'Buscar', id: 'search' },
  { icon: Bookmark, label: 'Favoritos', id: 'bookmarks' },
  { icon: User, label: 'Perfil', id: 'profile' },
];

interface SidebarProps {
  activeView: string;
  onNavigate: (id: string) => void;
  onSearchOpen: () => void;
}

export default function Sidebar({ activeView, onNavigate, onSearchOpen }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className="relative flex flex-col h-screen sticky top-0 z-40 transition-all duration-300"
      style={{
        width: collapsed ? '64px' : '220px',
        background: 'linear-gradient(180deg, #0d0d0d 0%, #070707 100%)',
        borderRight: '1px solid rgba(255,0,140,0.08)',
      }}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-[rgba(255,0,140,0.08)]">
        <div className="relative flex-shrink-0">
          <div
            className="w-8 h-8 rounded-lg overflow-hidden"
            style={{ boxShadow: '0 0 16px rgba(255,0,140,0.4)' }}
          >
            <Image
              src="/Gemini_Generated_Image_h7c861h7c861h7c8.png"
              alt="UBB Logo"
              width={32}
              height={32}
              className="w-full h-full object-cover"
            />
          </div>
          <div className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-[#ff008c] rounded-full animate-pulse" />
        </div>
        {!collapsed && (
          <div className="overflow-hidden">
            <div className="text-[13px] font-bold text-white leading-tight whitespace-nowrap">
              Universidade
            </div>
            <div
              className="text-[11px] font-semibold whitespace-nowrap"
              style={{ color: '#ff008c' }}
            >
              Bebê
            </div>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 space-y-0.5 px-2 overflow-y-auto overflow-x-hidden">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => item.id === 'search' ? onSearchOpen() : onNavigate(item.id)}
              className="w-full flex items-center gap-3 px-2 py-2.5 rounded-lg text-left transition-all duration-150 group relative"
              style={{
                background: isActive ? 'rgba(255,0,140,0.1)' : 'transparent',
                color: isActive ? '#ff008c' : '#9ca3af',
              }}
              onMouseEnter={e => {
                if (!isActive) (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.04)';
              }}
              onMouseLeave={e => {
                if (!isActive) (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
              }}
            >
              {isActive && (
                <div
                  className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-r"
                  style={{ background: '#ff008c', boxShadow: '0 0 8px #ff008c' }}
                />
              )}
              <Icon
                size={16}
                className="flex-shrink-0 transition-colors"
                style={{ color: isActive ? '#ff008c' : item.color || '#9ca3af' }}
              />
              {!collapsed && (
                <>
                  <span className="text-[13px] font-medium flex-1 whitespace-nowrap">{item.label}</span>
                  {item.badge && (
                    <span
                      className="text-[9px] font-bold px-1.5 py-0.5 rounded"
                      style={{ background: 'rgba(255,0,140,0.2)', color: '#ff4db8' }}
                    >
                      {item.badge}
                    </span>
                  )}
                </>
              )}
            </button>
          );
        })}
      </nav>

      {/* Bottom items */}
      <div className="border-t border-[rgba(255,0,140,0.08)] py-3 px-2 space-y-0.5">
        {bottomItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => item.id === 'search' ? onSearchOpen() : onNavigate(item.id)}
              className="w-full flex items-center gap-3 px-2 py-2.5 rounded-lg text-left transition-all duration-150"
              style={{
                background: isActive ? 'rgba(255,0,140,0.1)' : 'transparent',
                color: isActive ? '#ff008c' : '#9ca3af',
              }}
              onMouseEnter={e => {
                if (!isActive) (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.04)';
              }}
              onMouseLeave={e => {
                if (!isActive) (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
              }}
            >
              <Icon size={16} className="flex-shrink-0" />
              {!collapsed && <span className="text-[13px] font-medium">{item.label}</span>}
            </button>
          );
        })}
      </div>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="absolute -right-3 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center transition-all z-50"
        style={{
          background: '#111',
          border: '1px solid rgba(255,0,140,0.2)',
          color: '#9ca3af',
        }}
        onMouseEnter={e => {
          (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,0,140,0.6)';
          (e.currentTarget as HTMLButtonElement).style.color = '#ff008c';
        }}
        onMouseLeave={e => {
          (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,0,140,0.2)';
          (e.currentTarget as HTMLButtonElement).style.color = '#9ca3af';
        }}
      >
        <ChevronRight size={12} style={{ transform: collapsed ? 'rotate(0deg)' : 'rotate(180deg)', transition: 'transform 0.3s' }} />
      </button>
    </aside>
  );
}
