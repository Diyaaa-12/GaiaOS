"""Component to validate and map citations back to actual gathered evidence."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence

from logging_config import get_logger
from orchestrator.schemas.agent_io import AgentOutput, Evidence
from orchestrator.schemas.synthesis import RawCitedEvidence, SynthesizedClaim

_log = get_logger(__name__)


class CitationMapper:
    """Enforces citation integrity by verifying cited evidence.

    Uses ID-first matching with O(1) lookups and falls back gracefully
    to text-matching when evidence_id is missing or absent.
    """

    def __init__(self, gathered_outputs: list[AgentOutput]):
        self.evidence_pool: list[Evidence] = []
        for output in gathered_outputs:
            if output.evidence:
                self.evidence_pool.extend(output.evidence)

        # O(1) Lookup Indices built once during initialization
        self.id_index: dict[str, Evidence] = {}
        self.text_index: dict[tuple[str, str], list[Evidence]] = defaultdict(list)

        for e in self.evidence_pool:
            if e.id:
                self.id_index[str(e.id)] = e
            key = (self._normalize_text(e.source), self._normalize_text(e.claim))
            self.text_index[key].append(e)

        # Telemetry & Observability Counters
        self.total_citations: int = 0
        self.matched_by_id_count: int = 0
        self.matched_by_text_fallback_count: int = 0
        self.citation_missing_id_count: int = 0
        self.citation_ambiguous_fallback_count: int = 0

    @property
    def citation_fallback_rate(self) -> float:
        """Calculate fraction of citations that required text-matching fallback."""
        if self.total_citations == 0:
            return 0.0
        return self.matched_by_text_fallback_count / self.total_citations

    def map_citations(
        self, citations: Sequence[RawCitedEvidence]
    ) -> list[Evidence] | None:
        """Map raw LLM citations to verified Evidence entities from the pool.

        Returns None if any cited evidence is fabricated or ambiguous.
        """
        if not citations:
            return None

        verified_evidence: list[Evidence] = []
        for cited in citations:
            match = self._find_matching_evidence(cited)
            if not match:
                _log.error(
                    "synthesis.citation_mapper.fabrication_detected",
                    fabricated_claim=cited.claim,
                    fabricated_source=cited.source,
                )
                return None
            verified_evidence.append(match)

        return verified_evidence

    def validate_claim(self, claim: SynthesizedClaim) -> bool:
        """Validate that all supporting evidence in the claim exists in the gathered evidence pool.

        Modifies supporting_evidence in-place with verified evidence from the pool to preserve
        all original metadata. Returns False if any cited evidence is fabricated.
        """
        if not claim.supporting_evidence:
            _log.warning(
                "synthesis.citation_mapper.no_citations",
                claim_text=claim.text,
            )
            return False

        verified = self._verify_evidence_pool_membership(claim.supporting_evidence)
        if verified is None:
            return False

        claim.supporting_evidence = verified
        return True

    def _verify_evidence_pool_membership(
        self, evidence_list: Sequence[Evidence]
    ) -> list[Evidence] | None:
        """Verify already-constructed Evidence objects against the evidence pool."""
        if not evidence_list:
            return None

        verified_evidence: list[Evidence] = []
        for ev in evidence_list:
            match = self._find_matching_evidence_fields(
                evidence_id=ev.id,
                source=ev.source,
                claim=ev.claim,
            )
            if not match:
                _log.error(
                    "synthesis.citation_mapper.fabrication_detected",
                    fabricated_claim=ev.claim,
                    fabricated_source=ev.source,
                )
                return None
            verified_evidence.append(match)

        return verified_evidence

    def _find_matching_evidence(self, cited: RawCitedEvidence) -> Evidence | None:
        """Match cited raw evidence using ID-first matching with text fallback."""
        return self._find_matching_evidence_fields(
            evidence_id=cited.evidence_id,
            source=cited.source,
            claim=cited.claim,
        )

    def _find_matching_evidence_fields(
        self,
        evidence_id: object | None,
        source: str,
        claim: str,
    ) -> Evidence | None:
        """Core lookup logic matching ID-first with text fallback."""
        self.total_citations += 1

        # 1. Primary path: Direct UUID lookup
        if evidence_id is not None:
            uuid_str = str(evidence_id)
            if uuid_str in self.id_index:
                match = self.id_index[uuid_str]
                self.matched_by_id_count += 1
                _log.info(
                    "synthesis.citation_mapper.matched_by_id",
                    evidence_id=uuid_str,
                )
                return match

        # 2. Track missing/unmatched ID telemetry before fallback
        self.citation_missing_id_count += 1
        _log.info(
            "synthesis.citation_mapper.citation_missing_id",
            cited_source=source,
        )

        # 3. Fallback path: Text-normalization matching
        key = (self._normalize_text(source), self._normalize_text(claim))
        candidates = self.text_index.get(key, [])

        if len(candidates) == 1:
            match = candidates[0]
            self.matched_by_text_fallback_count += 1
            _log.info(
                "synthesis.citation_mapper.matched_by_text_fallback",
                evidence_id=str(match.id),
                cited_source=source,
            )
            return match

        if len(candidates) > 1:
            self.citation_ambiguous_fallback_count += 1
            _log.error(
                "synthesis.citation_mapper.citation_ambiguous_fallback",
                candidate_count=len(candidates),
                cited_source=source,
                cited_claim=claim,
            )
            return None

        return None

    def _normalize_text(self, text: str) -> str:
        """Normalize string by removing whitespace and converting to lowercase."""
        if not text:
            return ""
        return re.sub(r"\s+", "", text).lower()

