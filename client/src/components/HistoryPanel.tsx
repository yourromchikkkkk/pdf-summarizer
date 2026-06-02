import {
  FileText,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Clock,
} from "lucide-react";
import type { DocumentRecord } from "../types";

interface Props {
  history: DocumentRecord[];
  selectedDocId: string | null;
  onSelect: (id: string) => void;
}

function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

export function HistoryPanel({ history, selectedDocId, onSelect }: Props) {
  return (
    <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800/80 rounded-2xl p-6 shadow-xl flex-1 flex flex-col min-h-87.5">
      <h2 className="text-base font-semibold text-slate-200 mb-4 flex items-center justify-between">
        <span>Processing History</span>
        <span className="text-[10px] bg-slate-950 text-slate-400 border border-slate-800/80 px-2 py-0.5 rounded-full font-mono font-medium">
          Last 5 records
        </span>
      </h2>

      {history.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center p-6 border border-dashed border-slate-800/60 rounded-xl bg-slate-950/20">
          <FileText className="w-8 h-8 text-slate-600 mb-2" />
          <p className="text-sm font-medium text-slate-400">No summaries yet</p>
          <p className="text-xs text-slate-500 max-w-50 mt-1">
            Upload a PDF document to begin the Map-Reduce pipeline.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3 overflow-y-auto max-h-100 pr-1">
          {history.map((doc) => {
            const isSelected = doc.id === selectedDocId;
            const isProcessing = doc.status === "processing";
            const isFailed = doc.status === "failed";
            const isCompleted = doc.status === "completed";

            return (
              <button
                key={doc.id}
                onClick={() => !isProcessing && onSelect(doc.id)}
                disabled={isProcessing}
                className={`w-full text-left p-3.5 rounded-xl border transition-all duration-200 flex items-start gap-3 relative overflow-hidden group ${
                  isProcessing
                    ? "border-slate-800 bg-slate-950/20 cursor-wait"
                    : isSelected
                      ? "border-indigo-500/80 bg-indigo-500/5 shadow-md shadow-indigo-500/5"
                      : "border-slate-800 hover:border-slate-700 bg-slate-950/40 hover:bg-slate-950/60"
                }`}
              >
                <div className="mt-0.5">
                  {isProcessing && (
                    <Loader2 className="w-4 h-4 animate-spin text-amber-500" />
                  )}
                  {isFailed && <AlertCircle className="w-4 h-4 text-red-500" />}
                  {isCompleted && (
                    <CheckCircle2
                      className={`w-4 h-4 transition-colors ${isSelected ? "text-indigo-400" : "text-slate-400 group-hover:text-indigo-400"}`}
                    />
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <p className="text-xs font-semibold text-slate-200 truncate pr-2">
                      {doc.filename}
                    </p>
                    {isProcessing && (
                      <span className="text-[9px] font-bold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20 uppercase tracking-wider shrink-0">
                        processing
                      </span>
                    )}
                    {isFailed && (
                      <span className="text-[9px] font-bold text-red-400 bg-red-500/10 px-2 py-0.5 rounded border border-red-500/20 uppercase tracking-wider shrink-0">
                        failed
                      </span>
                    )}
                    {isCompleted && (
                      <span className="text-[9px] font-bold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20 uppercase tracking-wider shrink-0">
                        completed
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 text-[10px] text-slate-500 font-medium">
                    <Clock className="w-3 h-3" />
                    <span>{formatDate(doc.created_at)}</span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
