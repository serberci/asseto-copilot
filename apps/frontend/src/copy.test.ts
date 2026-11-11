import { describe, expect, test } from "vitest";
import {
  adviceLabel,
  changeLabel,
  coachingLabel,
  dashboardStatus,
  formatTimestamp,
  lapState,
  otherSummary,
  personalSummary,
} from "./copy";

describe("coaching labels", () => {
  test("calls a delivered line spoken, and otherwise ready or an observation", () => {
    expect(adviceLabel(true)).toBe("ready");
    expect(adviceLabel(false)).toBe("observation");
    expect(coachingLabel("2024-01-01T00:00:00Z", false)).toBe("spoken");
    expect(coachingLabel(null, true)).toBe("ready");
    expect(coachingLabel(null, false)).toBe("observation");
  });
});

describe("lapState", () => {
  test("joins the invalid reasons and falls back when the lap has none", () => {
    expect(lapState(true, ["cut"])).toBe("valid");
    expect(lapState(false, ["cut", "pit"])).toBe("cut, pit");
    expect(lapState(false, [])).toBe("invalid");
  });
});

describe("dashboardStatus", () => {
  test("uses the singular agent label and appends the open session", () => {
    expect(dashboardStatus(true, 1, null)).toBe("Dashboard connected · 1 agent");
    expect(dashboardStatus(false, 0, null)).toBe("Dashboard offline · 0 agents");
    expect(dashboardStatus(true, 2, { track_id: "spa", car_model: "mx5" })).toBe(
      "Dashboard connected · 2 agents · spa · mx5",
    );
  });
});

describe("changeLabel", () => {
  test("names the first lap, a gain, a loss, and a tie", () => {
    expect(changeLabel(null)).toBe("First valid lap");
    expect(changeLabel(0.5)).toBe("Faster by 0.500 s");
    expect(changeLabel(-0.25)).toBe("Slower by 0.250 s");
    expect(changeLabel(0)).toBe("Same time as the previous valid lap");
  });
});

describe("personalSummary", () => {
  test("says when no personal lap exists, and otherwise quotes the delta", () => {
    expect(personalSummary({ available: false, time_loss_s: null })).toBe(
      "No other lap of yours is available for this car and track.",
    );
    expect(personalSummary({ available: true, time_loss_s: null })).toBe("Compared with your other lap.");
    expect(personalSummary({ available: true, time_loss_s: 1.25 })).toBe(
      "Time versus your other lap: +1.250 s.",
    );
  });
});

describe("otherSummary", () => {
  test("explains a missing comparison, then names the other driver and the delta", () => {
    expect(otherSummary({ available: false, reason: "no_driver", driver_name: null, time_loss_s: null })).toBe(
      "These laps are not assigned to a driver.",
    );
    expect(otherSummary({ available: false, reason: "no_peer", driver_name: null, time_loss_s: null })).toBe(
      "No other driver has a valid lap in this car on this track.",
    );
    expect(otherSummary({ available: true, reason: null, driver_name: null, time_loss_s: null })).toBe(
      "Compared with another driver.",
    );
    expect(otherSummary({ available: true, reason: null, driver_name: "Ada", time_loss_s: -0.5 })).toBe(
      "Time versus Ada: -0.500 s.",
    );
  });
});

describe("formatTimestamp", () => {
  test("returns the original text when it is not a date", () => {
    expect(formatTimestamp("not-a-date")).toBe("not-a-date");
  });
});
