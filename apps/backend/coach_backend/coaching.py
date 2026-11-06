"""Evidence-backed coaching. Uncertainty is reported; it is not spoken as advice."""

from __future__ import annotations

from dataclasses import dataclass

from coach_backend.analysis import CornerMetrics, corner_metrics, delta_curve, series_from_rows, time_impact


@dataclass(frozen=True)
class Observation:
    rule_id: str
    corner_id: str | None
    advice: str
    recommendation_allowed: bool
    confidence: float
    severity: str
    priority: int
    evidence: dict
    reference: dict
    time_impact_s: float | None
    dedup_key: str
    spoken_text: str
    uncertainty: str | None

    def public(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "corner_id": self.corner_id,
            "advice": self.advice,
            "recommendation_allowed": self.recommendation_allowed,
            "confidence": self.confidence,
            "severity": self.severity,
            "priority": self.priority,
            "evidence": self.evidence,
            "reference": self.reference,
            "time_impact_s": self.time_impact_s,
            "dedup_key": self.dedup_key,
            "spoken_text": self.spoken_text,
            "uncertainty": self.uncertainty,
        }


@dataclass(frozen=True)
class Comparability:
    ok: bool
    reasons: tuple[str, ...]


def comparability(current: CornerMetrics, reference: CornerMetrics, *, same_setup: bool) -> Comparability:
    reasons: list[str] = []
    if not same_setup:
        reasons.append("different_car_or_track")
    if current.entry_speed_mps is None or reference.entry_speed_mps is None or reference.entry_speed_mps <= 1:
        reasons.append("missing_entry_speed")
    elif abs(current.entry_speed_mps - reference.entry_speed_mps) / reference.entry_speed_mps > 0.03:
        reasons.append("entry_speed")
    return Comparability(ok=not reasons, reasons=tuple(reasons))


def _round(value: float | None, digits: int = 3) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def evaluate_corner(
    current: CornerMetrics,
    reference: CornerMetrics,
    *,
    same_setup: bool,
    time_impact_s: float | None,
) -> list[Observation]:
    state = comparability(current, reference, same_setup=same_setup)
    events: list[Observation] = []
    brake = _brake_point(current, reference, state, time_impact_s)
    if brake is not None:
        events.append(brake)
    if not state.ok:
        return events
    for builder in (_excess_brake, _coasting, _late_throttle, _exit_speed):
        event = builder(current, reference, time_impact_s)
        if event is not None:
            events.append(event)
    return events


def _brake_point(current, reference, state: Comparability, time_impact_s: float | None) -> Observation | None:
    if current.braking_onset is None or reference.braking_onset is None:
        return None
    delta = current.braking_onset - reference.braking_onset
    shown_impact = _round(time_impact_s, 2)
    evidence = {
        "braking_onset": _round(current.braking_onset),
        "entry_speed_mps": _round(current.entry_speed_mps, 2),
        "time_impact_s": shown_impact,
    }
    reference_values = {
        "braking_onset": _round(reference.braking_onset),
        "entry_speed_mps": _round(reference.entry_speed_mps, 2),
    }
    if not state.ok:
        reason = ", ".join(state.reasons)
        return _event(
            rule_id="brake_point",
            corner=current,
            advice="none",
            allowed=False,
            confidence=0.4,
            evidence=evidence,
            reference_values=reference_values,
            time_impact_s=shown_impact,
            uncertainty=reason,
            spoken=(
                f"Braking onset in {current.name} is {evidence['braking_onset']} versus the reference "
                f"{reference_values['braking_onset']}. The laps are not comparable ({reason})."
            ),
        )
    if delta < -0.004 and shown_impact is not None and shown_impact > 0:
        return _event(
            rule_id="brake_point",
            corner=current,
            advice="reference_braked_later",
            allowed=True,
            confidence=0.8,
            evidence=evidence,
            reference_values=reference_values,
            time_impact_s=shown_impact,
            uncertainty=None,
            spoken=(
                f"You braked earlier than the reference in {current.name} and lost {shown_impact:.2f} s. "
                f"Entry speed matches. The reference onset was {reference_values['braking_onset']}."
            ),
        )
    if delta > 0.004:
        return _event(
            rule_id="brake_point",
            corner=current,
            advice="braked_later_than_reference",
            allowed=False,
            confidence=0.7,
            evidence=evidence,
            reference_values=reference_values,
            time_impact_s=shown_impact,
            uncertainty="later braking is not a recommendation",
            spoken=(
                f"You braked later than the reference in {current.name}. "
                "That measurement is not a reason to brake any later."
            ),
        )
    return None


def _excess_brake(current, reference, time_impact_s) -> Observation | None:
    if None in (current.peak_brake, reference.peak_brake, current.min_speed_mps, reference.min_speed_mps):
        return None
    if current.peak_brake <= reference.peak_brake + 0.15:
        return None
    if current.min_speed_mps >= reference.min_speed_mps - 0.5:
        return None
    return _event(
        rule_id="excess_brake",
        corner=current,
        advice="peak_brake_higher",
        allowed=True,
        confidence=0.7,
        evidence={"peak_brake": _round(current.peak_brake, 2), "min_speed_mps": _round(current.min_speed_mps, 2)},
        reference_values={"peak_brake": _round(reference.peak_brake, 2), "min_speed_mps": _round(reference.min_speed_mps, 2)},
        time_impact_s=_round(time_impact_s, 2),
        uncertainty=None,
        spoken=(
            f"Peak brake in {current.name} is {_round(current.peak_brake, 2)} against the reference "
            f"{_round(reference.peak_brake, 2)}, and minimum speed is lower."
        ),
    )


def _coasting(current, reference, time_impact_s) -> Observation | None:
    if current.coast_s is None or reference.coast_s is None:
        return None
    if current.coast_s <= reference.coast_s + 0.15:
        return None
    gap = round(current.coast_s - reference.coast_s, 2)
    return _event(
        rule_id="coasting",
        corner=current,
        advice="coast_longer_than_reference",
        allowed=True,
        confidence=0.7,
        evidence={"coast_s": round(current.coast_s, 2), "extra_coast_s": gap},
        reference_values={"coast_s": round(reference.coast_s, 2)},
        time_impact_s=_round(time_impact_s, 2),
        uncertainty=None,
        spoken=f"Coasting in {current.name} is {gap:.2f} s longer than the reference.",
    )


def _late_throttle(current, reference, time_impact_s) -> Observation | None:
    if current.throttle_onset is None or reference.throttle_onset is None:
        return None
    if current.throttle_onset <= reference.throttle_onset + 0.004:
        return None
    return _event(
        rule_id="late_throttle",
        corner=current,
        advice="throttle_later_than_reference",
        allowed=True,
        confidence=0.75,
        evidence={"throttle_onset": _round(current.throttle_onset)},
        reference_values={"throttle_onset": _round(reference.throttle_onset)},
        time_impact_s=_round(time_impact_s, 2),
        uncertainty=None,
        spoken=(
            f"Throttle in {current.name} starts at {_round(current.throttle_onset)} versus the reference "
            f"{_round(reference.throttle_onset)}."
        ),
    )


def _exit_speed(current, reference, time_impact_s) -> Observation | None:
    if current.exit_speed_mps is None or reference.exit_speed_mps is None:
        return None
    if current.exit_speed_mps >= reference.exit_speed_mps - 0.5:
        return None
    return _event(
        rule_id="exit_speed",
        corner=current,
        advice="exit_speed_lower",
        allowed=True,
        confidence=0.8,
        evidence={"exit_speed_mps": _round(current.exit_speed_mps, 2)},
        reference_values={"exit_speed_mps": _round(reference.exit_speed_mps, 2)},
        time_impact_s=_round(time_impact_s, 2),
        uncertainty=None,
        spoken=(
            f"Exit speed in {current.name} is {_round(current.exit_speed_mps, 2)} m/s versus the reference "
            f"{_round(reference.exit_speed_mps, 2)} m/s."
        ),
    )


def _event(**kwargs) -> Observation:
    corner = kwargs["corner"]
    impact = kwargs["time_impact_s"]
    priority = 10
    if impact is not None:
        priority += int(abs(impact) * 100)
    severity = "caution" if impact is not None and impact >= 0.1 else "info"
    return Observation(
        rule_id=kwargs["rule_id"],
        corner_id=corner.corner_id,
        advice=kwargs["advice"],
        recommendation_allowed=kwargs["allowed"],
        confidence=kwargs["confidence"],
        severity=severity,
        priority=priority,
        evidence=kwargs["evidence"],
        reference=kwargs["reference_values"],
        time_impact_s=impact,
        dedup_key=f"{kwargs['rule_id']}:{corner.corner_id}",
        spoken_text=kwargs["spoken"],
        uncertainty=kwargs["uncertainty"],
    )


class Scheduler:
    """Hold advice until the car is on throttle and outside a calibrated corner."""

    def __init__(self, cooldown_s: float = 20) -> None:
        self.cooldown_s = cooldown_s
        self._queue: dict[str, Observation] = {}
        self._spoken_at: dict[str, float] = {}

    def push(self, event: Observation) -> None:
        self._queue[event.dedup_key] = event

    def poll(self, *, brake: float, throttle: float, progress: float, now: float, corners: list) -> Observation | None:
        if brake >= 0.15 or throttle < 0.5:
            return None
        if any(corner.entry <= progress <= corner.exit for corner in corners):
            return None
        ready = [
            event
            for key, event in self._queue.items()
            if event.recommendation_allowed and now - self._spoken_at.get(key, -1_000_000) >= self.cooldown_s
        ]
        if not ready:
            return None
        ready.sort(key=lambda event: event.priority, reverse=True)
        chosen = ready[0]
        self._spoken_at[chosen.dedup_key] = now
        self._queue.pop(chosen.dedup_key, None)
        return chosen


def build_report(current_rows: list[dict], reference_rows: list[dict], track, *, same_setup: bool = True) -> dict:
    current = series_from_rows(current_rows)
    reference = series_from_rows(reference_rows)
    if current is None or reference is None:
        return {"delta": [], "corners": [], "events": [], "time_loss_s": None}
    delta = delta_curve(current, reference)
    finite = [point["delta_s"] for point in delta if point["delta_s"] is not None]
    loss = finite[-1] if finite else None
    corners = []
    events: list[Observation] = []
    if track is not None:
        for corner in track.corners:
            impact = time_impact(current, reference, corner.entry, corner.exit)
            current_metrics = corner_metrics(current, corner)
            reference_metrics = corner_metrics(reference, corner)
            state = comparability(current_metrics, reference_metrics, same_setup=same_setup)
            corners.append(
                {
                    "corner_id": corner.id,
                    "name": corner.name,
                    "time_impact_s": None if impact is None else round(impact, 3),
                    "comparability": {"ok": state.ok, "reasons": list(state.reasons)},
                    "current": _metrics(current_metrics),
                    "reference": _metrics(reference_metrics),
                }
            )
            events.extend(
                evaluate_corner(
                    current_metrics,
                    reference_metrics,
                    same_setup=same_setup,
                    time_impact_s=impact,
                )
            )
    return {"delta": delta, "corners": corners, "events": events, "time_loss_s": None if loss is None else round(loss, 3)}


def _metrics(metrics) -> dict:
    return {
        "braking_onset": _round(metrics.braking_onset),
        "peak_brake": _round(metrics.peak_brake, 2),
        "min_speed_mps": _round(metrics.min_speed_mps, 2),
        "throttle_onset": _round(metrics.throttle_onset),
        "full_throttle": _round(metrics.full_throttle),
        "entry_speed_mps": _round(metrics.entry_speed_mps, 2),
        "exit_speed_mps": _round(metrics.exit_speed_mps, 2),
        "corner_time_s": _round(metrics.corner_time_s, 3),
        "coast_s": _round(metrics.coast_s, 3),
    }
