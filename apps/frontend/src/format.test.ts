import { describe, expect, test } from "vitest";
import { kmh, lapTime, pedalWidth, signedSeconds } from "./format";

describe("kmh", () => {
  test("converts metres per second to a whole number of kilometres per hour", () => {
    expect(kmh(10)).toBe("36");
  });

  test("shows a dash when the speed is missing", () => {
    expect(kmh(null)).toBe("—");
    expect(kmh(undefined)).toBe("—");
    expect(kmh(Number.NaN)).toBe("—");
  });
});

describe("lapTime", () => {
  test("pads seconds and milliseconds", () => {
    expect(lapTime(0)).toBe("0.000");
    expect(lapTime(59999)).toBe("59.999");
    expect(lapTime(61500)).toBe("1:01.500");
  });

  test("shows a dash when the time is missing or negative", () => {
    expect(lapTime(null)).toBe("—");
    expect(lapTime(undefined)).toBe("—");
    expect(lapTime(-1)).toBe("—");
  });
});

describe("signedSeconds", () => {
  test("keeps a leading plus on a loss and a minus on a gain", () => {
    expect(signedSeconds(1.2)).toBe("+1.200");
    expect(signedSeconds(-0.5)).toBe("-0.500");
    expect(signedSeconds(0)).toBe("0.000");
  });

  test("shows a dash when the delta is missing", () => {
    expect(signedSeconds(null)).toBe("—");
    expect(signedSeconds(undefined)).toBe("—");
    expect(signedSeconds(Number.NaN)).toBe("—");
  });
});

describe("pedalWidth", () => {
  test("clamps the pedal to a percentage width", () => {
    expect(pedalWidth(0.333)).toBe("33%");
    expect(pedalWidth(1.5)).toBe("100%");
    expect(pedalWidth(-0.2)).toBe("0%");
    expect(pedalWidth(undefined)).toBe("0%");
  });
});
