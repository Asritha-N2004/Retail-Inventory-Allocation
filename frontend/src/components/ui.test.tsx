import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Badge, Table, Metric } from "./ui";
describe("Operational components", () => {
  it("shows readable status and actual metric", () => {
    render(
      <>
        <Badge>waiting_for_approval</Badge>
        <Metric label="Available stock" value={1234} />
      </>,
    );
    expect(screen.getByText("waiting for approval")).toBeInTheDocument();
    expect(screen.getByText("1234")).toBeInTheDocument();
  });
  it("opens a stock position through row selection", () => {
    const click = vi.fn();
    render(
      <Table
        columns={[{ key: "sku", label: "SKU" }]}
        rows={[{ id: 1, sku: "RTL-0001" }]}
        onClick={click}
      />,
    );
    fireEvent.click(screen.getByText("RTL-0001"));
    expect(click).toHaveBeenCalledWith({ id: 1, sku: "RTL-0001" });
  });
  it("explains empty backend results", () => {
    render(<Table columns={[]} rows={[]} />);
    expect(screen.getByText(/No records yet/)).toBeInTheDocument();
  });
});
