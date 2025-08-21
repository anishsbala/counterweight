from __future__ import annotations

import logging
import os
import signal
import socket
from typing import Callable

from fastapi import HTTPException

from app.db import wait_for_database
from app.jobs import JobService
from app.main import verify_article
from app.schemas import VerifyArticleRequest, VerifyArticleResponse

LOGGER = logging.getLogger(__name__)
RUNNING = True


def stop_worker(signum, frame) -> None:
    del signum, frame
    global RUNNING
    RUNNING = False


def process_next_job(
    jobs: JobService,
    verifier: Callable[[VerifyArticleRequest], VerifyArticleResponse],
    worker_id: str,
    timeout: int = 5,
) -> bool:
    job_id = jobs.next_job(timeout=timeout)
    if job_id is None:
        return False

    claimed = jobs.claim_job(job_id, worker_id)
    if claimed is None:
        return True

    try:
        payload = VerifyArticleRequest(**claimed["payload"])
        result = verifier(payload)
        jobs.complete_job(job_id, result.model_dump(mode="json"))
        LOGGER.info("completed job=%s attempt=%s", job_id, claimed["attempts"])
    except Exception as exc:
        if isinstance(exc, HTTPException):
            error = str(exc.detail)
        else:
            error = str(exc) or exc.__class__.__name__
        retry = jobs.fail_job(job_id, error)
        LOGGER.exception("job=%s failed retry=%s", job_id, retry)
    return True


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    signal.signal(signal.SIGTERM, stop_worker)
    signal.signal(signal.SIGINT, stop_worker)
    wait_for_database()
    jobs = JobService()
    worker_id = os.getenv("WORKER_ID", socket.gethostname())
    LOGGER.info("worker=%s ready", worker_id)

    while RUNNING:
        process_next_job(jobs, verify_article, worker_id)


if __name__ == "__main__":
    main()
