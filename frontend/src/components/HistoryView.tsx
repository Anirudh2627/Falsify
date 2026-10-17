import React, { useEffect, useState } from 'react';
import {
  History,
  Trash2,
  ChevronLeft,
  ChevronRight,
  Filter,
  Eye,
  AlertCircle,
  Loader2,
  CheckCircle2,
} from 'lucide-react';
import { deleteVerification, getVerificationById, getVerifications } from '../services/api';
import { PaginatedVerificationHistory, VerificationResult } from '../types/falsify';
import { VerdictBadge } from './VerdictBadge';

interface Props {
  onOpenResult: (result: VerificationResult) => void;
}

const VERDICT_OPTIONS = ['ALL', 'VERIFIED', 'QUALIFIED', 'CONFLICTED', 'REFUTED', 'UNVERIFIABLE'];

export const HistoryView: React.FC<Props> = ({ onOpenResult }) => {
  const [data, setData] = useState<PaginatedVerificationHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Pagination & filter state
  const [page, setPage] = useState(1);
  const pageSize = 10;
  const [selectedVerdict, setSelectedVerdict] = useState<string>('ALL');

  // Deletion modal state
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const fetchHistory = async () => {
    setLoading(true);
    setError(null);
    try {
      const vFilter = selectedVerdict === 'ALL' ? undefined : selectedVerdict;
      const res = await getVerifications(page, pageSize, vFilter);
      setData(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load history';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [page, pageSize, selectedVerdict]);

  const handleFilterChange = (v: string) => {
    setSelectedVerdict(v);
    setPage(1); // Reset to page 1 on filter change
  };

  const handleViewDetail = async (id: number) => {
    try {
      const full = await getVerificationById(id);
      onOpenResult(full);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to fetch verification detail');
    }
  };

  const handleConfirmDelete = async () => {
    if (deleteId === null) return;
    setIsDeleting(true);
    try {
      await deleteVerification(deleteId);
      setFeedback(`Record #${deleteId} deleted successfully.`);
      setDeleteId(null);
      await fetchHistory();
      setTimeout(() => setFeedback(null), 3000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete record');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="bg-[#0a0e17] rounded-xl border border-[#1b2538] shadow-[0_0_25px_rgba(0,0,0,0.7)] p-6 mb-8 font-sans">
      {/* Top Header & Filters */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#162033]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-blue-950/80 border border-blue-500/40 text-blue-400 flex items-center justify-center shadow-[0_0_10px_rgba(59,130,246,0.3)]">
            <History className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm sm:text-base font-bold text-white tracking-wide">Verification History</h2>
            <p className="text-xs text-slate-400">
              Audit log of past claim verifications, verdicts, and evidence traces.
            </p>
          </div>
        </div>

        {/* Verdict filter dropdown */}
        <div className="flex items-center gap-2 self-start sm:self-auto text-xs">
          <Filter className="w-3.5 h-3.5 text-slate-400" />
          <label htmlFor="verdict-filter" className="text-slate-400 font-medium">
            Filter:
          </label>
          <select
            id="verdict-filter"
            value={selectedVerdict}
            onChange={(e) => handleFilterChange(e.target.value)}
            className="text-xs rounded-lg border border-[#1e2a40] py-1.5 px-2 bg-[#0c121e] text-slate-200 focus:outline-none focus:border-cyan-500"
          >
            {VERDICT_OPTIONS.map((opt) => (
              <option key={opt} value={opt} className="bg-[#0c121e] text-slate-200">
                {opt === 'ALL' ? 'All Verdicts' : opt}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Feedback banner */}
      {feedback && (
        <div className="my-3 p-2.5 rounded-lg bg-emerald-950/50 border border-emerald-800/60 text-xs text-emerald-300 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{feedback}</span>
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="my-3 p-3 rounded-lg bg-rose-950/50 border border-rose-800/60 text-xs text-rose-300 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Table & List Area */}
      <div className="mt-4">
        {loading ? (
          <div className="py-12 flex flex-col items-center justify-center text-slate-400 gap-2">
            <Loader2 className="w-6 h-6 animate-spin text-cyan-400" />
            <span className="text-xs text-slate-400">Loading verification history...</span>
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="py-12 text-center text-sm text-slate-500 italic">
            No verification records found
            {selectedVerdict !== 'ALL' && ` matching verdict '${selectedVerdict}'`}.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-[#080d16] text-slate-400 font-bold border-b border-[#1b2538] uppercase tracking-wider text-[10px]">
                <tr>
                  <th scope="col" className="py-3 px-3">ID</th>
                  <th scope="col" className="py-3 px-3">Submitted Claim</th>
                  <th scope="col" className="py-3 px-3">Verdict</th>
                  <th scope="col" className="py-3 px-3">Confidence</th>
                  <th scope="col" className="py-3 px-3">Date</th>
                  <th scope="col" className="py-3 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#162033]">
                {data.items.map((item) => (
                  <tr key={item.id} className="hover:bg-[#0c1322] transition-colors">
                    <td className="py-3 px-3 font-sans font-semibold text-cyan-400">#{item.id}</td>
                    <td className="py-3 px-3 max-w-xs md:max-w-md truncate font-medium text-slate-200" title={item.claim_text}>
                      {item.claim_text}
                    </td>
                    <td className="py-3 px-3 whitespace-nowrap">
                      <VerdictBadge verdict={item.verdict} size="sm" />
                    </td>
                    <td className="py-3 px-3 font-sans font-bold text-slate-200 whitespace-nowrap">
                      {Math.round(item.confidence * 100)}%
                    </td>
                    <td className="py-3 px-3 text-slate-500 whitespace-nowrap">
                      {new Date(item.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-3 text-right whitespace-nowrap space-x-1">
                      <button
                        type="button"
                        onClick={() => handleViewDetail(item.id)}
                        className="p-1.5 rounded hover:bg-cyan-950/60 text-slate-400 hover:text-cyan-400 transition-colors"
                        title="View Full Reasoning Trace"
                        aria-label={`View detail for verification ${item.id}`}
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => setDeleteId(item.id)}
                        className="p-1.5 rounded hover:bg-rose-950/60 text-slate-400 hover:text-rose-400 transition-colors"
                        title="Delete Record"
                        aria-label={`Delete verification ${item.id}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        {data && data.total_pages > 1 && (
          <div className="flex items-center justify-between pt-4 border-t border-[#162033] text-xs text-slate-400 mt-4">
            <div>
              Showing <span className="font-bold text-slate-200">{(page - 1) * pageSize + 1}</span> to{' '}
              <span className="font-bold text-slate-200">
                {Math.min(page * pageSize, data.total)}
              </span>{' '}
              of <span className="font-bold text-slate-200">{data.total}</span> records
            </div>

            <div className="flex items-center gap-1">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(p - 1, 1))}
                className="p-1.5 rounded border border-[#1b2538] hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed"
                title="Previous Page"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="px-2 font-sans font-medium">
                {page} / {data.total_pages}
              </span>
              <button
                type="button"
                disabled={page >= data.total_pages}
                onClick={() => setPage((p) => Math.min(p + 1, data.total_pages))}
                className="p-1.5 rounded border border-[#1b2538] hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed"
                title="Next Page"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Confirmation Modal for Delete */}
      {deleteId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#0b0f19] rounded-xl max-w-sm w-full p-6 shadow-xl border border-rose-900/60 animate-in fade-in zoom-in-95 font-sans">
            <div className="flex items-center gap-3 text-rose-400 mb-3">
              <AlertCircle className="w-6 h-6" />
              <h3 className="text-base font-bold text-white">Delete Verification Record?</h3>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed font-sans">
              Are you sure you want to delete verification record #{deleteId}? This action permanently removes the stored evidence trace from SQLite history.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                disabled={isDeleting}
                onClick={() => setDeleteId(null)}
                className="px-3 py-1.5 text-xs font-semibold rounded-lg border border-slate-700 hover:bg-slate-800 text-slate-300"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isDeleting}
                onClick={handleConfirmDelete}
                className="px-3.5 py-1.5 text-xs font-bold rounded-lg bg-rose-600 hover:bg-rose-700 text-white shadow-[0_0_12px_rgba(244,63,94,0.4)] flex items-center gap-1.5 uppercase"
              >
                {isDeleting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>Delete Record</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
