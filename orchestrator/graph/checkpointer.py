"""Redis-backed LangGraph checkpointer.

Implements the BaseCheckpointSaver interface to persist graph state
in standard Redis (no enterprise modules required).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Sequence
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    SerializerProtocol,
)
from redis.asyncio import Redis


class RedisCheckpointSaver(BaseCheckpointSaver):
    """An asynchronous LangGraph checkpointer that stores states in standard Redis."""

    def __init__(self, client: Redis, *, serde: SerializerProtocol | None = None) -> None:
        super().__init__(serde=serde)
        self.client = client

    # --- Synchronous placeholders to satisfy abstract interface ---
    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        raise NotImplementedError("Use async aget_tuple instead.")

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        raise NotImplementedError("Use async alist instead.")

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Any,
    ) -> RunnableConfig:
        raise NotImplementedError("Use async aput instead.")

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
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

        data = self.serde.loads(serialized)
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
                channel_values = self.serde.loads(w_data)
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
        """Persist a new checkpoint to Redis."""
        thread_id = config.get("configurable", {}).get("thread_id")
        checkpoint_id = checkpoint["id"]

        if not thread_id:
            raise ValueError("thread_id is required in config.configurable.")

        data = {
            "checkpoint": checkpoint,
            "metadata": metadata,
            "parent_config": config,
        }
        serialized = self.serde.dumps(data)

        key = f"gaiaos:checkpoint:{thread_id}:checkpoint:{checkpoint_id}"
        key_latest = f"gaiaos:checkpoint:{thread_id}:latest"

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
        """Store intermediate task writes."""
        thread_id = config.get("configurable", {}).get("thread_id")
        checkpoint_id = config.get("configurable", {}).get("checkpoint_id")

        if not thread_id or not checkpoint_id:
            raise ValueError("thread_id and checkpoint_id are required for aput_writes.")

        serialized = self.serde.dumps(writes)
        key = f"gaiaos:checkpoint:{thread_id}:writes:{checkpoint_id}:{task_id}"
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
                data = self.serde.loads(serialized)
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
                        channel_values = self.serde.loads(w_data)
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
