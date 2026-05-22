'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { RefreshCw, X, Terminal, CheckCircle, AlertCircle } from 'lucide-react';
import { api } from '@/lib/api';

export default function SyncButton() {
  const [open, setOpen] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [available, setAvailable] = useState<boolean | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  useEffect(() => {
    fetch('/api/sync-info')
      .then(r => r.json())
      .then(d => setAvailable(d.available))
      .catch(() => setAvailable(false));
  }, []);

  const handleSync = useCallback(async () => {
    if (available === false) {
      setLogs(['ℹ️  Sync disponível apenas no ambiente de desenvolvimento.']);
      setLogs(prev => [...prev, '   O sync é executado no host via cron e envia os dados para cá.']);
      setDone(true);
      return;
    }
    setSyncing(true);
    setDone(false);
    setError(null);
    setLogs([]);

    try {
      const { task_id } = await api.sync.trigger();
      setTaskId(task_id);
      setLogs(prev => [...prev, '🔄 Sincronização iniciada...']);

      const es = api.sync.stream(task_id);
      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'progress' && data.text) {
            setLogs(prev => [...prev, data.text]);
          }
          if (data.type === 'complete') {
            setLogs(prev => [...prev, '✅ Sincronização concluída!']);
            setDone(true);
            setSyncing(false);
            es.close();
          }
          if (data.type === 'error') {
            setLogs(prev => [...prev, `❌ Erro: ${data.error || 'desconhecido'}`]);
            setError(data.error || 'Erro desconhecido');
            setDone(true);
            setSyncing(false);
            es.close();
          }
        } catch (e) {
          // ignore parse errors
        }
      };
      es.onerror = () => {
        setLogs(prev => [...prev, '⚠️ Conexão perdida. Verificando status...']);
        const poll = setInterval(async () => {
          try {
            const status = await api.sync.status(task_id);
            if (status.status === 'completed' || status.status === 'error') {
              clearInterval(poll);
              setSyncing(false);
              setDone(true);
              if (status.status === 'error') {
                setError('Erro durante sincronização');
              }
              status.messages.forEach(m => {
                if (m.text) setLogs(prev => [...prev, m.text]);
              });
            }
          } catch (e) {
            clearInterval(poll);
          }
        }, 2000);
      };
    } catch (e: any) {
      setLogs(prev => [...prev, `❌ Erro ao iniciar: ${e.message}`]);
      setError(e.message);
      setSyncing(false);
      setDone(true);
    }
  }, []);

  // Sempre mostra o botão, mas com fallback se sync não disponível

  return (
    <>
      {/* Floating button */}
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-3 rounded-xl text-sm font-bold transition-all duration-200"
        style={{
          background: syncing ? 'rgba(255,0,140,0.15)' : 'linear-gradient(135deg, #ff008c, #ff4db8)',
          border: `1px solid ${syncing ? 'rgba(255,0,140,0.3)' : 'rgba(255,255,255,0.1)'}`,
          color: '#fff',
          boxShadow: syncing ? '0 0 20px rgba(255,0,140,0.2)' : '0 0 25px rgba(255,0,140,0.4)',
        }}
        onMouseEnter={e => {
          if (!syncing) {
            e.currentTarget.style.boxShadow = '0 0 35px rgba(255,0,140,0.6)';
            e.currentTarget.style.transform = 'translateY(-2px)';
          }
        }}
        onMouseLeave={e => {
          if (!syncing) {
            e.currentTarget.style.boxShadow = '0 0 25px rgba(255,0,140,0.4)';
            e.currentTarget.style.transform = 'translateY(0)';
          }
        }}
      >
        <RefreshCw size={16} className={syncing ? 'animate-spin' : ''} />
        SYNC
      </button>

      {/* Modal */}
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(6px)' }}
          onClick={e => { if (e.target === e.currentTarget) setOpen(false); }}
        >
          <div
            className="w-full max-w-2xl rounded-xl overflow-hidden"
            style={{
              background: '#0d0d0d',
              border: '1px solid rgba(255,0,140,0.25)',
              boxShadow: '0 0 60px rgba(255,0,140,0.15)',
            }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-[rgba(255,255,255,0.06)]">
              <div className="flex items-center gap-3">
                <Terminal size={18} style={{ color: '#ff008c' }} />
                <span className="text-white font-bold text-sm">
                  Sync Terminal
                </span>
                {syncing && (
                  <span className="flex items-center gap-1.5 text-xs text-[#888]">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#ff008c] animate-pulse" />
                    running
                  </span>
                )}
              </div>
              <button onClick={() => setOpen(false)} className="text-[#555] hover:text-white transition-colors">
                <X size={16} />
              </button>
            </div>

            {/* Logs */}
            <div
              className="p-4 max-h-[400px] overflow-y-auto font-mono text-xs leading-relaxed"
              style={{ background: '#070707', minHeight: '200px' }}
            >
              {logs.length === 0 ? (
                <div className="flex items-center justify-center h-32 text-[#444] text-center px-4">
                  {available === false
                    ? 'Sync disponível apenas no ambiente de desenvolvimento.\nO conteúdo é sincronizado automaticamente via cron.'
                    : 'Clique em "Iniciar Sync" para começar'}
                </div>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className="py-0.5" style={{
                    color: log.startsWith('ERRO') || log.startsWith('❌') ? '#ff5f57'
                         : log.startsWith('✅') || log.startsWith('🔄') ? '#ff008c'
                         : log.startsWith('⚠️') ? '#febc2e'
                         : '#cfcfcf',
                  }}>
                    {log}
                  </div>
                ))
              )}
              <div ref={logEndRef} />
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between px-5 py-3 border-t border-[rgba(255,255,255,0.06)]">
              <div className="text-[11px] text-[#555]">
                {syncing ? 'Sincronizando...' : done ? (error ? 'Concluído com erros' : 'Concluído') : 'Pronto'}
              </div>
              <div className="flex gap-2">
                {!syncing && !done && (
                  <button
                    onClick={handleSync}
                    className="flex items-center gap-2 px-4 py-1.5 rounded-lg text-xs font-bold transition-all"
                    style={{
                      background: 'linear-gradient(135deg, #ff008c, #ff4db8)',
                      color: '#fff',
                    }}
                  >
                    <RefreshCw size={12} />
                    Iniciar Sync
                  </button>
                )}
                {done && (
                  <button
                    onClick={() => setOpen(false)}
                    className="px-4 py-1.5 rounded-lg text-xs font-bold transition-all"
                    style={{
                      background: 'rgba(255,255,255,0.06)',
                      border: '1px solid rgba(255,255,255,0.1)',
                      color: '#888',
                    }}
                  >
                    Fechar
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
