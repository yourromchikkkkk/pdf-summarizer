import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Toaster, toast } from "sonner";
import { fetchHistory, uploadDocument, openProgressStream } from "./api";
import type { ProgressEvent } from "./types";
import { ProcessingBanner } from "./components/ProcessingBanner";
import { Header } from "./components/Header";
import { UploadCard } from "./components/UploadCard";
import { HistoryPanel } from "./components/HistoryPanel";
import { SummaryPanel } from "./components/SummaryPanel";

function stageLabel(event: ProgressEvent): string {
  switch (event.stage) {
    case "parsing": return "Parsing PDF...";
    case "chunking": return `Split into ${event.total_chunks} chunks. Summarizing...`;
    case "summarizing": return `Summarizing chunk ${event.chunk}/${event.total_chunks}...`;
    case "reducing": return "Generating final summary...";
    default: return "Processing...";
  }
}

export default function App() {
  const [userId] = useState<string>(() => {
    try {
      let id = localStorage.getItem("pdf_summary_user_id");

      if (!id) {
        id =
          crypto.randomUUID?.() ??
          `user_${Math.random().toString(36).slice(2)}_${Date.now()}`;

        localStorage.setItem("pdf_summary_user_id", id);
      }

      return id;
    } catch {
      return (
        crypto.randomUUID?.() ??
        `user_${Math.random().toString(36).slice(2)}_${Date.now()}`
      );
    }
  });
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [streamDocId, setStreamDocId] = useState<string | null>(null);
  const [processingStage, setProcessingStage] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!streamDocId) return;
    const es = openProgressStream(streamDocId);
    esRef.current = es;

    es.onmessage = (e: MessageEvent) => {
      const event: ProgressEvent = JSON.parse(e.data);
      setProcessingStage(stageLabel(event));
      if (event.stage === "completed" || event.stage === "failed") {
        queryClient.invalidateQueries({ queryKey: ["history", userId] });
        es.close();
        setStreamDocId(null);
        setProcessingStage(null);
      }
    };

    es.onerror = () => {
      es.close();
      setStreamDocId(null);
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [streamDocId, userId, queryClient]);

  const { data: history = [] } = useQuery({
    queryKey: ["history", userId],
    queryFn: () => fetchHistory(userId),
    enabled: !!userId,
    refetchInterval: (query) =>
      query.state.data?.some((doc) => doc.status === "processing")
        ? 30000
        : false,
    refetchIntervalInBackground: false,
  });

  const isProcessingActive =
    !!streamDocId || history.some((doc) => doc.status === "processing");

  const upload = useMutation({
    mutationFn: (file: File) => uploadDocument(file, userId),
    onSuccess: (doc) => {
      queryClient.invalidateQueries({ queryKey: ["history", userId] });
      setSelectedDocId(doc.id);
      setStreamDocId(doc.id);
    },
  });

  async function handleUpload(file: File) {
    if (isProcessingActive) {
      toast.warning("A document is currently processing. Please wait.");
      return;
    }
    await toast.promise(upload.mutateAsync(file), {
      loading: "Uploading document and initiating pipeline...",
      success: "Document accepted! Processing initiated...",
      error: (err: Error) => `Upload failed: ${err.message || "Network error"}`,
    });
  }

  const selectedDoc = history.find((doc) => doc.id === selectedDocId) ?? null;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-indigo-500 selection:text-white">
      <Toaster position="bottom-right" theme="dark" closeButton />

      <ProcessingBanner visible={isProcessingActive} stage={processingStage} />

      <Header
        userId={userId}
        onRefresh={() =>
          queryClient.invalidateQueries({ queryKey: ["history", userId] })
        }
      />

      <main className="flex-1 max-w-7xl w-full mx-auto p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[calc(100vh-80px)]">
        <div className="lg:col-span-5 flex flex-col gap-6">
          <UploadCard
            onUpload={handleUpload}
            isProcessingActive={isProcessingActive}
            isUploading={upload.isPending}
          />
          <HistoryPanel
            history={history}
            selectedDocId={selectedDocId}
            onSelect={setSelectedDocId}
          />
        </div>

        <SummaryPanel document={selectedDoc} />
      </main>

      <footer className="border-t border-slate-900 bg-slate-950/60 py-4 text-center text-xs text-slate-600 font-mono mt-6">
        <span>Docling Version 2.0+ &bull; OpenAI GPT-4o-Mini</span>
      </footer>
    </div>
  );
}