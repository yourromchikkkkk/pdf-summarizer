export interface DocumentRecord {
  id: string;
  filename: string;
  status: 'processing' | 'completed' | 'failed';
  summary: string | null;
  created_at: string;
}

export interface ProgressEvent {
  stage: 'parsing' | 'chunking' | 'summarizing' | 'reducing' | 'completed' | 'failed';
  total_chunks?: number;
  chunk?: number;
  error?: string;
}
