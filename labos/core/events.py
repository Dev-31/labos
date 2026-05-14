from __future__ import annotations

import json
from dataclasses import dataclass, field
from uuid import uuid4

from sqlalchemy.orm import Session

from labos.core.enums import ActorType
from labos.db.schema import EventRow


@dataclass(frozen=True)
class EventRecord:
    event_type: str
    payload: dict[str, object] = field(default_factory=dict)
    lab_id: str | None = None
    run_id: str | None = None
    actor_type: str = ActorType.SYSTEM.value
    actor_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None


class EventWriter:
    def __init__(self, session: Session) -> None:
        self._session = session

    def write(self, event: EventRecord) -> EventRow:
        row = EventRow(
            id=str(uuid4()),
            lab_id=event.lab_id,
            run_id=event.run_id,
            event_type=event.event_type,
            actor_type=event.actor_type,
            actor_id=event.actor_id,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            payload_json=json.dumps(event.payload, sort_keys=True),
        )
        self._session.add(row)
        return row
