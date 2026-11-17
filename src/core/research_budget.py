"""Small, explicit research budgets; source counts never buy confidence."""

MAX_SEARCH_CALLS = 4
MAX_DOCUMENTS = 8
MAX_DOCUMENT_CHARS = 20000
MAX_MODEL_CALLS = 8  # extraction, four searches, qualification, audit, one scope repair
RETRIEVAL_TOKEN_LIMIT = 45000
# Four in-flight searches for multiple claims can return ~54k tokens before
# their use is observed. Preserve completion capacity for qualification/audit;
# this allowance never creates another search call or round.
ANALYSIS_TOKEN_LIMIT = 80000
ANALYSIS_SECONDS = 180
INTENTS = ('support', 'contradiction', 'neutral', 'primary')


def rounds_for(extraction):
    # Kept for callers inspecting the policy. Risk and scarcity change how the
    # available material is assessed, never trigger another paid search round.
    return 1


def plan_searches(extraction):
    """Keep all objectives auditable, prioritizing the actual verification target.

    Only the first MAX_SEARCH_CALLS entries may execute. Remaining entries are
    recorded as skipped rather than claiming that their retrieval was completed.
    """
    ordered = sorted(enumerate(extraction.claims), key=lambda pair: (
        not pair[1].verification_target, not pair[1].critical,
        -pair[1].materiality, pair[0]))
    # Two real calls cover four explicit objectives. Round-robin still gives
    # every material claim a first pass before a second call on the same claim.
    objective_pairs = (('primary', 'neutral'), ('contradiction', 'support'))
    return [(claim, objectives[0], ' | '.join(dict.fromkeys(
                claim.queries[INTENTS.index(intent)] for intent in objectives)), objectives)
            for objectives in objective_pairs for _, claim in ordered if claim.verifiable]
