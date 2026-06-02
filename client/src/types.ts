export interface DocumentRecord {
  id: string;
  filename: string;
  status: 'processing' | 'completed' | 'failed';
  summary: string | null;
  created_at: string;
}
