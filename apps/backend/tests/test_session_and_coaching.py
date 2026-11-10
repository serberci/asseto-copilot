import json
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from telemetry_schema import reference_session, synthetic_session
from telemetry_schema.messages import SCHEMA_VERSION

from coach_backend.analysis import CornerMetrics
from coach_backend.api import create_app
from coach_backend.assembler import LapAssembler
from coach_backend.coaching import Scheduler, comparability, evaluate_corner
from coach_backend.copilot import ask, answer_audio, is_grounded
from coach_backend.references import ReferenceLibrary, compare_pro, grip_flags
from coach_backend.settings import Settings
from coach_backend.store import Store


class _Model:
    name = "fake-model"

    def complete(self, system: str, user: str) -> str:
        del system, user
        return json.dumps(
            {
                "intent": "lap_delta",
                "spoken_response": "You lost 9.9 seconds.",
                "severity": "info",
                "priority": 1,
                "evidence": {"time_loss_s": 9.9},
                "trigger_tts": True,
            }
        )


def _metrics(onset: float, entry: float) -> CornerMetrics:
    return CornerMetrics(
        corner_id="t1",
        name="Turn 1",
        braking_onset=onset,
        peak_brake=0.8,
        min_speed_mps=30,
        min_speed_progress=0.5,
        throttle_onset=0.55,
        full_throttle=0.58,
        entry_speed_mps=entry,
        exit_speed_mps=40,
        corner_time_s=6,
        coast_s=0.2,
    )


def test_incomparable_entry_speed_does_not_recommend_a_later_brake():
    current = _metrics(0.42, 55)
    reference = _metrics(0.46, 50)
    state = comparability(current, reference, same_setup=True)
    assert state.ok is False
    assert "entry_speed" in state.reasons
    events = evaluate_corner(current, reference, same_setup=True, time_impact_s=0.4)
    assert len(events) == 1
    assert events[0].advice == "none"
    assert events[0].recommendation_allowed is False
    assert "not comparable" in events[0].spoken_text


def test_scheduler_waits_for_a_straight_and_does_not_repeat(tmp_path):
    del tmp_path
    current = _metrics(0.42, 50)
    reference = _metrics(0.46, 50)
    events = evaluate_corner(current, reference, same_setup=True, time_impact_s=0.2)
    allowed = next(event for event in events if event.recommendation_allowed)
    blocked = next(event for event in events if not event.recommendation_allowed) if any(not event.recommendation_allowed for event in events) else None
    scheduler = Scheduler(cooldown_s=20)
    scheduler.push(allowed)
    if blocked:
        scheduler.push(blocked)
    assert scheduler.poll(brake=0.9, throttle=0.0, progress=0.1, now=0, corners=[]) is None
    spoken = scheduler.poll(brake=0.0, throttle=1.0, progress=0.1, now=1, corners=[])
    assert spoken is not None
    assert spoken.recommendation_allowed is True
    assert scheduler.poll(brake=0.0, throttle=1.0, progress=0.1, now=2, corners=[]) is None


def test_ungrounded_model_output_is_replaced():
    answer = ask("where am I losing time", {"available": False}, _Model())
    assert "9.9" not in answer["spoken_response"]
    assert answer["model"] == "rejected-ungrounded"
    assert answer["grounded"] is True


def test_audio_without_a_speech_engine_reports_that_it_is_unavailable():
    result = answer_audio(b"\x00\x00", 16000, lambda question: {"spoken_response": question}, None, None)
    assert result["code"] == "stt_unavailable"


def test_replay_records_a_lap_and_explains_the_loss_without_inventing_a_number(tmp_path):
    settings = Settings(data_dir=tmp_path, auth_token="test-token", ollama_host=None, ollama_model="", static_dir=None)
    store = Store(tmp_path)
    client = TestClient(create_app(settings, store))
    headers = {"Authorization": "Bearer test-token"}
    denied = client.get("/api/v1/sessions")
    assert denied.status_code == 401

    body = "\n".join(item.model_dump_json() for item in synthetic_session())
    replayed = client.post("/api/v1/replay", headers=headers, json={"jsonl": body})
    assert replayed.status_code == 200
    session_id = replayed.json()["session_id"]
    laps = client.get(f"/api/v1/sessions/{session_id}/laps", headers=headers).json()["laps"]
    valid = [lap for lap in laps if lap["valid"]]
    assert [lap["lap_time_ms"] for lap in valid] == [30000, 30400]
    slower = valid[1]
    report = client.get(f"/api/v1/laps/{slower['id']}/analysis", headers=headers).json()["report"]
    corner = report["corners"][0]
    assert corner["time_impact_s"] == pytest.approx(0.4, abs=0.05)
    brake = next(event for event in report["events"] if event["rule_id"] == "brake_point")
    assert brake["recommendation_allowed"] is True
    assert brake["advice"] == "reference_braked_later"
    assert is_grounded(brake["spoken_text"], {"evidence": brake["evidence"], "reference": brake["reference"], "name": "Turn 1"})

    answer = client.post(
        "/api/v1/copilot/ask",
        headers=headers,
        json={"session_id": session_id, "question": "where am I losing time"},
    ).json()
    assert answer["model"] == "deterministic-explainer"
    assert "0.4" in answer["spoken_response"]
    assert is_grounded(answer["spoken_response"], answer["evidence"])

    store.model = _Model()
    rejected = store.ask("where am I losing time", session_id)
    assert "9.9" not in rejected["spoken_response"]
    assert rejected["model"] == "rejected-ungrounded"


def test_telemetry_socket_rejects_a_bad_token_and_a_bad_message(tmp_path):
    settings = Settings(data_dir=tmp_path, auth_token="test-token", ollama_host=None, ollama_model="", static_dir=None)
    client = TestClient(create_app(settings, Store(tmp_path)))
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/telemetry") as socket:
            socket.receive_json()
    with client.websocket_connect("/ws/telemetry", headers={"Authorization": "Bearer test-token"}) as socket:
        socket.send_json({"type": "nope", "schema_version": SCHEMA_VERSION})
        error = socket.receive_json()
        assert error["type"] == "error"
        hello = synthetic_session()[0].model_dump(mode="json")
        socket.send_json(hello)
        ack = socket.receive_json()
        assert ack["type"] == "ack"


def test_a_straight_sample_delivers_one_coaching_line(tmp_path):
    settings = Settings(data_dir=tmp_path, auth_token="test-token", ollama_host=None, ollama_model="", static_dir=None)
    store = Store(tmp_path)
    client = TestClient(create_app(settings, store))
    headers = {"Authorization": "Bearer test-token"}
    messages = synthetic_session()
    body = "\n".join(item.model_dump_json() for item in messages)
    session_id = client.post("/api/v1/replay", headers=headers, json={"jsonl": body}).json()["session_id"]
    last = next(item for item in reversed(messages) if item.type == "telemetry")
    follow = last.model_copy(
        update={
            "sequence": last.sequence + 1,
            "timestamp": last.timestamp + timedelta(seconds=2),
            "payload": last.payload.model_copy(update={"throttle": 1.0, "brake": 0.0, "normalized_progress": 0.1}),
        }
    )
    store.ingest(follow)
    coaching = client.get(f"/api/v1/sessions/{session_id}/coaching", headers=headers).json()["coaching"]
    delivered = [event for event in coaching if event["delivered_at"]]
    assert len(delivered) == 1
    assert delivered[0]["recommendation_allowed"] is True


def test_tracks_do_not_include_the_uncalibrated_template(tmp_path):
    store = Store(tmp_path)
    names = [track["track_id"] for track in store.tracks.list_tracks()]
    assert names == ["synthetic-oval"]
    assert store.tracks.get("REPLACE_WITH_THE_GAME_TRACK_ID") is None
    assert store.tracks.get("synthetic-oval") is not None


def test_start_line_wrap_stays_one_lap():
    messages = [item for item in synthetic_session() if item.type == "telemetry"]
    in_lap = [item for item in messages if item.payload.lap_number == 1]
    boundary = next(item for item in messages if item.payload.completed_laps == 1 and item.payload.lap_number == 2)
    wrap = in_lap[-1].model_copy(
        update={
            "timestamp": in_lap[-1].timestamp + timedelta(milliseconds=50),
            "payload": in_lap[-1].payload.model_copy(update={"normalized_progress": 0.001, "completed_laps": 0}),
        }
    )
    assembler = LapAssembler()
    finished = None
    for message in [*in_lap, wrap, boundary]:
        finished = assembler.add(message) or finished
    assert finished is not None
    assert finished.valid
    assert finished.lap_time_ms == 30000
    assert "too_few_samples" not in finished.invalid_reasons
    assert "progress_reset" not in finished.invalid_reasons


def test_mid_lap_progress_drop_is_still_rejected():
    messages = [item for item in synthetic_session() if item.type == "telemetry" and item.payload.lap_number == 1]
    jump = messages[25].model_copy(
        update={
            "timestamp": messages[25].timestamp + timedelta(milliseconds=20),
            "payload": messages[25].payload.model_copy(update={"normalized_progress": 0.1}),
        }
    )
    assembler = LapAssembler()
    finished = None
    for message in [*messages[:26], jump]:
        finished = assembler.add(message) or finished
    assert finished is not None
    assert "progress_reset" in finished.invalid_reasons


def test_synthetic_mclaren_pack_is_not_an_accreplay_download():
    library = ReferenceLibrary()
    listed = library.list_laps()
    assert {item["id"] for item in listed} == {"synthetic-pro-spa-720s", "synthetic-user-spa-720s"}
    assert {item["source"] for item in listed} == {"synthetic-test"}
    pro = library.pro_for("assetto_corsa_competizione", "spa", "mclaren_720s_gt3_evo")
    user = library.get("synthetic-user-spa-720s")
    assert pro is not None and user is not None
    assert "not an accreplay download" in pro.note.lower()
    rows = [
        {
            "normalized_progress": sample.progress,
            "brake": sample.brake,
            "speed_mps": sample.speed_mps,
            "steering": sample.steering,
            "throttle": sample.throttle,
        }
        for sample in user.samples
    ]
    compared = compare_pro(
        rows,
        pro,
        game=pro.game,
        track_id=pro.track_id,
        car_model=pro.car_model,
        lap_time_ms=user.lap_time_ms,
    )
    assert compared["recommendation_allowed"] is True
    assert "0.40" in compared["spoken_text"]
    steering = next(tip for tip in compared["tips"] if tip["rule_id"] == "steering_peak")
    assert steering["recommendation_allowed"] is False
    other_game = compare_pro(
        rows,
        pro,
        game="assetto_corsa",
        track_id="spa",
        car_model="ks_ferrari_488_gt3",
        lap_time_ms=user.lap_time_ms,
    )
    assert other_game["available"] is False
    assert other_game["recommendation_allowed"] is False
    flags = grip_flags([sample.model_dump() for sample in user.samples])
    assert flags[0]["kind"] == "high_slip"
    assert flags[0]["recommendation_allowed"] is False


def test_replayed_mclaren_lap_is_compared_with_the_pro_file(tmp_path):
    library = ReferenceLibrary()
    user = library.get("synthetic-user-spa-720s")
    assert user is not None
    store = Store(tmp_path)
    for message in reference_session(
        game=user.game,
        track_id=user.track_id,
        car_model=user.car_model,
        lap_time_ms=user.lap_time_ms,
        samples=[sample.model_dump() for sample in user.samples],
    ):
        store.ingest(message)
    lap = next(item for item in store.laps(store.sessions()[0]["id"]) if item["valid"])
    benchmark = store.benchmark(lap["id"])
    assert benchmark["pro"]["available"] is True
    assert "pro file" in benchmark["pro"]["spoken_text"]
    assert "0.40" in benchmark["pro"]["spoken_text"]
    assert benchmark["grip"][0]["kind"] == "high_slip"


def test_history_reference_survives_a_new_session_and_pro_file_does_not_apply(tmp_path):
    store = Store(tmp_path)
    for message in synthetic_session():
        store.ingest(message)
    store._agents.clear()
    store._keys.clear()
    store._assemblers.clear()
    for message in synthetic_session():
        store.ingest(message)
    sessions = store.sessions()
    assert len(sessions) == 2
    latest = [lap for lap in store.laps(sessions[1]["id"]) if lap["valid"]][-1]
    benchmark = store.benchmark(latest["id"])
    assert benchmark["personal"]["available"] is True
    assert benchmark["personal"]["reference_lap_id"]
    assert benchmark["pro"]["reason"] == "no_pro_reference"
    assert benchmark["pro"]["recommendation_allowed"] is False
    assert benchmark["others"]["reason"] == "no_driver"


def test_drivers_keep_their_laps_and_compare_with_each_other(tmp_path):
    settings = Settings(data_dir=tmp_path, auth_token="test-token", ollama_host=None, ollama_model="", static_dir=None)
    app = create_app(settings, Store(tmp_path))
    client = TestClient(app)
    ava_client = TestClient(app)
    admin = {"Authorization": "Bearer test-token"}
    assert client.post("/api/v1/drivers", json={"display_name": "Ava", "password": "trackday-1"}).status_code == 401
    refused = client.post("/api/v1/login", json={"display_name": "Ava", "password": "wrong-password"})
    assert refused.status_code == 401
    assert refused.json()["detail"] == "The name or password is wrong"
    ava = client.post("/api/v1/drivers", headers=admin, json={"display_name": "Ava", "password": "trackday-1"})
    assert ava.status_code == 201
    assert "token" not in ava.json()
    bea = client.post("/api/v1/drivers", headers=admin, json={"display_name": "Bea", "password": "trackday-2"}).json()
    logged_in = ava_client.post("/api/v1/login", json={"display_name": "Ava", "password": "trackday-1"})
    assert logged_in.json()["display_name"] == "Ava"
    assert "token" not in ava_client.get("/api/v1/me").json()
    first_token = ava_client.post("/api/v1/agent-token").json()["token"]
    second_token = ava_client.post("/api/v1/agent-token").json()["token"]
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {first_token}"}).status_code == 401
    ava_headers = {"Authorization": f"Bearer {second_token}"}
    bea_client = TestClient(app)
    bea_client.post("/api/v1/login", json={"display_name": "Bea", "password": "trackday-2"})
    bea_headers = {"Authorization": f"Bearer {bea_client.post('/api/v1/agent-token').json()['token']}"}
    assert client.post("/api/v1/drivers", headers=ava_headers, json={"display_name": "Nope", "password": "trackday-3"}).status_code == 403
    listed = client.get("/api/v1/drivers", headers=admin).json()["drivers"]
    assert [item["display_name"] for item in listed] == ["Ava", "Bea"]
    assert client.get("/api/v1/me", headers=ava_headers).json()["role"] == "driver"

    body = "\n".join(item.model_dump_json() for item in synthetic_session())
    claimed = client.post("/api/v1/replay", headers=admin, json={"jsonl": body}).json()["session_id"]
    assert client.get(f"/api/v1/sessions/{claimed}", headers=bea_headers).status_code == 404
    claim = client.post(f"/api/v1/drivers/{ava.json()['id']}/claim-unassigned", headers=admin)
    assert claim.json()["sessions"] == 1
    assert client.get(f"/api/v1/sessions/{claimed}", headers=ava_headers).status_code == 200
    assert client.get(f"/api/v1/sessions/{claimed}", headers=bea_headers).status_code == 404

    catalog = ava_client.get("/api/v1/laps", params={"track_id": "synthetic-oval"}).json()["laps"]
    assert len([lap for lap in catalog if lap["valid"]]) == 2
    assert ava_client.get("/api/v1/laps", params={"track_id": "imola"}).json()["laps"] == []
    trend = ava_client.get("/api/v1/performance", params={"track_id": "synthetic-oval"}).json()["laps"]
    assert trend[0]["lap_time_s"] == 30.0
    assert trend[0]["improvement_s"] is None
    assert trend[1]["improvement_s"] == pytest.approx(-0.4, abs=0.05)

    bea_session = client.post("/api/v1/replay", headers=bea_headers, json={"jsonl": body}).json()["session_id"]
    laps = client.get(f"/api/v1/sessions/{bea_session}/laps", headers=bea_headers).json()["laps"]
    slower = [lap for lap in laps if lap["valid"]][-1]
    benchmark = client.get(f"/api/v1/laps/{slower['id']}/benchmark", headers=bea_headers).json()
    assert benchmark["personal"]["available"] is True
    assert benchmark["others"]["driver_name"] == "Ava"
    assert benchmark["others"]["time_loss_s"] == pytest.approx(0.4, abs=0.05)
    assert benchmark["others"]["tips"][0]["spoken_text"].startswith("Against Ava:")
    assert benchmark["pro"]["reason"] == "no_pro_reference"
    assert client.get(f"/api/v1/laps/{slower['id']}/benchmark", headers=ava_headers).status_code == 404

    assert ava_client.post("/api/v1/logout").json()["ok"] is True
    assert ava_client.get("/api/v1/me").status_code == 401
    assert client.post(f"/api/v1/drivers/{ava.json()['id']}/revoke", headers=admin).json()["revoked"] is True
    assert client.get("/api/v1/me", headers=ava_headers).status_code == 401


def test_admin_assigns_one_lap_and_deletes_the_driver(tmp_path):
    settings = Settings(data_dir=tmp_path, auth_token="test-token", ollama_host=None, ollama_model="", static_dir=None)
    app = create_app(settings, Store(tmp_path))
    client = TestClient(app)
    admin = {"Authorization": "Bearer test-token"}
    ava = client.post("/api/v1/drivers", headers=admin, json={"display_name": "Ava", "password": "trackday-1"}).json()
    bea = client.post("/api/v1/drivers", headers=admin, json={"display_name": "Bea", "password": "trackday-2"}).json()
    body = "\n".join(item.model_dump_json() for item in synthetic_session())
    client.post("/api/v1/replay", headers=admin, json={"jsonl": body})
    valid = [lap for lap in client.get("/api/v1/laps", headers=admin).json()["laps"] if lap["valid"]]
    assert valid[0]["driver_name"] is None

    assigned = client.post(f"/api/v1/laps/{valid[0]['id']}/assign", headers=admin, json={"driver_id": ava["id"]})
    assert assigned.json()["driver_id"] == ava["id"]
    assert client.post(f"/api/v1/laps/{valid[1]['id']}/assign", headers=admin, json={"driver_id": bea["id"]}).status_code == 200
    assert client.post("/api/v1/laps/missing/assign", headers=admin, json={"driver_id": ava["id"]}).status_code == 404

    ava_client = TestClient(app)
    ava_client.post("/api/v1/login", json={"display_name": "Ava", "password": "trackday-1"})
    assert [lap["id"] for lap in ava_client.get("/api/v1/laps").json()["laps"]] == [valid[0]["id"]]
    assert ava_client.get(f"/api/v1/laps/{valid[1]['id']}/benchmark").status_code == 404
    assert ava_client.get(f"/api/v1/laps/{valid[0]['id']}/benchmark").status_code == 200
    assert len(ava_client.get("/api/v1/performance", params={"track_id": "synthetic-oval"}).json()["laps"]) == 1
    assert ava_client.delete(f"/api/v1/drivers/{bea['id']}").status_code == 403

    assert client.post(f"/api/v1/laps/{valid[0]['id']}/assign", headers=admin, json={"driver_id": None}).json()["driver_id"] is None
    cleared = {lap["id"]: lap for lap in client.get("/api/v1/laps", headers=admin).json()["laps"]}
    assert cleared[valid[0]["id"]]["driver_name"] is None
    client.post(f"/api/v1/laps/{valid[0]['id']}/assign", headers=admin, json={"driver_id": ava["id"]})

    assert client.delete(f"/api/v1/drivers/{ava['id']}", headers=admin).json()["deleted"] is True
    assert ava_client.get("/api/v1/me").status_code == 401
    remaining = {lap["id"]: lap for lap in client.get("/api/v1/laps", headers=admin).json()["laps"]}
    assert remaining[valid[0]["id"]]["driver_name"] is None
    assert remaining[valid[1]["id"]]["driver_name"] == "Bea"
    assert client.post("/api/v1/drivers", headers=admin, json={"display_name": "Ava", "password": "trackday-9"}).status_code == 201

    password = (tmp_path / "admin.password").read_text(encoding="utf-8").strip()
    desk = TestClient(app)
    desk.post("/api/v1/login", json={"display_name": "administrator", "password": password})
    administrator_id = desk.get("/api/v1/me").json()["driver_id"]
    assert client.delete(f"/api/v1/drivers/{administrator_id}", headers=admin).status_code == 404
