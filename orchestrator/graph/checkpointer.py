"""Redis-backed LangGraph checkpointer.

Implements the BaseCheckpointSaver interface to persist graph state
in standard Redis (no enterprise modules required).
"""

from __future__ import annotations

from collections import ChainMap
from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    SerializerProtocol,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from redis.asyncio import Redis

from config.settings import get_settings


def _is_unpicklable_callable(val: Any) -> bool:
    return callable(val) and not isinstance(val, type)


def _normalize_serializable(obj: Any) -> Any:
    """Recursively convert ChainMap and mappings to python primitives, stripping callables."""
    if _is_unpicklable_callable(obj):
        return None
    if isinstance(obj, (ChainMap, Mapping)) or hasattr(obj, "maps"):
        return {
            str(k): _normalize_serializable(v)
            for k, v in obj.items()
            if k != "stream_writer" and not _is_unpicklable_callable(v)
        }
    if isinstance(obj, dict):
        return {
            str(k): _normalize_serializable(v)
            for k, v in obj.items()
            if k != "stream_writer" and not _is_unpicklable_callable(v)
        }
    if isinstance(obj, tuple):
        return tuple(
            _normalize_serializable(item) for item in obj if not _is_unpicklable_callable(item)
        )
    if isinstance(obj, (list, set)):
        return [_normalize_serializable(item) for item in obj if not _is_unpicklable_callable(item)]
    return obj


class GaiaOSSerializer(JsonPlusSerializer):
    """Custom JsonPlusSerializer that normalizes ChainMap and non-dict Mappings."""

    def __init__(self, *, pickle_fallback: bool = True, **kwargs: Any) -> None:
        super().__init__(pickle_fallback=pickle_fallback, **kwargs)

    def dumps_typed(self, obj: Any) -> tuple[str, bytes]:
        sanitized = _normalize_serializable(obj)
        try:
            return super().dumps_typed(sanitized)
        except Exception:
            import json

            return "json", json.dumps(sanitized, default=str).encode("utf-8")

    def dumps(self, obj: Any) -> bytes:
        type_, data_ = self.dumps_typed(obj)
        return type_.encode("utf-8") + b":" + data_

    def loads(self, data: bytes) -> Any:
        if b":" in data:
            type_bytes, _, payload = data.partition(b":")
            return self.loads_typed((type_bytes.decode("utf-8"), payload))
        return self.loads_typed(("msgpack", data))


class RedisCheckpointSaver(BaseCheckpointSaver):
    """An asynchronous LangGraph checkpointer that stores states in standard Redis."""

    def __init__(
        self,
        client: Redis,
        *,
        serde: SerializerProtocol | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        super().__init__(serde=serde or GaiaOSSerializer())
        self.client = client
        if ttl_seconds is not None:
            self.ttl_seconds: int | None = ttl_seconds
        else:
            self.ttl_seconds = get_settings().checkpoint_ttl_seconds

    # --- Synchronous placeholders to satisfy abstract interface ---
    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        print("\n[DIAGNOSTIC TRACE] RedisCheckpointSaver.get_tuple CALLED", flush=True)
        raise NotImplementedError("Use async aget_tuple instead.")

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        print("\n[DIAGNOSTIC TRACE] RedisCheckpointSaver.list CALLED", flush=True)
        raise NotImplementedError("Use async alist instead.")

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Any,
    ) -> RunnableConfig:
        print("\n[DIAGNOSTIC TRACE] RedisCheckpointSaver.put CALLED", flush=True)
        raise NotImplementedError("Use async aput instead.")

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        print("\n[DIAGNOSTIC TRACE] RedisCheckpointSaver.put_writes CALLED", flush=True)
        raise NotImplementedError("Use async aput_writes instead.")

    # --- Asynchronous contract implementation ---
    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """Fetch a specific checkpoint tuple by thread_id and optional checkpoint_id."""
        thread_id = config.get("configurable", {}).get("thread_id")
        checkpoint_id = config.get("configurable", {}).get("checkpoint_id")

        if not thread_id:
            return None

        if not checkpoint_id:
            # Fetch latest checkpoint_id for this thread
            key_latest = f"gaiaos:checkpoint:{thread_id}:latest"
            latest_id_bytes = await self.client.get(key_latest)
            if not latest_id_bytes:
                return None
            checkpoint_id = (
                latest_id_bytes.decode("utf-8")
                if isinstance(latest_id_bytes, bytes)
                else latest_id_bytes
            )

        key = f"gaiaos:checkpoint:{thread_id}:checkpoint:{checkpoint_id}"
        serialized = await self.client.get(key)
        if not serialized:
            return None

        data = cast(Any, self.serde).loads(serialized)
        checkpoint = data["checkpoint"]
        metadata = data["metadata"]
        parent_config = data.get("parent_config")

        # Fetch writes for this checkpoint
        writes_pattern = f"gaiaos:checkpoint:{thread_id}:writes:{checkpoint_id}:*"
        write_keys = [key async for key in self.client.scan_iter(match=writes_pattern)]
        pending_writes = []

        for wkey in write_keys:
            wkey_str = wkey.decode("utf-8") if isinstance(wkey, bytes) else wkey
            task_id = wkey_str.split(":")[-1]
            w_data = await self.client.get(wkey)
            if w_data:
                channel_values = cast(Any, self.serde).loads(w_data)
                for channel, value in channel_values:
                    pending_writes.append((task_id, channel, value))

        return CheckpointTuple(
            config=config,
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=parent_config,
            pending_writes=pending_writes,
        )

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Any,
    ) -> RunnableConfig:
        """Persist a new checkpoint to Redis with TTL expiration."""
        thread_id = config.get("configurable", {}).get("thread_id")
        checkpoint_id = checkpoint["id"]

        if not thread_id:
            raise ValueError("thread_id is required in config.configurable.")

        data = {
            "checkpoint": _normalize_serializable(checkpoint),
            "metadata": _normalize_serializable(metadata),
            "parent_config": _normalize_serializable(config),
        }
        serialized = cast(Any, self.serde).dumps(data)

        key = f"gaiaos:checkpoint:{thread_id}:checkpoint:{checkpoint_id}"
        key_latest = f"gaiaos:checkpoint:{thread_id}:latest"

        if self.ttl_seconds and self.ttl_seconds > 0:
            await self.client.set(key, serialized, ex=self.ttl_seconds)
            await self.client.set(key_latest, checkpoint_id, ex=self.ttl_seconds)
        else:
            await self.client.set(key, serialized)
            await self.client.set(key_latest, checkpoint_id)

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
            }
        }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Store intermediate task writes with TTL expiration."""
        thread_id = config.get("configurable", {}).get("thread_id")
        checkpoint_id = config.get("configurable", {}).get("checkpoint_id")

        if not thread_id or not checkpoint_id:
            raise ValueError("thread_id and checkpoint_id are required for aput_writes.")

        filtered_writes = [
            (channel, val)
            for channel, val in writes
            if channel != "stream_writer" and not callable(val)
        ]
        serialized = cast(Any, self.serde).dumps(_normalize_serializable(filtered_writes))
        key = f"gaiaos:checkpoint:{thread_id}:writes:{checkpoint_id}:{task_id}"

        if self.ttl_seconds and self.ttl_seconds > 0:
            await self.client.set(key, serialized, ex=self.ttl_seconds)
        else:
            await self.client.set(key, serialized)

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """List historical checkpoints for a given thread_id."""
        if not config:
            return

        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return

        # Fetch all checkpoint keys for this thread
        pattern = f"gaiaos:checkpoint:{thread_id}:checkpoint:*"
        keys = [key async for key in self.client.scan_iter(match=pattern)]

        tuples = []
        for key in keys:
            serialized = await self.client.get(key)
            if serialized:
                data = cast(Any, self.serde).loads(serialized)
                checkpoint = data["checkpoint"]
                metadata = data["metadata"]
                parent_config = data.get("parent_config")
                checkpoint_id = checkpoint["id"]

                # Fetch writes for this checkpoint
                writes_pattern = f"gaiaos:checkpoint:{thread_id}:writes:{checkpoint_id}:*"
                write_keys = [key async for key in self.client.scan_iter(match=writes_pattern)]
                pending_writes = []

                for wkey in write_keys:
                    wkey_str = wkey.decode("utf-8") if isinstance(wkey, bytes) else wkey
                    task_id = wkey_str.split(":")[-1]
                    w_data = await self.client.get(wkey)
                    if w_data:
                        channel_values = cast(Any, self.serde).loads(w_data)
                        for channel, value in channel_values:
                            pending_writes.append((task_id, channel, value))

                c_config: RunnableConfig = {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_id": checkpoint_id,
                    }
                }
                tuples.append(
                    CheckpointTuple(
                        config=c_config,
                        checkpoint=checkpoint,
                        metadata=metadata,
                        parent_config=parent_config,
                        pending_writes=pending_writes,
                    )
                )

        # Sort checkpoints by step or timestamp (newest first)
        def get_sort_key(t: CheckpointTuple) -> str:
            return t.checkpoint.get("ts", "")

        tuples.sort(key=get_sort_key, reverse=True)

        before_checkpoint_id = (
            before.get("configurable", {}).get("checkpoint_id") if before else None
        )

        count = 0
        found_before = False if before_checkpoint_id else True

        for t in tuples:
            if before_checkpoint_id and not found_before:
                if t.config["configurable"]["checkpoint_id"] == before_checkpoint_id:
                    found_before = True
                    # "before" is exclusive
                    continue
                continue

            yield t
            count += 1
            if limit and count >= limit:
                break
