import { describe, it, expect, vi, afterEach } from "vitest";
import { timeAgo } from "../services/format";

describe("timeAgo", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns 'Just now' for recent timestamps", () => {
    const now = new Date();
    expect(timeAgo(now.toISOString())).toBe("Just now");
  });

  it("returns minutes ago", () => {
    vi.useFakeTimers();
    const now = new Date("2026-03-22T12:00:00Z");
    vi.setSystemTime(now);

    const fiveMinAgo = new Date("2026-03-22T11:55:00Z");
    expect(timeAgo(fiveMinAgo.toISOString())).toBe("5 minutes ago");

    const oneMinAgo = new Date("2026-03-22T11:59:00Z");
    expect(timeAgo(oneMinAgo.toISOString())).toBe("1 minute ago");
  });

  it("returns hours ago", () => {
    vi.useFakeTimers();
    const now = new Date("2026-03-22T12:00:00Z");
    vi.setSystemTime(now);

    const threeHoursAgo = new Date("2026-03-22T09:00:00Z");
    expect(timeAgo(threeHoursAgo.toISOString())).toBe("3 hours ago");

    const oneHourAgo = new Date("2026-03-22T11:00:00Z");
    expect(timeAgo(oneHourAgo.toISOString())).toBe("1 hour ago");
  });

  it("returns days ago", () => {
    vi.useFakeTimers();
    const now = new Date("2026-03-22T12:00:00Z");
    vi.setSystemTime(now);

    const twoDaysAgo = new Date("2026-03-20T12:00:00Z");
    expect(timeAgo(twoDaysAgo.toISOString())).toBe("2 days ago");
  });

  it("returns formatted date for older timestamps", () => {
    vi.useFakeTimers();
    const now = new Date("2026-03-22T12:00:00Z");
    vi.setSystemTime(now);

    const twoWeeksAgo = new Date("2026-03-08T12:00:00Z");
    const result = timeAgo(twoWeeksAgo.toISOString());
    expect(result).not.toContain("ago");
  });
});
