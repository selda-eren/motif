// Mirrors backend/motif/schema.py and graph.snapshot(). Read-only view of the stored representation.

export type RelationType = "SUPPORTS" | "CONTRADICTS" | "REFINES" | "CAUSES" | "REFRAMES" | "RELATES_TO" | "CHANGES_STATE";
export type Layer = "observation" | "interpretation";

export interface Evidence { passage: number; quote: string; start: number; end: number }

export interface Unit {
  id: string;
  kind: "concept" | "claim" | "event" | "situation" | "entity" | "image";
  label: string;
  content: string;
  participants: string[];
  layer: Layer;
  confidence: number;
  status: "active" | "contested";
  reading: string | null;
  introduced_at: number;
  last_active_at: number;
  evidence: Evidence[];
}

export interface Relation {
  id: string;
  source: string;
  target: string;
  type: RelationType;
  rationale: string;
  confidence: number;
  created_at: number;
  layer: Layer;
  rationale_raw?: string; // as stored; `rationale` has internal ids replaced by labels
}

export interface Revision {
  unit_id: string;
  passage: number;
  old_reading: string | null;
  new_reading: string;
  rationale: string;
  cause_unit: string | null;
  kind?: "state" | "interpretive"; // absent in older data: interpretive
  source?: "integration" | "propagation";
}

export interface PassageChange {
  passage: number;
  gist: string | null;
  processed: boolean;
  introduced: string[];
  reinforced: string[];
  relations: string[];
  cross_passage_relations: string[];
  revisions: Revision[];
  change_score: number;
}

export interface Book {
  id: string;
  title: string;
  author: string;
  genre: string;
  meta: Record<string, string>;
  provenance: string; // "model" | "demo-fixture"
  model: string | null;
}

export interface Passage { idx: number; text: string; gist: string | null; processed: number | boolean }

/** A chapter of the source book (only for books whose text file supplies a chapter map). Not a passage. */
export interface ChapterRef { number: number; numeral: string; title: string; start: number; end: number }
export interface ChapterMap { chapters: ChapterRef[]; passages: { idx: number; start: number; chapters: ChapterRef[] }[] }

export interface Snapshot {
  book: Book;
  passages: Passage[];
  units: Unit[];
  relations: Relation[];
  revisions: Revision[];
  changes: PassageChange[];
  constructions?: Construction[];
}

/** A higher-level meaning MOTIF built from several units; the units themselves are unchanged. */
export interface Construction {
  id: string;
  statement: string; // generated interpretation
  passage: number;
  contributors: { unit_id: string; role: string; added_at?: number | null }[];
  relationship: string;
  basis: "explicit" | "inferred";
  relation_to_existing: "new" | "supplements" | "challenges" | "extends";
  related_to: string | null;
  justification: string;
  limitations: string;
  model_confidence: number;
  evidence: { unit_id: string; passage: number; quote: string }[];
  triggers: string[];
  status?: "established" | "pending"; // absent in older data: established
  explicit_quote?: { unit_id: string; passage: number; quote: string } | null;
  reinforcements?: { passage: number; new_units: string[]; statement: string; via: string }[];
  strength?: { distinct_units: number; distinct_passages: number; reinforcements: number };
}

export interface QuoteInContext { passage: number; quote: string; before: string; after: string; start?: number }

export interface RelationDetail {
  earlier: string;
  later: string;
  relation: Relation;
  source: Unit;
  target: Unit;
  source_evidence: QuoteInContext[];
  target_evidence: QuoteInContext[];
}

export type Selection =
  | { kind: "relation"; id: string }
  | { kind: "unit"; id: string }
  | { kind: "passage"; idx: number }
  | null;

export interface JourneyStage {
  index: number;
  title: string; // generated interpretation
  summary: string; // generated interpretation
  first_passage: number;
  last_passage: number;
  key_units: string[]; // units whose quotations evidence the stage
  leads_to_next: string; // generated interpretation
  bridge_relations: string[];
  key_meanings?: string[]; // constructed meanings that explain the stage
}

export type TransitionKind = "development" | "reinterpretation" | "contradiction" | "consequence" | "analogy" | "succession" | "unclassified";

export interface GroundedQuote { unit_id: string; label: string; passage: number; quote: string; start: number; end: number }

export interface StageExplanation {
  index: number;
  what_changes: string; // generated
  why_it_matters: string; // generated
  quotes: (GroundedQuote & { how_it_supports: string })[];
}

export interface TransitionEvidence {
  kind: "relation" | "revision" | "construction";
  type: string; // MORe relation type, or REVISION
  relation_id?: string;
  unit_id?: string;
  rationale: string;
  new_reading?: string;
  statement?: string;
  construction_id?: string;
  earlier: GroundedQuote;
  later: GroundedQuote;
  adjacent: boolean;
  how_it_supports: string; // generated
}

export interface TransitionExplanation {
  from_index: number;
  to_index: number;
  kind: TransitionKind;
  certainty: "supported" | "tentative";
  what_changes: string;
  why: string;
  evidence: TransitionEvidence[];
  limitation: string;
  grounding_note: string; // set by MOTIF's validation, not the model
  beyond_evidence?: string; // generated: what the explanation adds beyond the cited evidence
}

export interface JourneyExplanation {
  stages: StageExplanation[];
  transitions: TransitionExplanation[];
  warnings: string[];
  provenance: string;
  model: string | null;
}

export interface Journey {
  overview: string;
  explanation?: JourneyExplanation;
  stages: JourneyStage[];
  warnings: string[];
  provenance: string;
  model: string | null;
  generated_at: number;
}

export type View = "journey" | "weave";
