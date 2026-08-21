'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { api, GraphData } from '@/lib/api';

// ── Types ──────────────────────────────────────────────────────────────────
interface GraphNode {
  id: string;
  label: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  posts: number;
  color: string;
  layer: 'offensive' | 'defensive' | 'ai' | 'reality';
  pulsePhase: number;
  isNew?: boolean;
  isTrending?: boolean;
}

interface GraphEdge {
  source: string;
  target: string;
  curvature: number;
}

interface FlowParticle {
  edgeIndex: number;
  t: number;
  speed: number;
  isRipple?: boolean;
  rippleAlpha?: number;
}

// ── Layer helpers ──────────────────────────────────────────────────────────
const LAYER_NAMES = ['offensive', 'defensive', 'ai', 'reality', 'orbital'] as const;

const LAYER_COLORS: Record<string, string> = {
  offensive: '#ff008c',
  defensive: '#06b6d4',
  ai: '#f97316',
  reality: '#cbd5e1',
  orbital: '#f59e0b',
};

const LAYER_LABELS: Record<string, string> = {
  offensive: 'Offensive Security',
  defensive: 'Defensive & SOC',
  ai: 'AI & Emerging Threats',
  reality: 'Cyber Reality & Fundamentals',
  orbital: 'Gerais',
};

// Each non-orbital layer clusters around its own anchor point instead of
// all collapsing onto the canvas center — orbital (Gerais) stays put at the center.
const LAYER_ANCHOR_ANGLE: Record<string, number | null> = {
  offensive: -Math.PI / 2,
  defensive: 0,
  ai: Math.PI / 2,
  reality: Math.PI,
  orbital: null,
};

function layerAnchor(layer: string, w: number, h: number) {
  const cx = w / 2;
  const cy = h / 2;
  const angle = LAYER_ANCHOR_ANGLE[layer];
  if (angle == null) return { x: cx, y: cy };
  const orbitR = Math.min(w, h) * 0.32;
  return { x: cx + Math.cos(angle) * orbitR, y: cy + Math.sin(angle) * orbitR };
}

// ── Component ──────────────────────────────────────────────────────────────
export default function KnowledgeGraph({ onNavigate }: { onNavigate?: (view: string, disciplineId: number, disciplineName: string) => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const nodesRef = useRef<GraphNode[]>([]);
  const edgesRef = useRef<GraphEdge[]>([]);
  const particlesRef = useRef<FlowParticle[]>([]);
  const mouseRef = useRef({ x: -9999, y: -9999 });
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);

  const buildGraph = useCallback((w: number, h: number, data?: GraphData) => {
    let nodes: GraphNode[];
    let edges: GraphEdge[];

    if (data && data.nodes.length > 0) {
      nodes = data.nodes.map((n, i) => {
        const layer = LAYER_NAMES[n.layer] as GraphNode['layer'];
        const anchor = layerAnchor(layer, w, h);
        return {
          id: String(n.id),
          label: n.label,
          x: anchor.x + (Math.random() - 0.5) * 70,
          y: anchor.y + (Math.random() - 0.5) * 70,
          vx: (Math.random() - 0.5) * 0.12,
          vy: (Math.random() - 0.5) * 0.12,
          radius: 4.5 + Math.pow(n.posts, 0.68) * 2.2,
          posts: n.posts,
          color: n.color,
          layer,
          pulsePhase: Math.random() * Math.PI * 2,
          isNew: n.is_new,
          isTrending: n.is_trending,
        };
      });

      edges = data.edges.map((e, i) => ({
        source: String(e.source),
        target: String(e.target),
        curvature: (Math.sin(i * 1.618) * 0.18 + 0.12) * (i % 2 === 0 ? 1 : -1),
      }));
    } else {
      nodes = [];
      edges = [];
    }

    // Normal ambient flow particles
    const particles: FlowParticle[] = edges.map((_, i) => ({
      edgeIndex: i,
      t: Math.random(),
      speed: 0.0007 + Math.random() * 0.0005,
    }));

    // Ripple particles originating from "new" nodes — MELHORIA 7
    nodes.filter(n => n.isNew || n.isTrending).forEach(newNode => {
      edges.forEach((e, ei) => {
        if (e.source === newNode.id || e.target === newNode.id) {
          particles.push({
            edgeIndex: ei,
            t: e.source === newNode.id ? 0 : 1,
            speed: (e.source === newNode.id ? 1 : -1) * (0.0018 + Math.random() * 0.0008),
            isRipple: true,
            rippleAlpha: 1,
          });
        }
      });
    });

    nodesRef.current = nodes;
    edgesRef.current = edges;
    particlesRef.current = particles;
  }, []);

  // Fetch graph data from API
  useEffect(() => {
    api.graph.get()
      .then(data => {
        setGraphData(data);
        const canvas = canvasRef.current;
        if (canvas) {
          const w = canvas.width || 600;
          const h = canvas.height || 500;
          buildGraph(w, h, data);
        }
      })
      .catch(() => setGraphData(null))
      .finally(() => setLoading(false));
  }, [buildGraph]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const resize = () => {
      const rect = canvas.parentElement?.getBoundingClientRect();
      if (!rect) return;
      canvas.width = rect.width;
      canvas.height = rect.height;
      if (nodesRef.current.length === 0) buildGraph(rect.width, rect.height);
    };

    resize();
    if (nodesRef.current.length === 0) {
      const r = canvas.getBoundingClientRect();
      buildGraph(r.width || 600, r.height || 500);
    }

    // Slow drift — MELHORIA 1 (graph reorganizes slowly) + MELHORIA 10
    const driftTimer = setInterval(() => {
      for (const n of nodesRef.current) {
        n.vx += (Math.random() - 0.5) * 0.05;
        n.vy += (Math.random() - 0.5) * 0.05;
      }
    }, 9000);

    const getNode = (id: string) => nodesRef.current.find(n => n.id === id);

    const bezierPoint = (t: number, p0x: number, p0y: number, cpx: number, cpy: number, p1x: number, p1y: number) => ({
      x: (1 - t) * (1 - t) * p0x + 2 * (1 - t) * t * cpx + t * t * p1x,
      y: (1 - t) * (1 - t) * p0y + 2 * (1 - t) * t * cpy + t * t * p1y,
    });

    const draw = (time: number) => {
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      const w = canvas.width;
      const h = canvas.height;

      ctx.clearRect(0, 0, w, h);

      // ── MELHORIA 4: Atmospheric layered background ──────────────────────
      const bg = [
        { x: 0.22, y: 0.25, r: 0.65, c: 'rgba(255,0,140,0.06)' },
        { x: 0.78, y: 0.72, r: 0.5,  c: 'rgba(6,182,212,0.04)' },
        { x: 0.5,  y: 1.0,  r: 0.45, c: 'rgba(249,115,22,0.03)' },
        { x: 0.85, y: 0.15, r: 0.35, c: 'rgba(255,0,140,0.03)' },
      ];
      for (const b of bg) {
        const g = ctx.createRadialGradient(w * b.x, h * b.y, 0, w * b.x, h * b.y, Math.max(w, h) * b.r);
        g.addColorStop(0, b.c);
        g.addColorStop(1, 'transparent');
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, w, h);
      }

      const nodes = nodesRef.current;
      const edges = edgesRef.current;
      const particles = particlesRef.current;

      // ── Physics ─────────────────────────────────────────────────────────
      for (const n of nodes) {
        for (const m of nodes) {
          if (n === m) continue;
          const dx = n.x - m.x;
          const dy = n.y - m.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const minD = (n.radius + m.radius) * 7.5;
          if (dist < minD) {
            const f = ((minD - dist) / minD) * 0.022;
            n.vx += (dx / dist) * f;
            n.vy += (dy / dist) * f;
          }
        }
        const anchor = layerAnchor(n.layer, w, h);
        const pull = 0.00010 + 0.00002 * (1 - n.posts / 18);
        n.vx += (anchor.x - n.x) * pull;
        n.vy += (anchor.y - n.y) * pull;
        n.vx *= 0.97;
        n.vy *= 0.97;
        n.x += n.vx;
        n.y += n.vy;
        n.x = Math.max(n.radius + 14, Math.min(w - n.radius - 14, n.x));
        n.y = Math.max(n.radius + 14, Math.min(h - n.radius - 14, n.y));
      }

      // ── Hover detection ──────────────────────────────────────────────────
      const mx = mouseRef.current.x;
      const my = mouseRef.current.y;
      let hov: GraphNode | null = null;
      for (const n of nodes) {
        const dx = n.x - mx;
        const dy = n.y - my;
        if (dx * dx + dy * dy < (n.radius + 10) * (n.radius + 10)) { hov = n; break; }
      }
      setHoveredNode(hov);

      // ── MELHORIA 2: Curved edges ─────────────────────────────────────────
      for (let i = 0; i < edges.length; i++) {
        const e = edges[i];
        const src = getNode(e.source);
        const tgt = getNode(e.target);
        if (!src || !tgt) continue;

        const midX = (src.x + tgt.x) / 2;
        const midY = (src.y + tgt.y) / 2;
        const dx = tgt.x - src.x;
        const dy = tgt.y - src.y;
        const len = Math.sqrt(dx * dx + dy * dy) || 1;
        const cpx = midX + (-dy / len) * len * e.curvature;
        const cpy = midY + (dx / len) * len * e.curvature;

        const isHovEdge = hov && (hov.id === e.source || hov.id === e.target);
        const isSelEdge = selectedNode && (selectedNode.id === e.source || selectedNode.id === e.target);

        ctx.beginPath();
        ctx.moveTo(src.x, src.y);
        ctx.quadraticCurveTo(cpx, cpy, tgt.x, tgt.y);

        if (isSelEdge) {
          ctx.strokeStyle = src.color + 'cc';
          ctx.lineWidth = 1.6;
          ctx.shadowColor = src.color;
          ctx.shadowBlur = 10;
        } else if (isHovEdge) {
          ctx.strokeStyle = src.color + '88';
          ctx.lineWidth = 1.1;
          ctx.shadowColor = src.color;
          ctx.shadowBlur = 7;
        } else {
          ctx.strokeStyle = src.color + '55';
          ctx.lineWidth = 0.9;
          ctx.shadowBlur = 0;
        }
        ctx.stroke();
        ctx.shadowBlur = 0;
      }

      // ── MELHORIA 2+7: Flow particles & ripples ───────────────────────────
      for (const p of particles) {
        const spd = p.speed;
        p.t += spd;

        // Ripple particles bounce back and fade
        if (p.isRipple) {
          if (p.t > 1 || p.t < 0) {
            p.speed = -p.speed;
            p.rippleAlpha = (p.rippleAlpha ?? 1) * 0.72;
            if ((p.rippleAlpha ?? 0) < 0.05) {
              p.t = spd > 0 ? 0 : 1;
              p.rippleAlpha = 0.9;
            }
          }
        } else {
          if (p.t > 1) p.t -= 1;
        }

        const e = edges[p.edgeIndex];
        if (!e) continue;
        const src = getNode(e.source);
        const tgt = getNode(e.target);
        if (!src || !tgt) continue;

        const midX = (src.x + tgt.x) / 2;
        const midY = (src.y + tgt.y) / 2;
        const dx = tgt.x - src.x;
        const dy = tgt.y - src.y;
        const len = Math.sqrt(dx * dx + dy * dy) || 1;
        const cpx = midX + (-dy / len) * len * e.curvature;
        const cpy = midY + (dx / len) * len * e.curvature;

        const t = Math.max(0, Math.min(1, p.t));
        const pt = bezierPoint(t, src.x, src.y, cpx, cpy, tgt.x, tgt.y);

        const isEdgeActive = hov && (hov.id === e.source || hov.id === e.target);
        const alpha = p.isRipple
          ? (p.rippleAlpha ?? 0.9)
          : isEdgeActive ? 0.85 : 0.18;
        const radius = p.isRipple ? 2.4 : isEdgeActive ? 1.8 : 1.1;

        ctx.beginPath();
        ctx.arc(pt.x, pt.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = src.color + Math.round(alpha * 255).toString(16).padStart(2, '0');
        if (p.isRipple || isEdgeActive) {
          ctx.shadowColor = src.color;
          ctx.shadowBlur = p.isRipple ? 10 : 5;
        }
        ctx.fill();
        ctx.shadowBlur = 0;
      }

      // ── MELHORIA 1+3+8+9: Nodes ──────────────────────────────────────────
      // Bigger nodes (and the hovered/selected one) claim label space first —
      // renderNodes only reorders drawing, edges/particles above still use `nodes`.
      const renderNodes = [...nodes].sort((a, b) => {
        if (a.id === hov?.id || a.id === selectedNode?.id) return -1;
        if (b.id === hov?.id || b.id === selectedNode?.id) return 1;
        return b.radius - a.radius;
      });
      const labelRects: { x0: number; y0: number; x1: number; y1: number }[] = [];
      for (const n of renderNodes) {
        const isHov = hov?.id === n.id;
        const isSel = selectedNode?.id === n.id;
        const pulse = Math.sin(time * 0.0014 + n.pulsePhase) * 0.5 + 0.5;
        const trendPulse = n.isTrending ? Math.sin(time * 0.0028 + n.pulsePhase) * 0.5 + 0.5 : 0;

        // Outer atmospheric glow
        const glowR = isHov ? n.radius * 4.2 : n.radius * (2.0 + pulse * 0.7 + trendPulse * 1.0);
        const glowA = isHov ? 0.52 : 0.1 + pulse * 0.07 + trendPulse * 0.12;
        const glowGrad = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, glowR);
        const hexA = Math.round(glowA * 255).toString(16).padStart(2, '0');
        const hexA2 = Math.round(glowA * 0.35 * 255).toString(16).padStart(2, '0');
        glowGrad.addColorStop(0, n.color + hexA);
        glowGrad.addColorStop(0.45, n.color + hexA2);
        glowGrad.addColorStop(1, 'transparent');
        ctx.beginPath();
        ctx.arc(n.x, n.y, glowR, 0, Math.PI * 2);
        ctx.fillStyle = glowGrad;
        ctx.fill();

        // MELHORIA 3: Trending expanding ring pulse
        if (n.isTrending) {
          const ringR = n.radius + 4 + trendPulse * 9;
          const ringA = (1 - trendPulse) * 0.55;
          ctx.beginPath();
          ctx.arc(n.x, n.y, ringR, 0, Math.PI * 2);
          ctx.strokeStyle = n.color + Math.round(ringA * 255).toString(16).padStart(2, '0');
          ctx.lineWidth = 1.4;
          ctx.stroke();
        }

        // Selected halo
        if (isSel) {
          ctx.beginPath();
          ctx.arc(n.x, n.y, n.radius + 7, 0, Math.PI * 2);
          ctx.strokeStyle = n.color + 'cc';
          ctx.lineWidth = 2;
          ctx.shadowColor = n.color;
          ctx.shadowBlur = 18;
          ctx.stroke();
          ctx.shadowBlur = 0;
        }

        // MELHORIA 8: Node body with semantic size gradient
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
        const bodyGrad = ctx.createRadialGradient(
          n.x - n.radius * 0.28, n.y - n.radius * 0.28, 0,
          n.x, n.y, n.radius
        );
        bodyGrad.addColorStop(0, isHov ? '#ffffff' : n.color + 'f2');
        bodyGrad.addColorStop(1, n.color + '99');
        ctx.fillStyle = bodyGrad;
        ctx.shadowColor = n.color;
        ctx.shadowBlur = isHov ? 24 : isSel ? 20 : 8 + trendPulse * 8;
        ctx.fill();
        ctx.shadowBlur = 0;

        // Thin ring
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.radius + 1.5, 0, Math.PI * 2);
        ctx.strokeStyle = isHov ? n.color + 'ff' : n.color + '50';
        ctx.lineWidth = isHov ? 1.5 : 0.7;
        ctx.stroke();

        // Label — skip drawing if it would collide with an already-placed label,
        // unless this node is hovered/selected (those always win a spot).
        const fs = isHov ? 11 : n.radius > 13 ? 10 : 9;
        ctx.font = `${isHov || isSel ? 600 : 500} ${fs}px Inter, sans-serif`;
        const labelY = n.y + n.radius + 13;
        const textW = ctx.measureText(n.label).width;
        const rect = {
          x0: n.x - textW / 2 - 3,
          y0: labelY - fs,
          x1: n.x + textW / 2 + 3,
          y1: labelY + 4,
        };
        const collides = labelRects.some(
          r => rect.x0 < r.x1 && rect.x1 > r.x0 && rect.y0 < r.y1 && rect.y1 > r.y0
        );
        if (isHov || isSel || !collides) {
          const lAlpha = isHov || isSel ? 1 : 0.48 + pulse * 0.18;
          ctx.fillStyle = `rgba(238,238,238,${lAlpha})`;
          ctx.textAlign = 'center';
          ctx.shadowColor = 'rgba(0,0,0,0.9)';
          ctx.shadowBlur = 5;
          ctx.fillText(n.label, n.x, labelY);
          ctx.shadowBlur = 0;
          labelRects.push(rect);
        }

        // MELHORIA 7: NEW badge
        if (n.isNew) {
          const bx = n.x + n.radius * 0.65;
          const by = n.y - n.radius * 0.72;
          ctx.font = 'bold 7px Inter, sans-serif';
          ctx.fillStyle = '#ff008c';
          ctx.textAlign = 'center';
          ctx.shadowColor = '#ff008c';
          ctx.shadowBlur = 8;
          ctx.fillText('NEW', bx, by);
          ctx.shadowBlur = 0;
        }
      }

      animRef.current = requestAnimationFrame(draw);
    };

    animRef.current = requestAnimationFrame(draw);

    const ro = new ResizeObserver(resize);
    if (canvas.parentElement) ro.observe(canvas.parentElement);

    return () => {
      cancelAnimationFrame(animRef.current);
      clearInterval(driftTimer);
      ro.disconnect();
    };
  }, [buildGraph]);

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    mouseRef.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    setTooltipPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  const handleMouseLeave = () => { mouseRef.current = { x: -9999, y: -9999 }; };

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;
    const clicked = nodesRef.current.find(n => {
      const dx = n.x - cx; const dy = n.y - cy;
      return dx * dx + dy * dy < (n.radius + 10) * (n.radius + 10);
    });
    setSelectedNode(prev => prev?.id === clicked?.id ? null : (clicked ?? null));
  };

  return (
    <div className="relative w-full h-full">
      <canvas
        ref={canvasRef}
        className="w-full h-full cursor-crosshair"
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        onClick={handleClick}
      />

      {loading && (
        <div className="absolute inset-0 flex items-center justify-center z-30">
          <div className="w-6 h-6 border-2 border-[#ff008c] border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {/* Hover tooltip */}
      {hoveredNode && !selectedNode && (
        <div
          className="absolute pointer-events-none z-10 rounded-xl px-3 py-2.5 text-xs"
          style={{
            left: tooltipPos.x + 18,
            top: tooltipPos.y - 12,
            background: 'rgba(8,8,8,0.93)',
            border: `1px solid ${hoveredNode.color}30`,
            boxShadow: `0 0 28px ${hoveredNode.color}20`,
            backdropFilter: 'blur(10px)',
            transform: tooltipPos.x > 280 ? 'translateX(-110%)' : 'none',
          }}
        >
          <div className="font-semibold text-white mb-1">{hoveredNode.label}</div>
          <div className="text-[#9ca3af] mb-0.5">{hoveredNode.posts} publicações</div>
          <div className="text-[10px]" style={{ color: hoveredNode.color }}>
            {LAYER_LABELS[hoveredNode.layer]}
          </div>
          <div className="text-[#555] text-[10px] mt-1.5">clique para explorar →</div>
        </div>
      )}

      {/* MELHORIA 6: Selected node sidebar */}
      {selectedNode && (
        <div
          className="absolute right-2 top-2 bottom-2 w-48 rounded-xl flex flex-col overflow-hidden z-20"
          style={{
            background: 'rgba(6,6,6,0.95)',
            border: `1px solid ${selectedNode.color}28`,
            boxShadow: `0 0 40px ${selectedNode.color}14`,
            backdropFilter: 'blur(16px)',
          }}
        >
          {/* Header */}
          <div className="px-4 py-3 flex items-start justify-between" style={{ borderBottom: `1px solid ${selectedNode.color}18` }}>
            <div>
              <div className="text-white font-bold text-sm leading-tight">{selectedNode.label}</div>
              <div className="text-[10px] mt-0.5" style={{ color: selectedNode.color }}>
                {LAYER_LABELS[selectedNode.layer]}
              </div>
            </div>
            <button onClick={() => setSelectedNode(null)} className="text-[#444] hover:text-white transition-colors text-xl leading-none mt-[-2px]">×</button>
          </div>

          {/* Stats */}
          <div className="px-4 py-2.5 flex items-center gap-3" style={{ borderBottom: `1px solid rgba(255,255,255,0.04)` }}>
            <div>
              <div className="text-white font-bold text-lg leading-none">{selectedNode.posts}</div>
              <div className="text-[10px] text-[#555] mt-0.5">publicações</div>
            </div>
            {selectedNode.isTrending && (
              <div className="ml-auto flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: selectedNode.color }} />
                <span className="text-[10px]" style={{ color: selectedNode.color }}>trending</span>
              </div>
            )}
            {selectedNode.isNew && (
              <div className="ml-auto">
                <span className="text-[9px] font-bold px-1.5 py-0.5 rounded" style={{ background: '#ff008c', color: '#fff' }}>NEW</span>
              </div>
            )}
          </div>

          {/* Related */}
          <div className="px-4 py-3 flex-1 overflow-y-auto">
            <div className="text-[9px] uppercase tracking-widest text-[#3a3a3a] mb-2">Relacionados</div>
            {edgesRef.current
              .filter(e => e.source === selectedNode.id || e.target === selectedNode.id)
              .map(e => {
                const relId = e.source === selectedNode.id ? e.target : e.source;
                const rel = nodesRef.current.find(n => n.id === relId);
                if (!rel) return null;
                return (
                  <button
                    key={relId}
                    onClick={() => {
                      const found = nodesRef.current.find(x => x.id === relId);
                      if (found) setSelectedNode({ ...found });
                    }}
                    className="w-full flex items-center gap-2 py-1.5 text-left group"
                  >
                    <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: rel.color }} />
                    <span className="text-xs text-[#777] group-hover:text-white transition-colors truncate">{rel.label}</span>
                    <span className="text-[10px] text-[#333] ml-auto flex-shrink-0">{rel.posts}p</span>
                  </button>
                );
              })}
          </div>

          {/* Tags + CTA */}
          <div className="px-4 py-3" style={{ borderTop: `1px solid rgba(255,255,255,0.04)` }}>
            <div className="flex flex-wrap gap-1 mb-3">
              {['osint', 'recon', 'intel'].map(t => (
                <span key={t} className="text-[9px] px-1.5 py-0.5 rounded text-[#444] bg-[#1a1a1a]">#{t}</span>
              ))}
            </div>
            <button
              onClick={() => onNavigate?.('posts', Number(selectedNode.id), selectedNode.label)}
              className="w-full text-[11px] py-1.5 rounded-lg font-semibold transition-all"
              style={{ background: selectedNode.color + '18', color: selectedNode.color, border: `1px solid ${selectedNode.color}30` }}
            >
              Ver publicações →
            </button>
          </div>
        </div>
      )}

      {/* Legend — groups disciplines by color (dynamic, auto-detects new schools) */}
      <div className="absolute bottom-2 left-2 flex flex-col gap-1.5">
        {(() => {
          const byColor = new Map<string, string[]>();
          (graphData?.nodes || []).forEach(n => {
            const list = byColor.get(n.color) || [];
            list.push(n.label);
            byColor.set(n.color, list);
          });
          return Array.from(byColor.entries()).map(([color, names]) => (
            <div key={color} className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
              <span className="text-[9px] text-[#555]">{names.join(', ')}</span>
            </div>
          ));
        })()}
      </div>
    </div>
  );
}
