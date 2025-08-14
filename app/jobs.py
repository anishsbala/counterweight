from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

import redis
from psycopg2.extras import Json

from app.config import REDIS_URL
from app.db import fetch_all, fetch_one, get_db_connection

QUEUE_NAME = "counterweight:verification_jobs"


class RedisJobQueue:
    def __init__(self, url: str = REDIS_URL) -> None:
        self.client = redis.Redis.from_url(url, decode_responses=True)

    def enqueue(self, job_id: str) -> None:
        self.client.lpush(QUEUE_NAME, job_id)

    def dequeue(self, timeout: int = 5) -> Optional[str]:
        item = self.client.brpop(QUEUE_NAME, timeout=timeout)
        return None if item is None else item[1]

    def ping(self) -> bool:
        return bool(self.client.ping())


class JobRepository:
    def create(self, payload: Dict[str, Any], max_attempts: int = 3) -> Dict[str, Any]:
        job_id = str(uuid.uuid4())
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO verification_jobs (id, status, payload, max_attempts)
                    VALUES (%s, 'QUEUED', %s, %s)
                    RETURNING id, status, created_at
                    """,
                    (job_id, Json(payload), max_attempts),
                )
                row = cur.fetchone()
        return {"job_id": str(row["id"]), "status": row["status"], "created_at": row["created_at"]}

    def claim(self, job_id: str, worker_id: str) -> Optional[Dict[str, Any]]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE verification_jobs
                    SET
                        status = 'RUNNING',
                        worker_id = %s,
                        attempts = attempts + 1,
                        started_at = NOW(),
                        error = NULL
                    WHERE id = %s AND status = 'QUEUED'
                    RETURNING payload, attempts, max_attempts
                    """,
                    (worker_id, job_id),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return {
            "payload": row["payload"],
            "attempts": int(row["attempts"]),
            "max_attempts": int(row["max_attempts"]),
        }

    def complete(self, job_id: str, result: Dict[str, Any]) -> None:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE verification_jobs
                    SET status = 'SUCCEEDED', result = %s, completed_at = NOW()
                    WHERE id = %s AND status = 'RUNNING'
                    """,
                    (Json(result), job_id),
                )

    def fail(self, job_id: str, error: str) -> bool:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT attempts, max_attempts
                    FROM verification_jobs
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (job_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return False
                retry = int(row["attempts"]) < int(row["max_attempts"])
                cur.execute(
                    """
                    UPDATE verification_jobs
                    SET
                        status = %s,
                        error = %s,
                        worker_id = NULL,
                        completed_at = CASE WHEN %s THEN NULL ELSE NOW() END
                    WHERE id = %s
                    """,
                    ("QUEUED" if retry else "FAILED", error[:1000], retry, job_id),
                )
        return retry

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        row = fetch_one(
            """
            SELECT id, status, attempts, max_attempts, worker_id, error, result,
                   created_at, started_at, completed_at
            FROM verification_jobs
            WHERE id = %s
            """,
            (job_id,),
        )
        return None if row is None else self._normalize(row)

    def list(self, limit: int = 50) -> List[Dict[str, Any]]:
        rows = fetch_all(
            """
            SELECT id, status, attempts, max_attempts, worker_id, error, result,
                   created_at, started_at, completed_at
            FROM verification_jobs
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        return [self._normalize(row) for row in rows]

    def queued_ids(self) -> List[str]:
        rows = fetch_all("SELECT id FROM verification_jobs WHERE status = 'QUEUED' ORDER BY created_at ASC")
        return [str(row["id"]) for row in rows]

    @staticmethod
    def _normalize(row: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(row)
        normalized["job_id"] = str(normalized.pop("id"))
        if isinstance(normalized.get("result"), str):
            normalized["result"] = json.loads(normalized["result"])
        return normalized


class JobService:
    def __init__(
        self,
        repository: Optional[JobRepository] = None,
        queue: Optional[RedisJobQueue] = None,
    ) -> None:
        self.repository = repository or JobRepository()
        self.queue = queue or RedisJobQueue()

    def create_job(self, payload: Dict[str, Any], max_attempts: int = 3) -> Dict[str, Any]:
        job = self.repository.create(payload, max_attempts=max_attempts)
        self.queue.enqueue(job["job_id"])
        return {
            "job_id": job["job_id"],
            "status": job["status"],
            "status_url": f"/jobs/{job['job_id']}",
        }

    def next_job(self, timeout: int = 5) -> Optional[str]:
        return self.queue.dequeue(timeout=timeout)

    def claim_job(self, job_id: str, worker_id: str) -> Optional[Dict[str, Any]]:
        return self.repository.claim(job_id, worker_id)

    def complete_job(self, job_id: str, result: Dict[str, Any]) -> None:
        self.repository.complete(job_id, result)

    def fail_job(self, job_id: str, error: str) -> bool:
        retry = self.repository.fail(job_id, error)
        if retry:
            self.queue.enqueue(job_id)
        return retry

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self.repository.get(job_id)

    def list_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.repository.list(limit)

    def recover_queued_jobs(self) -> int:
        job_ids = self.repository.queued_ids()
        for job_id in job_ids:
            self.queue.enqueue(job_id)
        return len(job_ids)
