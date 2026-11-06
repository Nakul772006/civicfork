"""In-memory session store for CivicFork simulations."""

import uuid
from typing import Any, Dict, Optional, Union
from app.models.domain import SessionData


class SessionStore:
    """Thread-safe in-memory session storage holding authoritative SessionData keyed by UUID."""

    def __init__(self):
        self._sessions: Dict[str, SessionData] = {}

    def create(self, initial_data: Optional[Union[Dict[str, Any], SessionData]] = None) -> str:
        """Create a new session and return its unique session_id."""
        session_id = str(uuid.uuid4())
        if isinstance(initial_data, SessionData):
            sid = initial_data.session_id or session_id
            self._sessions[sid] = initial_data
            return sid

        record = SessionData(session_id=session_id)
        if initial_data:
            record.update(initial_data)
        self._sessions[session_id] = record
        return session_id

    def get(self, session_id: str) -> Optional[SessionData]:
        """Retrieve a session by ID or return None if it does not exist."""
        return self._sessions.get(session_id)

    def get_session_data(self, session_id: str) -> Optional[SessionData]:
        """Retrieve authoritative SessionData instance."""
        return self.get(session_id)

    def set_session_data(self, session_id: str, data: SessionData) -> None:
        """Store or replace authoritative SessionData for session_id."""
        self._sessions[session_id] = data

    def update(
        self, session_id: str, updates: Union[Dict[str, Any], SessionData]
    ) -> SessionData:
        """Update fields in an existing session."""
        session = self.get(session_id)
        if session is None:
            from app.exceptions import SessionNotFoundError
            raise SessionNotFoundError(session_id)

        if isinstance(updates, SessionData):
            self._sessions[session_id] = updates
            return updates

        session.update(updates)
        return session

    def delete(self, session_id: str) -> bool:
        """Remove a session if it exists."""
        return self._sessions.pop(session_id, None) is not None

    def count(self) -> int:
        """Return the count of active in-memory sessions."""
        return len(self._sessions)

    def clear(self) -> None:
        """Clear all active sessions (useful for tests)."""
        self._sessions.clear()


# Global singleton instance
session_store = SessionStore()
