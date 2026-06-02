import { useState } from 'react';
import { FileText, Loader2, AlertCircle, Copy, Check, Download } from 'lucide-react';
import { toast } from 'sonner';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { DocumentRecord } from '../types';

interface Props {
  document: DocumentRecord | null;
}

export function SummaryPanel({ document: doc }: Props) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    if (!doc?.summary) return;
    navigator.clipboard.writeText(doc.summary);
    setCopied(true);
    toast.success('Summary copied to clipboard!');
    setTimeout(() => setCopied(false), 2000);
  }

  function handleDownload() {
    if (!doc?.summary) return;
    const blob = new Blob([doc.summary], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement('a'), {
      href: url,
      download: `${doc.filename.replace('.pdf', '')}_summary.md`,
    });
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success('Markdown summary exported successfully!');
  }

  return (
    <div className="lg:col-span-7 bg-slate-900/50 backdrop-blur-sm border border-slate-800/80 rounded-2xl p-6 shadow-xl flex flex-col min-h-[500px]">
      {doc ? (
        <div className="flex-1 flex flex-col h-full">
          <div className="flex items-start justify-between border-b border-slate-800 pb-4 mb-4">
            <div className="min-w-0 pr-4">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-[10px] font-bold bg-indigo-500/15 text-indigo-400 px-2.5 py-0.5 rounded-full border border-indigo-500/20 tracking-wide uppercase">
                  Analysis Report
                </span>
                <span className="text-[10px] text-slate-500 font-mono">ID: {doc.id.substring(0, 8)}...</span>
              </div>
              <h2 className="text-base font-bold text-slate-100 truncate">{doc.filename}</h2>
            </div>

            {doc.status === 'completed' && doc.summary && (
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={handleCopy}
                  className="p-2 text-slate-400 hover:text-slate-200 bg-slate-950/60 hover:bg-slate-950 rounded-lg border border-slate-800 transition-colors flex items-center gap-1.5 text-xs font-semibold"
                  title="Copy to Clipboard"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>Copy</span>
                </button>
                <button
                  onClick={handleDownload}
                  className="p-2 text-slate-400 hover:text-slate-200 bg-slate-950/60 hover:bg-slate-950 rounded-lg border border-slate-800 transition-colors flex items-center gap-1.5 text-xs font-semibold"
                  title="Export Markdown"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Export</span>
                </button>
              </div>
            )}
          </div>

          <div className="flex-1 overflow-y-auto max-h-[600px] pr-2">
            {doc.status === 'processing' && (
              <div className="h-full flex flex-col items-center justify-center text-center p-8">
                <div className="p-4 rounded-full bg-slate-900 border border-slate-800 mb-4 animate-bounce">
                  <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
                </div>
                <h3 className="text-sm font-semibold text-slate-200 mb-1">
                  Summarization Pipeline in Progress
                </h3>
                <p className="text-xs text-slate-400 max-w-[320px] leading-relaxed">
                  Docling is converting the document layout, and OpenAI is executing the Map-Reduce pipeline. This can take 10-60s depending on document size.
                </p>
              </div>
            )}

            {doc.status === 'failed' && (
              <div className="h-full flex flex-col items-center justify-center text-center p-8 bg-red-500/5 rounded-xl border border-red-500/10">
                <div className="p-4 rounded-full bg-slate-900 border border-slate-800 mb-4 text-red-400">
                  <AlertCircle className="w-8 h-8" />
                </div>
                <h3 className="text-sm font-semibold text-red-200 mb-2">Pipeline Execution Failed</h3>
                <div className="text-left bg-slate-950 p-4 rounded-lg border border-slate-900 max-w-md w-full">
                  <p className="text-[11px] font-mono text-red-400/90 whitespace-pre-wrap leading-relaxed">
                    {doc.summary || 'An unknown error occurred during parsing.'}
                  </p>
                </div>
                <p className="text-xs text-slate-500 mt-4 max-w-[320px]">
                  Please make sure your API keys are correct, and the document is a readable, uncorrupted PDF.
                </p>
              </div>
            )}

            {doc.status === 'completed' && doc.summary && (
              <article className="markdown-body p-2 select-text selection:bg-indigo-600/40">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{doc.summary}</ReactMarkdown>
              </article>
            )}
          </div>
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-indigo-500/10 to-purple-500/10 border border-slate-800 flex items-center justify-center mb-4 shadow-inner">
            <FileText className="w-6 h-6 text-indigo-400" />
          </div>
          <h3 className="text-sm font-semibold text-slate-200 mb-1">No Document Selected</h3>
          <p className="text-xs text-slate-500 max-w-[280px] leading-relaxed">
            Select a completed summarization from your history panel or upload a new PDF to view the executive analysis here.
          </p>
        </div>
      )}
    </div>
  );
}
