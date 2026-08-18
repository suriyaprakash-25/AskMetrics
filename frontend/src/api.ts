export type AskStatus = 'success' | 'refusal' | 'error';

export type ResultRow = Record<string, unknown>;

export interface AskResponse {
  status: AskStatus;
  question: string;
  sql: string | null;
  answer: ResultRow[] | null;
  rows: ResultRow[];
  row_count: number;
  explanation: string;
  error?: string;
  attempts: number;
}

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '');

export const askQuestion = async (question: string): Promise<AskResponse> => {
  const response = await fetch(`${API_BASE_URL}/ask`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ question }),
  });

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new Error(`Backend returned an invalid response (${response.status}).`);
  }

  if (!response.ok) {
    const detail =
      typeof payload === 'object' && payload !== null && 'detail' in payload
        ? String((payload as { detail: unknown }).detail)
        : response.statusText;
    throw new Error(`API error (${response.status}): ${detail}`);
  }

  return payload as AskResponse;
};
