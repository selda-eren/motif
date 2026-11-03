import { createContext, useContext } from "react";
import type { ChapterMap, ChapterRef } from "./types";
import { passageNo } from "./vocab";

/** For books with a chapter map: passage index (and, when known, a character offset inside the passage) -> "XII" or "XII–XIII",
 *  the book's own chapter numerals. A passage can straddle two chapters; a quotation lies in exactly one. */
export type ChapterOf = (passageIdx: number, offsetInPassage?: number) => string;
export const ChapterContext = createContext<ChapterOf>(() => "");

const span = (cs: ChapterRef[]) => (cs.length === 1 ? cs[0].numeral : `${cs[0].numeral}–${cs[cs.length - 1].numeral}`);

export function chapterLabeller(map: ChapterMap | null): ChapterOf {
  if (!map) return () => "";
  const byPassage = new Map(map.passages.map((p) => [p.idx, p]));
  return (idx, at) => {
    const p = byPassage.get(idx);
    if (!p || !p.chapters.length) return "";
    if (at !== undefined && p.chapters.length > 1) {
      const abs = p.start + at;
      const c = p.chapters.find((x) => x.start <= abs && abs < x.end);
      if (c) return c.numeral;
    }
    return span(p.chapters);
  };
}

/** "74" or "74 · ch. XIII": the passage number (an internal index) with the book's chapter when known.
 *  Pass `at` (the quotation's offset inside the passage) to name the quotation's own chapter rather than the passage's range. */
export function PassageNo({ i, at }: { i: number; at?: number }) {
  const ch = useContext(ChapterContext)(i, at);
  return <>{passageNo(i)}{ch && <span className="chapter-ref"> · ch. {ch}</span>}</>;
}
