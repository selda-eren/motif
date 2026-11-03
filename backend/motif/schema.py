"""MORe (Meaning-Oriented Representation): data types.

Two families of types live here:
  * LLM I/O contracts (Perception*, Integration*), sent as JSON Schema to the model and
    used to validate what comes back.
  * The persisted representation (Unit, Relation, Evidence, Revision), which our own code
    produces after grounding and validating the model's proposals.

Provisional research decisions, deliberately simple:
  * A Unit is the elementary representation: one concept, claim, event, situation,
    entity or image (recurring figure/motif), anchored to at least one verbatim quote.
  * `layer` separates what the text states ("observation") from what the system infers
    ("interpretation"). Relations are always interpretations.
  * A Unit's `content` is fixed once grounded; its `reading` (current significance) is the
    revisable part, and every change to it is logged as a Revision.
  * A change over time is not a contradiction. A Revision is either a `state` update (what is
    now the case: something lost, sold, ended) or an `interpretive` one (what it signifies). State
    updates go to `state` and leave the reading alone; an interpretive reading may replace the
    current one or coexist with it (`other_readings`).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, computed_field

UnitKind = Literal["concept", "claim", "event", "situation", "entity", "image"]
RelationType = Literal["SUPPORTS", "CONTRADICTS", "REFINES", "CAUSES", "REFRAMES", "RELATES_TO", "CHANGES_STATE"]
Layer = Literal["observation", "interpretation"]
RevisionKind = Literal["state", "interpretive"]

RELATION_DEFINITIONS: dict[str, str] = {
    # Read every relation as "A <TYPE> B".
    "SUPPORTS": "A gives evidence, an example or a reason for B",
    "CONTRADICTS": "A conflicts with, denies, opposes or undermines B as an account or claim. A later "
                   "change of circumstances is not a contradiction: use CHANGES_STATE",
    "REFINES": "A makes B more precise, qualified or developed",
    "CAUSES": "A brings about B",
    "CHANGES_STATE": "A is a later event that changes the situation B describes (something is lost, sold, "
                     "ended or transformed); B stays true of its own time",
    "REFRAMES": "A changes what B means or stands for (e.g. a literal image is revealed as a figure "
                "for something else)",
    "RELATES_TO": "a meaningful but weaker thematic link; use sparingly",
}


# ---------- LLM contract: perception (one passage, local) ----------

class PerceivedUnit(BaseModel):
    kind: UnitKind
    label: str = Field(description="2-6 word name for the unit")
    content: str = Field(description="One sentence stating the unit as the passage presents it")
    participants: list[str] = Field(description="Agents or entities involved; may be empty")
    quote: str = Field(description="Exact, verbatim span copied from the passage (5-40 words) that grounds this unit")
    basis: Literal["explicit", "inferred"] = Field(
        description="explicit: directly stated in the quote; inferred: your interpretation anchored by the quote")
    confidence: float = Field(description="0.0-1.0")


class PerceptionResult(BaseModel):
    gist: str = Field(description="One sentence: what this passage does in the argument or story")
    units: list[PerceivedUnit]


# ---------- LLM contract: integration (new units vs. activated memory) ----------

class ProposedRelation(BaseModel):
    target: str = Field(description="id of an existing unit (e.g. u00_1) or another new unit (e.g. n2)")
    type: RelationType
    direction: Literal["new_to_target", "target_to_new"] = Field(
        description="new_to_target: NEW unit <TYPE> target. target_to_new: target <TYPE> NEW unit "
                    "(e.g. when an earlier unit CAUSES the new one)")
    rationale: str = Field(description="Why they relate, referring to what each text says")
    confidence: float = Field(description="0.0-1.0")


class ProposedRevision(BaseModel):
    target: str = Field(description="id of an existing unit whose significance changes")
    # Defaults keep older fixtures valid; the schema sent to the model requires both (see require_all).
    kind: RevisionKind = Field(
        "interpretive", description="state: only the facts of the earlier unit changed over time (what is "
                                    "now the case); interpretive: what it means or signifies has changed")
    new_reading: str = Field(description="state: what is now the case. interpretive: how the earlier "
                                         "unit should now be understood")
    coexists: bool = Field(
        False, description="interpretive only: true if this reading adds to the current reading instead "
                           "of replacing it (e.g. practical significance changes, symbolic remains)")
    rationale: str


class IntegrationDecision(BaseModel):
    new_unit: str = Field(description="temporary id of the new unit, e.g. n1")
    action: Literal["add", "merge"] = Field(
        description="merge only if the new unit restates an existing unit; otherwise add")
    merge_into: str = Field(description="existing unit id when action is merge, else empty string")
    relations: list[ProposedRelation]
    revisions: list[ProposedRevision]


class IntegrationResult(BaseModel):
    decisions: list[IntegrationDecision]


# ---------- LLM contract: propagation (reconsider units linked to a changed unit) ----------

class Reconsideration(BaseModel):
    candidate: str = Field(description="id of the candidate unit")
    verdict: Literal["unchanged", "state_update", "reinterpretation"]
    new_reading: str = Field(description="new state or new reading in one sentence; empty if unchanged")
    coexists: bool = Field(description="reinterpretation only: true if it adds to the current reading "
                                       "instead of replacing it; false otherwise")
    evidence: list[str] = Field(description="ids of listed units whose quotations support the new reading; "
                                            "empty if unchanged")
    rationale: str


class PropagationResult(BaseModel):
    reconsiderations: list[Reconsideration]


# ---------- LLM contract: construction (higher-level meaning from several units) ----------

class ProposedRole(BaseModel):
    unit: str = Field(description="id of a listed unit")
    role: str = Field(description="what this unit contributes to the meaning")


class ProposedMeaning(BaseModel):
    statement: str = Field(description="the emerging meaning, in one sentence")
    contributors: list[ProposedRole] = Field(description="at least two listed units, each one necessary")
    relationship: str = Field(description="how the contributors relate (e.g. parallel, contrast, cause and consequence)")
    basis: Literal["explicit", "inferred", "speculative"] = Field(
        description="explicit: the meaning itself is substantially stated in the text (not merely its facts); "
                    "inferred: constructed by combining the textual evidence; speculative: needs assumptions "
                    "the evidence does not sufficiently support")
    # Default keeps saved Milestone 5 outputs replayable; the schema sent to the model requires it.
    stated_quote: str = Field("", description="explicit only: the exact words from the text that state the central "
                                          "meaning itself, copied verbatim; empty string otherwise")
    kind: Literal["emergent_meaning", "state_consequence"]
    relation_to_existing: Literal["new", "supplements", "challenges", "extends", "reinforces"]
    related_to: str = Field(description="id of the unit whose reading, or of the constructed meaning, it "
                                        "supplements, challenges, extends or reinforces; empty string if new")
    justification: str = Field(description="how the contributors jointly support the meaning")
    assumptions: str = Field(description="anything the meaning needs that no listed unit states or clearly "
                                         "implies; empty string if none")
    limitations: str
    confidence: float


class ConstructionResult(BaseModel):
    meanings: list[ProposedMeaning]
    no_new_meaning: str = Field(description="why no (further) meaning is supported; may be empty")


def require_all(schema: dict) -> dict:
    """Mark every property required, including those with defaults, in a JSON schema for the model."""
    for node in [schema, *schema.get("$defs", {}).values()]:
        if "properties" in node:
            node["required"] = list(node["properties"])
    return schema


# ---------- Persisted representation ----------

class Evidence(BaseModel):
    passage: int
    quote: str
    start: int  # offsets within the passage text
    end: int


class Unit(BaseModel):
    id: str
    kind: UnitKind
    label: str
    content: str
    participants: list[str]
    layer: Layer
    confidence: float
    status: Literal["active", "contested"] = "active"
    reading: str | None = None
    state: str | None = None  # what is now the case, if a later passage changed it
    other_readings: list[str] = []  # interpretive readings that coexist with `reading`
    introduced_at: int
    last_active_at: int
    evidence: list[Evidence] = []


class Relation(BaseModel):
    id: str
    source: str
    target: str
    type: RelationType
    rationale: str
    confidence: float
    created_at: int  # passage index where the link was formed
    layer: Layer = "interpretation"


class Contributor(BaseModel):
    unit_id: str
    role: str
    added_at: int | None = None  # passage where a later reinforcement added it; None for original contributors


class Reinforcement(BaseModel):
    """The same meaning met again with distinct new evidence."""
    passage: int
    new_units: list[str]
    statement: str  # the wording at that point, kept so that its perspective is not lost
    via: Literal["model", "similarity"]  # declared by the model, or found by the duplicate check


class ConstructionEvidence(BaseModel):
    unit_id: str
    passage: int
    quote: str


class Construction(BaseModel):
    """A higher-level meaning built from two or more units, which it references but never changes."""
    id: str
    statement: str
    passage: int  # where the meaning first became possible
    contributors: list[Contributor]
    relationship: str
    basis: Literal["explicit", "inferred"]
    relation_to_existing: Literal["new", "supplements", "challenges", "extends", "overlaps"]
    related_to: str | None  # unit id (its reading) or construction id
    justification: str
    limitations: str
    model_confidence: float  # the model's own estimate; not evidence of correctness
    evidence: list[ConstructionEvidence]  # contributors' quotations from passages read by then
    triggers: list[str]  # the rules that caused construction to run at this passage
    reinforcements: list[Reinforcement] = []
    repeated_at: list[int] = []  # passages where it was proposed again with no new evidence (adds no strength)
    # "pending": kept for review because its classification was ambiguous; never presented as established.
    status: Literal["established", "pending"] = "established"
    pending_reason: str | None = None
    resolved_at: int | None = None  # passage where a pending meaning was confirmed by a later proposal
    explicit_quote: ConstructionEvidence | None = None  # the verified words that state it, when basis is explicit

    @computed_field
    @property
    def strength(self) -> dict:
        """Memory strength as distinct support only: not model confidence, not repetitions."""
        return {"distinct_units": len({c.unit_id for c in self.contributors}),
                "distinct_passages": len({e.passage for e in self.evidence}),
                "reinforcements": len(self.reinforcements)}


class Revision(BaseModel):
    unit_id: str
    passage: int
    old_reading: str | None
    new_reading: str
    rationale: str
    cause_unit: str | None
    kind: RevisionKind = "interpretive"
    mode: Literal["replaces", "coexists"] = "replaces"
    source: Literal["integration", "propagation"] = "integration"
    trigger_unit: str | None = None  # propagation: the changed unit that prompted reconsideration
    evidence_units: list[str] = []  # units whose (verbatim-grounded) quotations support it
