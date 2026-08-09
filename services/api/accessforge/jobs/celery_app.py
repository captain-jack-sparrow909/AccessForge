from celery import Celery

from accessforge.core.config import get_settings

settings = get_settings()
celery_app = Celery("accessforge", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(name="accessforge.jobs.health_check")  # type: ignore[untyped-decorator]
def health_check() -> dict[str, str]:
    return {"status": "ok"}
