from celery import Celery

from accessforge.core.config import get_settings

settings = get_settings()
# Worker and beat processes start from this module, so task discovery must be
# explicit. Without the include list, a clean process exposes only the health
# task and cannot receive the durable deletion/CAD tasks or register schedules.
celery_app = Celery(
    "accessforge",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["accessforge.jobs.tasks"],
)
CELERY_BEAT_SCHEDULE: dict[str, dict[str, object]] = {
    "expire pending uploads": {
        "task": "accessforge.jobs.expire_pending_assets",
        "schedule": 3600.0,
    },
    "process durable deletion outbox": {
        "task": "accessforge.jobs.process_deletion_jobs",
        "schedule": 60.0,
    },
    "recover durable CAD jobs": {
        "task": "accessforge.jobs.recover_cad_jobs",
        "schedule": 60.0,
    },
}
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    timezone="UTC",
    enable_utc=True,
    beat_schedule=CELERY_BEAT_SCHEDULE,
)


@celery_app.task(name="accessforge.jobs.health_check")  # type: ignore[untyped-decorator]
def health_check() -> dict[str, str]:
    return {"status": "ok"}
