"""Foundation integration tests exercising the end-to-end backend flow."""

from app.api.dependencies import get_config, get_valid_session
from app.config_loader import AppConfig, load_app_config
from app.models.domain import PlotLocation, SessionData
from app.session import session_store


def test_foundation_integration_flow(client):
    """Exercise the end-to-end foundation integration:
    1. Load application configuration.
    2. Create a session containing valid SessionData.
    3. Retrieve that session through the FastAPI dependency path.
    4. Confirm the returned object is the authoritative SessionData.
    5. Confirm /api/health reports the configuration as loaded.
    """
    # 1. Load application configuration
    config = load_app_config(force_reload=True)
    assert isinstance(config, AppConfig)
    assert len(config.scenarios.scenarios) == 7
    assert len(config.scoring.base_scores) == 7
    assert len(config.feasibility.scenarios) == 7

    # Confirm FastAPI dependency retrieves the same loaded configuration
    dep_config = get_config()
    assert dep_config is config

    # 2. Create a session containing valid SessionData
    plot = PlotLocation(lat=12.3100, lng=76.6500, radius_m=2000, area_sqm=3000.0)
    session_data = SessionData(
        session_id="foundation-integ-test-session",
        plot=plot,
    )
    sid = session_store.create(session_data)
    assert sid == "foundation-integ-test-session"

    # 3. Retrieve that session through the FastAPI dependency path
    retrieved_session = get_valid_session(session_id=sid)

    # 4. Confirm the returned object is the authoritative SessionData
    assert isinstance(retrieved_session, SessionData)
    assert retrieved_session.session_id == sid
    assert retrieved_session.plot.lat == 12.3100
    assert retrieved_session.plot.lng == 76.6500
    assert retrieved_session.plot.radius_m == 2000
    assert retrieved_session.plot.area_sqm == 3000.0
    assert retrieved_session is session_data

    # 5. Confirm /api/health reports the configuration as loaded and session count
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["error"] is None
    data = payload["data"]
    assert data["status"] == "healthy"
    assert data["osm_data_loaded"] is True
    assert data["config_loaded"] is True
    assert data["active_sessions"] >= 1
    assert data["demo_area"] == "mysuru"

    # Clean up session
    session_store.delete(sid)
