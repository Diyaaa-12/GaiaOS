"""Component to validate and map citations back to actual gathered evidence."""

from __future__ import annotations

import re

from logging_config import get_logger
from orchestrator.schemas.agent_io import AgentOutput, Evidence
from orchestrator.schemas.synthesis import SynthesizedClaim

_log = get_logger(__name__)


class CitationMapper:
    """Enforces citation integrity by verifying cited evidence.

    Checks citations against the gathered evidence pool.
    """

    def __init__(self, gathered_outputs: list[AgentOutput]):
        self.evidence_pool: list[Evidence] = []
        for output in gathered_outputs:
            if output.evidence:
                self.evidence_pool.extend(output.evidence)

    def validate_claim(self, claim: SynthesizedClaim) -> bool:
        """Validate that all supporting evidence in the claim exists in the gathered evidence pool.

        Modifies supporting_evidence in-place with verified evidence from the pool to preserve
        all original metadata. Returns False if any cited evidence is fabricated.
        """
        if not claim.supporting_evidence:
            # If a claim has no citations, it is not evidence-backed.
            # Depending on policy, we might allow it or reject it.
            # The roadmap says: "every synthesized claim references real gathered evidence".
            # Therefore, we reject claims that have no citations.
            _log.warning(
                "synthesis.citation_mapper.no_citations",
                claim_text=claim.text,
            )
            return False

        verified_evidence: list[Evidence] = []
        for cited in claim.supporting_evidence:
            match = self._find_matching_evidence(cited)
            if not match:
                _log.error(
                    "synthesis.citation_mapper.fabrication_detected",
                    claim_text=claim.text,
                    fabricated_claim=cited.claim,
                    fabricated_source=cited.source,
                )
                return False
            verified_evidence.append(match)

        claim.supporting_evidence = verified_evidence
        return True

    def _find_matching_evidence(self, cited: Evidence) -> Evidence | None:
        """Match cited evidence against actual evidence pool using normalized text."""
        cited_claim_norm = self._normalize_text(cited.claim)
        cited_source_norm = self._normalize_text(cited.source)

        for actual in self.evidence_pool:
            if (
                self._normalize_text(actual.claim) == cited_claim_norm
                and self._normalize_text(actual.source) == cited_source_norm
            ):
                return actual
        return None

    def _normalize_text(self, text: str) -> str:
        """Normalize string by removing whitespace and converting to lowercase."""
        if not text:
            return ""
        return re.sub(r"\s+", "", text).lower()
