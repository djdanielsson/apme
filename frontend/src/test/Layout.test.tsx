import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Layout } from "../components/Layout";

function renderLayout(path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Layout>
        <div data-testid="child">Page Content</div>
      </Layout>
    </MemoryRouter>,
  );
}

describe("Layout", () => {
  it("renders sidebar with APME branding", () => {
    renderLayout();
    expect(screen.getByText("APME")).toBeInTheDocument();
  });

  it("renders all nav items", () => {
    renderLayout();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Scans")).toBeInTheDocument();
    expect(screen.getByText("Sessions")).toBeInTheDocument();
    expect(screen.getByText("Top Violations")).toBeInTheDocument();
    expect(screen.getByText("Fix Tracker")).toBeInTheDocument();
    expect(screen.getByText("AI Metrics")).toBeInTheDocument();
    expect(screen.getByText("Health")).toBeInTheDocument();
    expect(screen.getByText("New Scan")).toBeInTheDocument();
  });

  it("renders children content", () => {
    renderLayout();
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });

  it("renders theme toggle button", () => {
    renderLayout();
    expect(screen.getByLabelText("Toggle theme")).toBeInTheDocument();
  });

  it("highlights active nav item", () => {
    renderLayout("/scans");
    const scansLink = screen.getByText("Scans").closest("a");
    expect(scansLink?.className).toContain("active");
  });
});
