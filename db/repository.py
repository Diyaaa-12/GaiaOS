"""Database repository functions for managing user investigations."""

from __future__ import annotations

import uuid
from collections import ChainMap
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.alert_incident import AlertIncident
from db.models.alert_rule import AlertRule
from db.models.investigation import Investigation
from db.models.password_reset_token import PasswordResetToken
from db.models.user import User
from orchestrator.schemas.agent_io import Evidence


class UserRepository:
    """Helper repository to manage CRUD operations for users."""

    @staticmethod
    async def create_user(
        session: AsyncSession,
        email: str,
        hashed_password: str,
        full_name: str | None = None,
        role: str = "user",
        is_verified: bool = False,
        hashed_verification_token: str | None = None,
        verification_token_expires_at: datetime | None = None,
    ) -> User:
        user = User(
            email=email.lower().strip(),
            hashed_password=hashed_password,
            full_name=full_name,
            role=role,
            is_active=True,
            is_verified=is_verified,
            hashed_verification_token=hashed_verification_token,
            verification_token_expires_at=verification_token_expires_at,
        )
        session.add(user)
        try:
            await session.commit()
        except Exception as exc:
            await session.rollback()
            raise exc
        await session.refresh(user)
        return user

    @staticmethod
    async def get_user_by_email(
        session: AsyncSession,
        email: str,
        include_deleted: bool = False,
    ) -> User | None:
        stmt = select(User).where(User.email == email.lower().strip())
        if not include_deleted:
            stmt = stmt.where(User.deleted_at.is_(None))
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_id(
        session: AsyncSession,
        user_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> User | None:
        stmt = select(User).where(User.id == user_id)
        if not include_deleted:
            stmt = stmt.where(User.deleted_at.is_(None))
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_hashed_verification_token(
        session: AsyncSession,
        hashed_token: str,
    ) -> User | None:
        stmt = select(User).where(
            User.hashed_verification_token == hashed_token,
            User.deleted_at.is_(None),
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def verify_user_email(
        session: AsyncSession,
        user: User,
    ) -> User:
        user.is_verified = True
        user.hashed_verification_token = None
        user.verification_token_expires_at = None
        try:
            await session.commit()
        except Exception as exc:
            await session.rollback()
            raise exc
        await session.refresh(user)
        return user

    @staticmethod
    async def update_last_login(
        session: AsyncSession,
        user_id: uuid.UUID,
    ) -> None:
        user = await UserRepository.get_user_by_id(session, user_id)
        if user:
            user.last_login_at = datetime.now(UTC)
            try:
                await session.commit()
            except Exception:
                await session.rollback()

    @staticmethod
    async def update_verification_token(
        session: AsyncSession,
        user: User,
        hashed_token: str,
        expires_at: datetime,
    ) -> User:
        user.hashed_verification_token = hashed_token
        user.verification_token_expires_at = expires_at
        try:
            await session.commit()
        except Exception as exc:
            await session.rollback()
            raise exc
        await session.refresh(user)
        return user

    @staticmethod
    async def soft_delete_user(
        session: AsyncSession,
        user_id: uuid.UUID,
    ) -> bool:
        user = await UserRepository.get_user_by_id(session, user_id)
        if not user:
            return False
        user.deleted_at = datetime.now(UTC)
        user.is_active = False
        try:
            await session.commit()
            return True
        except Exception:
            await session.rollback()
            return False

    @staticmethod
    async def create_password_reset_token(
        session: AsyncSession,
        user_id: uuid.UUID,
        hashed_token: str,
        expires_at: datetime,
    ) -> PasswordResetToken:
        """Persist a new password reset token record."""
        token_record = PasswordResetToken(
            user_id=user_id,
            hashed_token=hashed_token,
            expires_at=expires_at,
        )
        session.add(token_record)
        try:
            await session.commit()
        except Exception as exc:
            await session.rollback()
            raise exc
        await session.refresh(token_record)
        return token_record

    @staticmethod
    async def reset_password_with_token(
        session: AsyncSession,
        hashed_token: str,
        new_hashed_password: str,
    ) -> User | None:
        """Atomic password reset execution.

        Executes all four operations within a single database transaction using pessimistic locking:
        1. Fetch valid, unexpired, unconsumed reset token with row lock (SELECT FOR UPDATE).
        2. Fetch associated user.
        3. Update user's hashed password.
        4. Consume presented token and invalidate ALL open reset tokens for user (used_at = now()).
        """
        now = datetime.now(UTC)
        try:
            stmt = (
                select(PasswordResetToken)
                .where(
                    PasswordResetToken.hashed_token == hashed_token,
                    PasswordResetToken.used_at.is_(None),
                    PasswordResetToken.expires_at > now,
                )
                .with_for_update()
            )
            res = await session.execute(stmt)
            token_obj = res.scalar_one_or_none()
            if not token_obj:
                return None

            stmt_user = select(User).where(User.id == token_obj.user_id, User.deleted_at.is_(None))
            res_user = await session.execute(stmt_user)
            user = res_user.scalar_one_or_none()
            if not user or not user.is_active:
                return None

            user.hashed_password = new_hashed_password

            # Invalidate presented token and all remaining active reset tokens for user
            await session.execute(
                update(PasswordResetToken)
                .where(
                    PasswordResetToken.user_id == user.id,
                    PasswordResetToken.used_at.is_(None),
                )
                .values(used_at=now)
            )
            await session.commit()
            await session.refresh(user)
            return user
        except Exception as exc:
            await session.rollback()
            raise exc


def _normalize_serializable(obj: Any) -> Any:
    """Recursively convert ChainMap and non-dict mappings to standard python primitives."""
    if isinstance(obj, (ChainMap, Mapping)) or hasattr(obj, "maps"):
        return {str(k): _normalize_serializable(v) for k, v in obj.items()}
    if isinstance(obj, dict):
        return {str(k): _normalize_serializable(v) for k, v in obj.items()}
    if isinstance(obj, tuple):
        return tuple(_normalize_serializable(item) for item in obj)
    if isinstance(obj, (list, set)):
        return [_normalize_serializable(item) for item in obj]
    return obj


class InvestigationRepository:
    """Helper repository to manage CRUD operations for investigations."""

    @staticmethod
    async def create_investigation(
        session: AsyncSession,
        query: str,
        user_id: uuid.UUID | None = None,
    ) -> Investigation:
        """Create a new investigation in the 'planning' status."""
        investigation = Investigation(
            query_text=query,
            user_id=user_id,
            status="planning",
        )
        session.add(investigation)
        try:
            await session.commit()
        except Exception as exc:
            await session.rollback()
            raise exc
        await session.refresh(investigation)
        return investigation

    @staticmethod
    async def update_investigation_status(
        session: AsyncSession,
        investigation_id: uuid.UUID,
        status: str,
        complexity_tier: str | None = None,
        answer: str | None = None,
        confidence: float | None = None,
        execution_trace: dict[str, Any] | None = None,
    ) -> Investigation | None:
        """Update fields of an investigation, setting completed_at if entering terminal status."""
        investigation = await InvestigationRepository.get_investigation(session, investigation_id)
        if not investigation:
            return None

        investigation.status = status
        if complexity_tier is not None:
            investigation.complexity_tier = complexity_tier
        if answer is not None:
            investigation.answer = answer
        if confidence is not None:
            investigation.confidence = confidence
        if execution_trace is not None:
            investigation.execution_trace = _normalize_serializable(execution_trace)

        if status in ("complete", "failed"):
            investigation.completed_at = datetime.now(UTC)

        try:
            await session.commit()
        except Exception as exc:
            await session.rollback()
            raise exc
        await session.refresh(investigation)
        return investigation

    @staticmethod
    async def get_investigation(
        session: AsyncSession,
        investigation_id: uuid.UUID,
    ) -> Investigation | None:
        """Retrieve an investigation by its primary key ID."""
        stmt = select(Investigation).where(Investigation.id == investigation_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


class LiteratureRepository:
    """Helper repository to manage CRUD and hybrid retrieval operations for literature chunks."""

    @staticmethod
    async def hybrid_search(
        session: AsyncSession,
        query: str,
        query_embedding: list[float] | None,
        k: int = 10,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        embedding_duration_ms: int = 0,
        retrieval_start_time: float | None = None,
    ) -> list[Evidence]:
        """Perform hybrid search (vector similarity + FTS) over literature chunks.

        Merges results using Reciprocal Rank Fusion (RRF) and normalizes the scores.
        """
        import time

        from sqlalchemy import func, select

        from db.models.literature_chunk import LiteratureChunk
        from logging_config import get_logger
        from orchestrator.schemas.agent_io import Evidence

        _log = get_logger(__name__)

        retrieval_start = retrieval_start_time or time.perf_counter()
        vector_results = []
        fts_results = []

        # 1. Vector similarity search
        if query_embedding is not None:
            stmt_vector = (
                select(LiteratureChunk)
                .order_by(LiteratureChunk.embedding.cosine_distance(query_embedding))
                .limit(k)
            )
            res_vector = await session.execute(stmt_vector)
            vector_results = list(res_vector.scalars().all())

        # 2. Full-text search
        stmt_fts = (
            select(LiteratureChunk)
            .where(LiteratureChunk.ts_content.op("@@")(func.plainto_tsquery("english", query)))
            .order_by(
                func.ts_rank(
                    LiteratureChunk.ts_content, func.plainto_tsquery("english", query)
                ).desc()
            )
            .limit(k)
        )
        res_fts = await session.execute(stmt_fts)
        fts_results = list(res_fts.scalars().all())

        # 3. Reciprocal Rank Fusion (RRF)
        # rrf_constant (k) is set to 60 as documented in Cormack et al. (2009).
        rrf_constant = 60
        ranks_vector = {chunk.id: idx + 1 for idx, chunk in enumerate(vector_results)}
        ranks_fts = {chunk.id: idx + 1 for idx, chunk in enumerate(fts_results)}

        all_chunk_ids = set(ranks_vector.keys()) | set(ranks_fts.keys())
        chunk_lookup = {chunk.id: chunk for chunk in vector_results + fts_results}

        rrf_scores = {}
        for cid in all_chunk_ids:
            score = 0.0
            if cid in ranks_vector:
                score += 1.0 / (rrf_constant + ranks_vector[cid])
            if cid in ranks_fts:
                score += 1.0 / (rrf_constant + ranks_fts[cid])
            rrf_scores[cid] = score

        # Sort and take top k
        sorted_chunk_ids = sorted(all_chunk_ids, key=lambda x: rrf_scores[x], reverse=True)
        top_k_ids = sorted_chunk_ids[:k]

        # Max possible score occurs when a document is ranked #1 in both vector and FTS lists
        max_possible_score = 2.0 / (rrf_constant + 1)

        evidence_list = []
        for cid in top_k_ids:
            chunk = chunk_lookup[cid]
            score = rrf_scores[cid]
            # Normalize to 0-1 range
            normalized_score = score / max_possible_score
            normalized_score = max(0.0, min(1.0, normalized_score))

            meta = chunk.extra_metadata or {}
            chunk_id = meta.get("chunk_id")
            title = meta.get("title")

            evidence_list.append(
                Evidence(
                    source=chunk.document_id,
                    claim=chunk.chunk_text,
                    confidence=normalized_score,
                    document_id=chunk.document_id,
                    chunk_id=chunk_id,
                    title=title,
                    source_url=chunk.source_url,
                )
            )

        retrieval_duration_ms = int((time.perf_counter() - retrieval_start) * 1000)

        # Log detailed retrieval statistics
        _log.info(
            "literature.retrieval.stats",
            query=query,
            embedding_duration_ms=embedding_duration_ms,
            retrieval_duration_ms=retrieval_duration_ms,
            vector_result_count=len(vector_results),
            fts_result_count=len(fts_results),
            fusion_top_k=len(evidence_list),
        )

        return evidence_list

    @staticmethod
    async def seed_chunks(
        session: AsyncSession,
        chunks: list[dict],
    ) -> None:
        """Seed literature chunks into the database, implementing idempotency checks.

        Skips documents if they are already present in the database.
        """
        from sqlalchemy import select

        from db.models.literature_chunk import LiteratureChunk

        # Group by document_id to do document-level checking
        doc_chunks: dict[str, list[dict[str, Any]]] = {}

        for ch in chunks:
            doc_id = ch["document_id"]
            doc_chunks.setdefault(doc_id, []).append(ch)

        for doc_id, chunk_list in doc_chunks.items():
            # Check if this document has already been seeded
            stmt = select(LiteratureChunk.id).where(LiteratureChunk.document_id == doc_id).limit(1)
            res = await session.execute(stmt)
            if res.scalar_one_or_none() is not None:
                # Document already exists, skip it
                continue

            for ch in chunk_list:
                db_chunk = LiteratureChunk(
                    document_id=ch["document_id"],
                    chunk_text=ch["chunk_text"],
                    embedding=ch.get("embedding"),
                    source_url=ch.get("source_url"),
                    extra_metadata=ch.get("extra_metadata"),
                )
                session.add(db_chunk)

        try:
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise e


async def find_causal_chain(
    event_type: str,
    point: tuple[float, float],
    radius_meters: float,
    max_depth: int = 4,
    statement_timeout_ms: int = 2000,
) -> list[Evidence]:
    """Exposed stable public interface for causal chain traversal reasoning.

    Internally queries via CausalChainRepository using AsyncSessionLocal.
    """
    from db.causal_repository import CausalChainRepository
    from db.session import AsyncSessionLocal

    if AsyncSessionLocal is None:
        raise RuntimeError("Database session factory is not initialised.")

    async with AsyncSessionLocal() as session:
        return await CausalChainRepository.find_causal_chain(
            session=session,
            event_type=event_type,
            point=point,
            radius_meters=radius_meters,
            max_depth=max_depth,
            statement_timeout_ms=statement_timeout_ms,
        )


class AlertRepository:
    """Repository helper for AlertRules and AlertIncidents CRUD operations."""

    @staticmethod
    async def upsert_alert_rule(
        session: AsyncSession,
        name: str,
        metric: str,
        threshold: float,
        comparison: str = "gt",
        window: str = "15m",
        severity: str = "warning",
        consecutive_cycles: int = 1,
        is_enabled: bool = True,
    ) -> AlertRule:
        """Create or update an alert rule by name (idempotent upsert)."""
        stmt = select(AlertRule).where(AlertRule.name == name)
        res = await session.execute(stmt)
        rule = res.scalar_one_or_none()

        if rule:
            rule.metric = metric
            rule.threshold = threshold
            rule.comparison = comparison
            rule.window = window
            rule.severity = severity
            rule.consecutive_cycles = consecutive_cycles
            rule.is_enabled = is_enabled
        else:
            rule = AlertRule(
                name=name,
                metric=metric,
                threshold=threshold,
                comparison=comparison,
                window=window,
                severity=severity,
                consecutive_cycles=consecutive_cycles,
                is_enabled=is_enabled,
            )
            session.add(rule)

        try:
            await session.commit()
        except Exception as exc:
            await session.rollback()
            raise exc

        await session.refresh(rule)
        return rule

    @staticmethod
    async def get_active_alert_rules(session: AsyncSession) -> list[AlertRule]:
        """Fetch all active (is_enabled=True) alert rules."""
        stmt = select(AlertRule).where(AlertRule.is_enabled.is_(True))
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def list_alert_rules(session: AsyncSession) -> list[AlertRule]:
        """Fetch all alert rules."""
        stmt = select(AlertRule).order_by(AlertRule.name)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_alert_rule_by_id(session: AsyncSession, rule_id: uuid.UUID) -> AlertRule | None:
        """Fetch an alert rule by primary key ID."""
        stmt = select(AlertRule).where(AlertRule.id == rule_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def delete_alert_rule(session: AsyncSession, rule_id: uuid.UUID) -> bool:
        """Delete an alert rule by primary key ID."""
        rule = await AlertRepository.get_alert_rule_by_id(session, rule_id)
        if not rule:
            return False
        await session.delete(rule)
        try:
            await session.commit()
            return True
        except Exception as exc:
            await session.rollback()
            raise exc

    @staticmethod
    async def get_open_incident_by_rule_name(
        session: AsyncSession, rule_name: str
    ) -> AlertIncident | None:
        """Fetch an open ('firing') incident for a specific rule name."""
        stmt = select(AlertIncident).where(
            AlertIncident.rule_name == rule_name,
            AlertIncident.status == "firing",
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def create_incident(
        session: AsyncSession,
        rule_id: uuid.UUID | None,
        rule_name: str,
        severity: str,
        last_value: float,
        threshold: float,
        consecutive_violations: int = 1,
        slo_name: str | None = None,
    ) -> AlertIncident:
        """Record a new firing alert incident."""
        incident = AlertIncident(
            rule_id=rule_id,
            rule_name=rule_name,
            slo_name=slo_name,
            severity=severity,
            status="firing",
            last_value=last_value,
            threshold=threshold,
            consecutive_violations=consecutive_violations,
            fired_at=datetime.now(UTC),
        )
        session.add(incident)
        try:
            await session.commit()
        except Exception as exc:
            await session.rollback()
            raise exc
        await session.refresh(incident)
        return incident

    @staticmethod
    async def update_incident_last_value(
        session: AsyncSession,
        incident_id: uuid.UUID,
        last_value: float,
        consecutive_violations: int,
    ) -> None:
        """Update last_value and consecutive_violations on an open incident."""
        stmt = select(AlertIncident).where(AlertIncident.id == incident_id)
        res = await session.execute(stmt)
        incident = res.scalar_one_or_none()
        if incident:
            incident.last_value = last_value
            incident.consecutive_violations = consecutive_violations
            try:
                await session.commit()
            except Exception:
                await session.rollback()

    @staticmethod
    async def resolve_incident(
        session: AsyncSession,
        incident_id: uuid.UUID,
    ) -> AlertIncident | None:
        """Mark an open incident as resolved."""
        stmt = select(AlertIncident).where(AlertIncident.id == incident_id)
        res = await session.execute(stmt)
        incident = res.scalar_one_or_none()
        if incident and incident.status == "firing":
            incident.status = "resolved"
            incident.resolved_at = datetime.now(UTC)
            try:
                await session.commit()
                await session.refresh(incident)
                return incident
            except Exception as exc:
                await session.rollback()
                raise exc
        return incident

    @staticmethod
    async def list_incidents(
        session: AsyncSession,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AlertIncident]:
        """List alert incidents with optional status filter."""
        stmt = select(AlertIncident)
        if status:
            stmt = stmt.where(AlertIncident.status == status)
        stmt = stmt.order_by(AlertIncident.fired_at.desc()).limit(limit).offset(offset)
        res = await session.execute(stmt)
        return list(res.scalars().all())
