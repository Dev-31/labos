from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from labos.core.enums import SchedulerAction, SchedulerJobState
from labos.core.models import SchedulerJobCreateRequest
from labos.db.schema import SchedulerJobRow, utc_now


class SchedulerQuotaExceededError(Exception):
    pass


class SchedulerService:
    """Queue-oriented scheduler hook service for governed LabOS actions."""

    def __init__(self, *, max_pending_jobs_per_requester: int = 5) -> None:
        self.max_pending_jobs_per_requester = max_pending_jobs_per_requester

    def enqueue(self, session: Session, request: SchedulerJobCreateRequest) -> SchedulerJobRow:
        pending_count = session.scalar(
            select(func.count())
            .select_from(SchedulerJobRow)
            .where(
                SchedulerJobRow.requester_id == request.requester_id,
                SchedulerJobRow.state.in_(
                    [SchedulerJobState.QUEUED.value, SchedulerJobState.DISPATCHED.value]
                ),
            )
        )
        if pending_count is None:
            pending_count = 0
        if pending_count >= self.max_pending_jobs_per_requester:
            raise SchedulerQuotaExceededError

        row = SchedulerJobRow(
            id=str(uuid4()),
            action=request.action.value,
            state=SchedulerJobState.QUEUED.value,
            requester_id=request.requester_id,
            profile_name=request.profile_name,
            lab_id=request.lab_id,
            command=request.command,
            scheduled_for=request.scheduled_for or utc_now(),
            attempt_count=0,
            max_attempts=request.max_attempts,
        )
        session.add(row)
        session.flush()
        return row

    def list_jobs(self, session: Session) -> list[SchedulerJobRow]:
        return list(
            session.scalars(
            select(SchedulerJobRow).order_by(
                SchedulerJobRow.scheduled_for,
                SchedulerJobRow.created_at,
                SchedulerJobRow.id,
            )
            ).all()
        )

    def run_next(
        self,
        session: Session,
        *,
        create_lab: Callable[[str], str],
        create_run: Callable[[str, str], str],
        now: datetime | None = None,
    ) -> SchedulerJobRow | None:
        current_time = now or utc_now()
        job = session.scalars(
            select(SchedulerJobRow)
            .where(
                SchedulerJobRow.state == SchedulerJobState.QUEUED.value,
                SchedulerJobRow.scheduled_for <= current_time,
            )
            .order_by(
                SchedulerJobRow.scheduled_for,
                SchedulerJobRow.created_at,
                SchedulerJobRow.id,
            )
        ).first()
        if job is None:
            return None

        job.state = SchedulerJobState.DISPATCHED.value
        job.attempt_count += 1
        job.dispatched_at = current_time
        job.last_error = None
        session.flush()

        try:
            with session.begin_nested():
                action = SchedulerAction(job.action)
                if action is SchedulerAction.CREATE_LAB:
                    assert job.profile_name is not None
                    resource_type = "lab"
                    resource_id = create_lab(job.profile_name)
                else:
                    assert job.lab_id is not None
                    assert job.command is not None
                    resource_type = "run"
                    resource_id = create_run(job.lab_id, job.command)
        except Exception as exc:
            job.last_error = str(exc)
            if job.attempt_count >= job.max_attempts:
                job.state = SchedulerJobState.FAILED.value
                job.completed_at = utc_now()
            else:
                job.state = SchedulerJobState.QUEUED.value
            session.flush()
            return job

        job.state = SchedulerJobState.SUCCEEDED.value
        job.completed_at = utc_now()
        job.result_resource_type = resource_type
        job.result_resource_id = resource_id
        job.last_error = None
        session.flush()
        return job
