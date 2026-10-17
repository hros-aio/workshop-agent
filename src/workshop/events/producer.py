"""Outbound Kafka producer (confluent-kafka).

Kafka is used only to publish coarse-grained domain events for existing platform
modules. It never drives internal workshop logic. Disabled by default in tests
and local dev via WORKSHOP_KAFKA_ENABLED.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from workshop.logging import get_logger
from workshop.settings import get_settings

logger = get_logger(__name__)

_producer: Any | None = None


def _get_producer() -> Any | None:
    global _producer
    settings = get_settings()
    if not settings.kafka_enabled:
        return None
    if _producer is None:
        from confluent_kafka import Producer

        _producer = Producer({"bootstrap.servers": settings.kafka_bootstrap_servers})
    return _producer


def publish(topic: str, payload: dict[str, Any]) -> None:
    producer = _get_producer()
    if producer is None:
        logger.info("kafka.disabled", topic=topic, payload=payload)
        return
    producer.produce(topic, json.dumps(payload).encode("utf-8"))
    producer.poll(0)
    logger.info("kafka.published", topic=topic)


def emit_finalized(*, project_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    publish(
        get_settings().kafka_finalized_topic,
        {"projectId": str(project_id), "tenantId": str(tenant_id)},
    )


def emit_exported(*, project_id: uuid.UUID, tenant_id: uuid.UUID, package_version: int, storage_prefix: str) -> None:
    publish(
        get_settings().kafka_exported_topic,
        {
            "projectId": str(project_id),
            "tenantId": str(tenant_id),
            "packageVersion": package_version,
            "storagePrefix": storage_prefix,
        },
    )
