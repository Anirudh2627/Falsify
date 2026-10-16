import React from 'react';
import { CheckCircle2, AlertTriangle, GitFork, XCircle, HelpCircle } from 'lucide-react';
import { Verdict } from '../types/falsify';

interface Props {
  verdict: Verdict | string;
  size?: 'sm' | 'md' | 'lg';
}

export const VerdictBadge: React.FC<Props> = ({ verdict, size = 'md' }) => {
  const normalized = (verdict || 'UNVERIFIABLE').toUpperCase();

  const config = {
    VERIFIED: {
      label: 'VERIFIED',
      bg: 'bg-emerald-950/70 text-emerald-300 border-emerald-500/60 shadow-[0_0_12px_rgba(16,185,129,0.35)]',
      icon: CheckCircle2,
      desc: 'Corroborated by high-quality independent sources',
    },
    QUALIFIED: {
      label: 'QUALIFIED',
      bg: 'bg-amber-950/70 text-amber-300 border-amber-500/60 shadow-[0_0_12px_rgba(245,158,11,0.35)]',
      icon: AlertTriangle,
      desc: 'Partially accurate or subject to conditions',
    },
    CONFLICTED: {
      label: 'CONFLICTED',
      bg: 'bg-orange-950/70 text-orange-300 border-orange-500/60 shadow-[0_0_12px_rgba(249,115,22,0.35)]',
      icon: GitFork,
      desc: 'Contradictory evidence from credible sources',
    },
    REFUTED: {
      label: 'REFUTED',
      bg: 'bg-rose-950/70 text-rose-300 border-rose-500/60 shadow-[0_0_15px_rgba(244,63,94,0.4)]',
      icon: XCircle,
      desc: 'Contradicted by authoritative evidence',
    },
    UNVERIFIABLE: {
      label: 'UNVERIFIABLE',
      bg: 'bg-slate-900/80 text-slate-300 border-slate-700 shadow-sm',
      icon: HelpCircle,
      desc: 'Insufficient or ambiguous evidence',
    },
  }[normalized] || {
    label: normalized,
    bg: 'bg-slate-900/80 text-slate-300 border-slate-700 shadow-sm',
    icon: HelpCircle,
    desc: 'Unknown verdict state',
  };

  const Icon = config.icon;

  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5 gap-1',
    md: 'text-xs sm:text-sm px-2.5 py-1 gap-1.5 font-mono font-bold tracking-wider',
    lg: 'text-sm sm:text-base px-3.5 py-1.5 gap-2 font-mono font-bold tracking-wider',
  }[size];

  const iconSizes = {
    sm: 'w-3.5 h-3.5',
    md: 'w-4 h-4',
    lg: 'w-5 h-5',
  }[size];

  return (
    <span
      className={`inline-flex items-center rounded-lg border uppercase ${config.bg} ${sizeClasses}`}
      title={config.desc}
      role="status"
      aria-label={`Verdict: ${config.label}`}
    >
      <Icon className={`${iconSizes} shrink-0`} aria-hidden="true" />
      <span>{config.label}</span>
    </span>
  );
};
