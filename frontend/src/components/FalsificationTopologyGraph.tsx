import React, { useState } from 'react';
import { VerificationResult } from '../types/falsify';

interface Props {
  result: VerificationResult | null;
  isStreaming: boolean;
  onSelectNode?: (nodeId: string) => void;
}

interface HexNode {
  id: string;
  name: string;
  stageName: string;
  cx: number;
  cy: number;
  category: 'discover' | 'guard' | 'remediate' | 'validate' | 'diagnose' | 'verify' | 'attack';
  description: string;
}

export const FalsificationTopologyGraph: React.FC<Props> = ({
  result,
  isStreaming,
  onSelectNode,
}) => {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  // Derive metrics
  const contradictionsCount = result?.contradictions?.length ?? 0;
  const hypothesesCount = result?.hypotheses?.length ?? 0;
  const isRefuted = result?.verdict === 'REFUTED' || result?.verdict === 'CONFLICTED';

  // 7 Hexagonal Agent Nodes positioned around center (500, 260)
  const nodes: HexNode[] = [
    {
      id: 'n_discover',
      name: 'DISCOVER',
      stageName: 'retrieval',
      cx: 500,
      cy: 70,
      category: 'discover',
      description: 'Multi-source adversarial web & academic evidence crawler',
    },
    {
      id: 'n_guard',
      name: 'GUARD',
      stageName: 'credibility',
      cx: 680,
      cy: 150,
      category: 'guard',
      description: 'Tier-1 regulatory authority & domain provenance filter',
    },
    {
      id: 'n_remediate',
      name: 'REMEDIATE',
      stageName: 'fusion',
      cx: 680,
      cy: 370,
      category: 'remediate',
      description: 'Dialectic evidence synthesis & cross-source reconciliation',
    },
    {
      id: 'n_validate',
      name: 'VALIDATE',
      stageName: 'synthesis',
      cx: 500,
      cy: 450,
      category: 'validate',
      description: 'Autonomous epistemic arbiter & verdict synthesizer',
    },
    {
      id: 'n_diagnose',
      name: 'DIAGNOSE',
      stageName: 'contradictions',
      cx: 320,
      cy: 370,
      category: 'diagnose',
      description: 'Adversarial contradiction matrix & empirical disproof audit',
    },
    {
      id: 'n_verify',
      name: 'VERIFY',
      stageName: 'epistemic',
      cx: 220,
      cy: 260,
      category: 'verify',
      description: 'Popperian falsification threshold & margin validation',
    },
    {
      id: 'n_attack',
      name: 'ATTACK',
      stageName: 'hypotheses',
      cx: 320,
      cy: 150,
      category: 'attack',
      description: 'Adversarial counter-claim generator & red-team vectors',
    },
  ];

  // Helper to compute vertices of a pointed-top hexagon
  const getHexagonPoints = (cx: number, cy: number, r: number = 24): string => {
    const angles = [30, 90, 150, 210, 270, 330];
    return angles
      .map((deg) => {
        const rad = (deg * Math.PI) / 180;
        const x = cx + r * Math.cos(rad);
        const y = cy + r * Math.sin(rad);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');
  };

  // Generate spiderweb concentric polygon loops around center (500, 260)
  const webRings = [26, 52, 80, 112, 146];
  const webSpokes = 12; // 12 radial spines

  return (
    <div className="w-full bg-[#080c16] rounded-2xl border border-[#141d2f] shadow-[0_15px_40px_rgba(0,0,0,0.85)] relative overflow-hidden select-none p-3 sm:p-6 my-2">
      {/* Background Subtle Labyrinth/Circuit Motif */}
      <div className="absolute inset-0 opacity-[0.03] pointer-events-none bg-[radial-gradient(#00f5d4_1px,transparent_1px)] [background-size:24px_24px]" />

      {/* Main SVG Hero Canvas */}
      <div className="relative w-full flex justify-center items-center">
        <svg
          viewBox="0 0 1000 520"
          className="w-full max-w-[1000px] h-auto"
          style={{ minHeight: '360px' }}
        >
          <defs>
            {/* Glow Filters */}
            <filter id="glowGreenHex" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
            <filter id="glowCyanHex" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="5" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
            <filter id="glowRoseHex" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="5" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
            <filter id="glowCore" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>

            {/* Circuit Laser Gradients */}
            <linearGradient id="laserCyanGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#00f5d4" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#0284c7" stopOpacity="0.4" />
            </linearGradient>
            <linearGradient id="laserGreenGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#00f5a0" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#0f766e" stopOpacity="0.3" />
            </linearGradient>
          </defs>

          {/* ============================================================== */}
          {/* 1. CENTRAL SPIDERWEB CONSTELLATION MESH (Center: 500, 260)     */}
          {/* ============================================================== */}
          <g id="spiderweb-constellation">
            {/* Concentric Polygonal Web Rings */}
            {webRings.map((radius, rIdx) => {
              const points = Array.from({ length: webSpokes }).map((_, sIdx) => {
                const angle = (sIdx * 360) / webSpokes;
                // Add tiny organic geometric offset
                const jitter = (sIdx % 2 === 0 ? 1 : -1) * (rIdx * 1.2);
                const rad = (angle * Math.PI) / 180;
                const x = 500 + (radius + jitter) * Math.cos(rad);
                const y = 260 + (radius + jitter) * Math.sin(rad);
                return `${x.toFixed(1)},${y.toFixed(1)}`;
              });

              return (
                <polygon
                  key={`web-ring-${rIdx}`}
                  points={points.join(' ')}
                  fill="none"
                  stroke={rIdx === webRings.length - 1 ? '#0c3547' : '#0c2438'}
                  strokeWidth={rIdx === 0 ? '1' : '0.8'}
                  strokeDasharray={rIdx % 2 === 1 ? '3,2' : undefined}
                  opacity="0.85"
                />
              );
            })}

            {/* Radial Web Spines radiating from (500, 260) */}
            {Array.from({ length: webSpokes }).map((_, sIdx) => {
              const angle = (sIdx * 360) / webSpokes;
              const rad = (angle * Math.PI) / 180;
              const outerR = webRings[webRings.length - 1];
              const x2 = 500 + outerR * Math.cos(rad);
              const y2 = 260 + outerR * Math.sin(rad);

              return (
                <line
                  key={`web-spine-${sIdx}`}
                  x1="500"
                  y1="260"
                  x2={x2.toFixed(1)}
                  y2={y2.toFixed(1)}
                  stroke="#0f344d"
                  strokeWidth="0.85"
                  opacity="0.9"
                />
              );
            })}

            {/* Cross-Filaments (Organic web diagonals) */}
            <line x1="480" y1="210" x2="525" y2="212" stroke="#124866" strokeWidth="0.7" opacity="0.7" />
            <line x1="535" y1="225" x2="560" y2="255" stroke="#124866" strokeWidth="0.7" opacity="0.7" />
            <line x1="555" y1="275" x2="530" y2="305" stroke="#124866" strokeWidth="0.7" opacity="0.7" />
            <line x1="475" y1="310" x2="445" y2="290" stroke="#124866" strokeWidth="0.7" opacity="0.7" />
            <line x1="440" y1="245" x2="470" y2="218" stroke="#124866" strokeWidth="0.7" opacity="0.7" />

            {/* Web Vertex Intersections Glow Points */}
            <circle cx="480" cy="210" r="1.8" fill="#00d2ff" opacity="0.7" />
            <circle cx="525" cy="212" r="1.8" fill="#00d2ff" opacity="0.7" />
            <circle cx="560" cy="255" r="1.8" fill="#00d2ff" opacity="0.7" />
            <circle cx="530" cy="305" r="1.8" fill="#00d2ff" opacity="0.7" />
            <circle cx="475" cy="310" r="1.8" fill="#00d2ff" opacity="0.7" />
            <circle cx="440" cy="245" r="1.8" fill="#00d2ff" opacity="0.7" />

            {/* Central Core Glowing Orb */}
            <circle
              cx="500"
              cy="260"
              r="24"
              fill="none"
              stroke="#00f5d4"
              strokeWidth="1"
              opacity="0.25"
              className="animate-pulse"
            />
            <circle
              cx="500"
              cy="260"
              r="14"
              fill="none"
              stroke="#00d2ff"
              strokeWidth="1.5"
              opacity="0.4"
            />
            <circle
              cx="500"
              cy="260"
              r="7.5"
              fill="#00f5d4"
              filter="url(#glowCore)"
            />
            <circle
              cx="500"
              cy="260"
              r="3.5"
              fill="#ffffff"
            />
          </g>

          {/* ============================================================== */}
          {/* 2. CIRCUIT TRACES TO HEXAGONAL NODES                           */}
          {/* ============================================================== */}
          <g id="circuit-connectors">
            {/* 1. DISCOVER Trace (Top 12 o'clock: 500, 70) */}
            <path
              d="M 500 96 L 500 185"
              fill="none"
              stroke="#00f5a0"
              strokeWidth="1.5"
              opacity="0.8"
            />
            <circle cx="500" cy="185" r="3" fill="#00f5a0" />

            {/* 2. GUARD Trace (Top right: 680, 150) */}
            <path
              d="M 654 150 L 595 150 L 555 210"
              fill="none"
              stroke="#00f5a0"
              strokeWidth="1.5"
              opacity="0.8"
            />
            <circle cx="555" cy="210" r="3" fill="#00f5a0" />

            {/* 3. REMEDIATE Trace (Bottom right: 680, 370) */}
            <path
              d="M 654 370 L 595 370 L 555 310"
              fill="none"
              stroke="#00f5a0"
              strokeWidth="1.5"
              opacity="0.8"
            />
            <circle cx="555" cy="310" r="3" fill="#00f5a0" />

            {/* 4. VALIDATE Trace (Bottom 6 o'clock: 500, 450 - Glowing Cyan/Blue in Reference!) */}
            <path
              d="M 500 424 L 500 335"
              fill="none"
              stroke="#00d2ff"
              strokeWidth="2"
              opacity="0.9"
              filter="url(#glowCyanHex)"
            />
            <circle cx="500" cy="335" r="3.5" fill="#00d2ff" filter="url(#glowCyanHex)" />

            {/* 5. DIAGNOSE Trace (Bottom left: 320, 370) */}
            <path
              d="M 346 370 L 405 370 L 445 310"
              fill="none"
              stroke={contradictionsCount > 0 && result ? '#00f5a0' : '#00f5a0'}
              strokeWidth="1.5"
              opacity="0.8"
            />
            <circle cx="445" cy="310" r="3" fill="#00f5a0" />

            {/* 6. VERIFY Trace (Middle left: 220, 260) */}
            <path
              d="M 246 260 L 375 260"
              fill="none"
              stroke="#00f5a0"
              strokeWidth="1.5"
              opacity="0.8"
            />
            <circle cx="375" cy="260" r="3" fill="#00f5a0" />

            {/* 7. ATTACK Trace (Top left: 320, 150) */}
            <path
              d="M 346 150 L 405 150 L 445 210"
              fill="none"
              stroke="#00f5a0"
              strokeWidth="1.5"
              opacity="0.8"
            />
            <circle cx="445" cy="210" r="3" fill="#00f5a0" />
          </g>

          {/* ============================================================== */}
          {/* 3. HEXAGONAL AGENT NODES (7 Autonomous Agents)                 */}
          {/* ============================================================== */}
          <g id="hexagonal-agents">
            {nodes.map((node) => {
              const isHovered = hoveredNode === node.id;
              const isValidateNode = node.category === 'validate';

              // Determine color palette matching reference image:
              // VALIDATE is glowing cyan/blue; other completed nodes are emerald green (#00f5a0)
              const strokeColor = isValidateNode
                ? '#00d2ff'
                : isRefuted && node.category === 'diagnose'
                ? '#ff3366'
                : '#00f5a0';

              const glowFilter = isValidateNode
                ? 'url(#glowCyanHex)'
                : isRefuted && node.category === 'diagnose'
                ? 'url(#glowRoseHex)'
                : 'url(#glowGreenHex)';

              const fillColor = isHovered
                ? '#0a1d2e'
                : isValidateNode
                ? '#051926'
                : '#081a18';

              return (
                <g
                  key={node.id}
                  className="cursor-pointer group"
                  onClick={() => onSelectNode?.(node.id)}
                  onMouseEnter={() => setHoveredNode(node.id)}
                  onMouseLeave={() => setHoveredNode(null)}
                >
                  {/* Hexagon Outer Glow Filtered Polygon */}
                  <polygon
                    points={getHexagonPoints(node.cx, node.cy, 26)}
                    fill={fillColor}
                    stroke={strokeColor}
                    strokeWidth={isHovered ? '2.5' : isValidateNode ? '2.2' : '1.8'}
                    filter={glowFilter}
                    className="transition-all duration-200"
                  />

                  {/* Inner subtle hexagon border */}
                  <polygon
                    points={getHexagonPoints(node.cx, node.cy, 22)}
                    fill="none"
                    stroke={strokeColor}
                    strokeWidth="0.7"
                    opacity="0.4"
                  />

                  {/* Centered Icon inside Hexagon */}
                  {isValidateNode ? (
                    // VALIDATE Active Center Pulse Icon
                    <circle
                      cx={node.cx}
                      cy={node.cy}
                      r="5"
                      fill="#00d2ff"
                      className="animate-pulse"
                    />
                  ) : (
                    // Emerald Checkmark Icon matching the reference image!
                    <path
                      d={`M ${node.cx - 6} ${node.cy} L ${node.cx - 2} ${node.cy + 4} L ${node.cx + 6} ${node.cy - 5}`}
                      fill="none"
                      stroke={strokeColor}
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  )}

                  {/* Monospace Node Label Underneath */}
                  <text
                    x={node.cx}
                    y={node.cy + 42}
                    textAnchor="middle"
                    fill={strokeColor}
                    fontSize="9.5"
                    fontFamily="monospace"
                    fontWeight="bold"
                    letterSpacing="0.1em"
                    className="transition-colors select-none"
                  >
                    {node.name}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>

        {/* ============================================================== */}
        {/* 4. LEFT SIDE METRIC COUNTER (Errors / Contradictions)          */}
        {/* ============================================================== */}
        <div className="absolute left-4 sm:left-10 top-1/2 -translate-y-1/2 flex flex-col items-start select-none">
          <span className="text-[10px] sm:text-xs font-display font-bold tracking-widest text-[#ff3864]/90 uppercase">
            CONTRADICTIONS
          </span>
          <span className="font-mono font-black text-3xl sm:text-5xl text-[#ff3864] tracking-tight drop-shadow-[0_0_15px_rgba(255,56,100,0.4)] my-0.5">
            {contradictionsCount}
          </span>
          <span className="text-[10px] font-mono text-cyan-400 font-semibold tracking-wider mt-1.5">
            HYPOTHESES: {hypothesesCount}
          </span>
        </div>

        {/* ============================================================== */}
        {/* 5. BOTTOM-LEFT BRANDING (Falsify Core / Architecture)          */}
        {/* ============================================================== */}
        <div className="absolute bottom-4 left-4 sm:bottom-6 sm:left-8 select-none">
          <div className="flex items-center gap-2">
            <span className="font-display font-bold text-sm sm:text-base tracking-wider text-white">
              Falsify Core
            </span>
            {isStreaming && (
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping shadow-[0_0_8px_#00f5d4]" />
            )}
          </div>
          <div className="font-sans text-[10px] sm:text-[11px] text-slate-400 font-medium">
            Autonomous Adversarial Research &amp; Epistemic Engine
          </div>
        </div>

        {/* Hovered Node Description Tooltip */}
        {hoveredNode && (
          <div className="absolute top-4 right-4 sm:right-8 bg-[#0c1322]/90 border border-cyan-500/40 rounded-lg px-3 py-1.5 backdrop-blur-md text-[11px] font-mono text-cyan-300 shadow-[0_0_15px_rgba(6,182,212,0.25)] select-none pointer-events-none">
            {nodes.find((n) => n.id === hoveredNode)?.description}
          </div>
        )}
      </div>
    </div>
  );
};
