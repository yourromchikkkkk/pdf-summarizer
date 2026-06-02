import { Sparkles, RefreshCw } from 'lucide-react';

interface Props {
  userId: string;
  onRefresh: () => void;
}

export function Header({ userId, onRefresh }: Props) {
  return (
    <header className="border-b border-slate-900 bg-slate-950/80 backdrop-blur-md sticky top-0 z-40 px-6 py-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="p-2.5 bg-linear-to-tr from-indigo-600 to-purple-600 rounded-xl shadow-lg shadow-indigo-500/10">
          <Sparkles className="w-5 h-5 text-indigo-100" />
        </div>
        <div>
          <h1 className="text-xl font-bold bg-linear-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
            Docling PDF Summarizer
          </h1>
          <p className="text-xs text-slate-500 font-medium">Map-Reduce Synthesis Engine</p>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <button
          onClick={onRefresh}
          className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-900 rounded-lg transition-colors border border-slate-900"
          title="Refresh History"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
        <div className="text-right text-xs">
          <span className="text-slate-500 block">User Tracking Session</span>
          <span className="text-slate-400 font-mono text-[10px] select-all bg-slate-900/60 px-2 py-0.5 rounded border border-slate-900">
            {userId || 'Loading...'}
          </span>
        </div>
      </div>
    </header>
  );
}
