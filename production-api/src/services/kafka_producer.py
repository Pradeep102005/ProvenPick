import json
import os
import asyncio
from datetime import datetime, timezone

KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_ARTICLES = os.environ.get("KAFKA_TOPIC_ARTICLES", "provenpick-articles")

# Fallback in-memory queue if Apache Kafka server is starting/reconnecting
_IN_MEMORY_EVENT_BUS = []

async def produce_article_published_event(article_data: dict):
    """
    Publishes an 'article.published' event to Apache Kafka topic 'provenpick-articles'.
    Event Schema:
    {
        "event_type": "article.published",
        "article_uuid": "...",
        "title": "...",
        "slug": "...",
        "category_name": "Electronics -> Smartphones",
        "l1_category": "Electronics",
        "l2_category": "Smartphones",
        "published_at": "2026-08-19T00:00:00Z"
    }
    """
    payload = {
        "event_type": "article.published",
        "article_uuid": str(article_data.get("article_uuid", "")),
        "title": article_data.get("title", ""),
        "slug": article_data.get("slug", ""),
        "category_name": article_data.get("category_name", "Electronics"),
        "l1_category": article_data.get("l1_category", "Electronics"),
        "l2_category": article_data.get("l2_category", "Smartphones"),
        "published_at": datetime.now(timezone.utc).isoformat()
    }

    try:
        from aiokafka import AIOKafkaProducer
        producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
        await producer.start()
        try:
            val = json.dumps(payload).encode("utf-8")
            await producer.send_and_wait(KAFKA_TOPIC_ARTICLES, val)
            print(f"⚡ [KAFKA PRODUCER] Published 'article.published' event to topic '{KAFKA_TOPIC_ARTICLES}' for: {payload['title']}")
        finally:
            await producer.stop()
    except Exception as err:
        print(f"⚠️ [KAFKA PRODUCER] Kafka broker notice ({err}). Storing in local event bus for consumer...")
        _IN_MEMORY_EVENT_BUS.append(payload)

def get_in_memory_event_bus():
    return _IN_MEMORY_EVENT_BUS
