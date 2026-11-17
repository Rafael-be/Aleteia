"""Strict semantic contracts. A model supplies annotations, never public scores."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


_SCALES: dict[str, tuple[float, ...]] = {
    'stance': (-1.0, -0.5, 0.0, 0.5, 1.0),
    'source_quality': (0.0, 0.25, 0.5, 0.75, 1.0),
    'relevance': (0.0, 0.5, 1.0),
    'context_fit': (0.0, 0.5, 1.0),
}

# Literal does not support floats in Python's type system. Keep numeric types
# for static checking, enums for structured output, and runtime validation below.
StanceValue = Annotated[float, Field(json_schema_extra={'enum': list(_SCALES['stance'])})]
SourceQualityValue = Annotated[float, Field(json_schema_extra={'enum': list(_SCALES['source_quality'])})]
ContextValue = Annotated[float, Field(json_schema_extra={'enum': list(_SCALES['context_fit'])})]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class Claim(StrictModel):
    id: str = Field(min_length=1, max_length=32)
    text: str = Field(min_length=1, max_length=1500)
    original_span: str = Field(min_length=1, max_length=1500)
    context: str = Field(max_length=1000)
    materiality: float = Field(gt=0, le=1)
    critical: bool
    verifiable: bool
    high_risk: bool
    elements: list[str] = Field(min_length=1, max_length=8)
    queries: list[str] = Field(min_length=4, max_length=4)
    investigative: bool = False
    verification_target: bool = False
    relation_type: Literal['categorical', 'attribution', 'statistical', 'causal'] = 'categorical'
    personal_advice: bool = False


class Extraction(StrictModel):
    kind: Literal['FACTUAL', 'NEEDS_CONTEXT', 'NOT_VERIFIABLE', 'OUT_OF_SCOPE']
    claims: list[Claim] = Field(max_length=4)
    omitted_material: bool
    decomposition_complete: bool
    risk_requires_review: bool = False
    research_depth: Literal['standard', 'debated', 'obscure'] = 'standard'
    personal_advice: bool = False


class EvidenceAnnotation(StrictModel):
    claim_id: str = Field(max_length=32)
    source_id: str = Field(max_length=32)
    quote: str = Field(min_length=20, max_length=800)
    stance: StanceValue
    decision_scope: Literal['applicable', 'indirect', 'different_context', 'mere_mention', 'unclear'] = 'applicable'
    contribution: Literal['decision', 'explanation', 'incidental'] = 'decision'
    source_quality: SourceQualityValue | None
    relevance: ContextValue | None
    context_fit: ContextValue | None
    covered_elements: list[int] = Field(max_length=8)
    refutes_elements: list[int] = Field(default_factory=list, max_length=8)
    refutation_kind: Literal['none', 'explicit_contradiction'] = 'none'
    primary: bool
    origin_source_id: str | None
    origin_quote: str | None = Field(max_length=1200)
    rationale: str = Field(min_length=1, max_length=300)

    @field_validator('stance', 'source_quality', 'relevance', 'context_fit', mode='before')
    @classmethod
    def reject_boolean_scores(cls, value):
        if isinstance(value, bool):
            raise ValueError('Boolean is not a measured attribute')
        return value

    @field_validator('stance', 'source_quality', 'relevance', 'context_fit')
    @classmethod
    def enforce_numeric_scale(cls, value: float | None, info: ValidationInfo) -> float | None:
        if value is not None and value not in _SCALES[info.field_name or '']:
            raise ValueError('Attribute is outside its measured scale')
        return value


class ClaimReview(StrictModel):
    claim_id: str = Field(max_length=32)
    context_complete: bool
    decomposition_faithful: bool
    causal_overreach: bool
    analysis_overreach: bool = False
    # The reviewed target is distinct from the factual answer/correction. The
    # qualification validator requires this exact binding before using stance.
    evaluated_target: str = Field(default='', max_length=1500)
    conclusion: Literal['supports', 'refutes', 'mixed', 'insufficient'] = 'insufficient'
    search_finding: Literal['no_support_found', 'unclear_mentions', 'not_assessed'] = 'not_assessed'
    entity_resolved: bool = False
    absence_weakens_claim: bool = False
    assessment: str = Field(default='', max_length=1200)
    resolved_claim: str | None = Field(default=None, max_length=1500)
    resolution_source_ids: list[str] = Field(default_factory=list, max_length=12)


class ResolvedScope(StrictModel):
    id: str = Field(min_length=1, max_length=32)
    parent_claim_id: str = Field(max_length=32)
    text: str = Field(min_length=1, max_length=1500)
    context: str = Field(min_length=1, max_length=500)
    elements: list[str] = Field(min_length=1, max_length=8)
    source_ids: list[str] = Field(min_length=1, max_length=12)
    relation_type: Literal['categorical', 'attribution', 'statistical', 'causal'] = 'categorical'


class Qualification(StrictModel):
    evidence: list[EvidenceAnnotation] = Field(max_length=32)
    reviews: list[ClaimReview] = Field(max_length=8)
    resolved_scopes: list[ResolvedScope] = Field(default_factory=list, max_length=8)


STATES = {
    'NO_SUPPORT_FOUND': 'Sem sustentação nas fontes consultadas',
    'STRONGLY_SUPPORTED': 'Fortemente sustentada',
    'PREDOMINANTLY_SUPPORTED': 'Predominantemente sustentada',
    'STRONGLY_CONTRADICTED': 'Fortemente contraditada',
    'PREDOMINANTLY_CONTRADICTED': 'Predominantemente contraditada',
    'CONTESTED': 'Evidências em conflito',
    'MIXED': 'Parcialmente sustentada; contextos distintos',
    'INCONCLUSIVE': 'Inconclusiva',
    'NOT_VERIFIABLE': 'Não verificável',
    'HUMAN_REVIEW_REQUIRED': 'Requer revisão humana',
}
