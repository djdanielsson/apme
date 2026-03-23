import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "../components/StatusBadge";

describe("StatusBadge", () => {
  it("shows ISSUES when violations > 0 for scan type", () => {
    render(<StatusBadge violations={5} scanType="scan" />);
    expect(screen.getByText(/5 ISSUES/)).toBeInTheDocument();
  });

  it("shows ISSUES when violations > 0 for fix type", () => {
    render(<StatusBadge violations={3} scanType="fix" />);
    expect(screen.getByText(/3 ISSUES/)).toBeInTheDocument();
  });

  it("shows FIXED when violations = 0 and type is fix", () => {
    render(<StatusBadge violations={0} scanType="fix" />);
    expect(screen.getByText(/FIXED/)).toBeInTheDocument();
  });

  it("shows CLEAN when violations = 0 and type is scan", () => {
    render(<StatusBadge violations={0} scanType="scan" />);
    expect(screen.getByText(/CLEAN/)).toBeInTheDocument();
  });

  it("applies failed class when violations > 0", () => {
    const { container } = render(<StatusBadge violations={1} scanType="scan" />);
    expect(container.querySelector(".apme-badge.failed")).not.toBeNull();
  });

  it("applies passed class when violations = 0", () => {
    const { container } = render(<StatusBadge violations={0} scanType="scan" />);
    expect(container.querySelector(".apme-badge.passed")).not.toBeNull();
  });
});
