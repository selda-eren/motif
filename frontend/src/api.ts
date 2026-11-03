import type { Book, ChapterMap, Journey, RelationDetail, Snapshot } from "./types";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText} for ${path}: ${body.slice(0, 200)}`);
  }
  return (await res.json()) as T;
}

/** Like get(), but a 404 (nothing synthesized yet) resolves to null. */
async function getOptional<T>(path: string): Promise<T | null> {
  const res = await fetch(path);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${path}`);
  return (await res.json()) as T;
}

export const api = {
  journey: (bookId: string) => getOptional<Journey>(`/api/books/${encodeURIComponent(bookId)}/journey`),
  chapters: (bookId: string) => getOptional<ChapterMap>(`/api/books/${encodeURIComponent(bookId)}/chapters`),
  books: () => get<Book[]>("/api/books"),
  snapshot: (bookId: string) => get<Snapshot>(`/api/books/${encodeURIComponent(bookId)}`),
  connections: (bookId: string, top = 5) =>
    get<(RelationDetail & { score: number })[]>(`/api/books/${encodeURIComponent(bookId)}/connections?top=${top}`),
  relation: (bookId: string, relId: string) =>
    get<RelationDetail>(`/api/books/${encodeURIComponent(bookId)}/relations/${encodeURIComponent(relId)}`),
};
