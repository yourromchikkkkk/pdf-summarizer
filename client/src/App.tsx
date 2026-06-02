import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Toaster, toast } from "sonner";
import { fetchHistory, uploadDocument } from "./api";
import { ProcessingBanner } from "./components/ProcessingBanner";
import { Header } from "./components/Header";
import { UploadCard } from "./components/UploadCard";
import { HistoryPanel } from "./components/HistoryPanel";
import { SummaryPanel } from "./components/SummaryPanel";

const POLL_INTERVAL_MS = Number(import.meta.env.VITE_POLL_INTERVAL_MS) || 4000;

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
  const queryClient = useQueryClient();

  const { data: history = [] } = useQuery({
    queryKey: ["history", userId],
    queryFn: () => fetchHistory(userId),
    enabled: !!userId,
    refetchInterval: (query) =>
      query.state.data?.some((doc) => doc.status === "processing")
        ? POLL_INTERVAL_MS
        : false,
    refetchIntervalInBackground: false,
  });

  const isProcessingActive = history.some((doc) => doc.status === "processing");

  const upload = useMutation({
    mutationFn: (file: File) => uploadDocument(file, userId),
    onSuccess: (doc) => {
      queryClient.invalidateQueries({ queryKey: ["history", userId] });
      setSelectedDocId(doc.id);
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

      <ProcessingBanner visible={isProcessingActive} />

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