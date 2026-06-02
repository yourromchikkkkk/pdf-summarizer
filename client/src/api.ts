import type { DocumentRecord } from './types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function fetchHistory(userId: string): Promise<DocumentRecord[]> {
  const res = await fetch(`${API_BASE}/api/history`, {
    headers: { 'X-User-ID': userId },
  });
  if (!res.ok) throw new Error('Failed to fetch history');
  return res.json();
}

export async function uploadDocument(file: File, userId: string): Promise<DocumentRecord> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/api/upload`, {
    method: 'POST',
    headers: { 'X-User-ID': userId },
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Upload failed');
  }
  return res.json();
}
