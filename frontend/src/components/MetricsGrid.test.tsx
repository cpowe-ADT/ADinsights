import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import MetricsGrid from "./MetricsGrid";
import useDashboardStore, { MetricRow } from "../state/useDashboardStore";

describe("MetricsGrid", () => {
  const initialState = useDashboardStore.getState();

  beforeEach(() => {
    useDashboardStore.setState(initialState, true);
  });

  it("sorts rows by the selected metric and allows selecting a parish", () => {
    const sampleRows: MetricRow[] = [
      {
        date: "2024-10-01",
        platform: "Meta",
        campaign: "Fall Outreach",
        parish: "Baton Rouge",
        impressions: 200,
        clicks: 40,
        spend: 50,
        conversions: 5,
        roas: 4,
      },
      {
        date: "2024-10-02",
        platform: "Google",
        campaign: "Search Push",
        parish: "Metairie",
        impressions: 350,
        clicks: 20,
        spend: 60,
        conversions: 6,
        roas: 3,
      },
      {
        date: "2024-10-03",
        platform: "LinkedIn",
        campaign: "Professional Outreach",
        parish: "Shreveport",
        impressions: 100,
        clicks: 60,
        spend: 20,
        conversions: 2,
        roas: 2,
      },
    ];

    act(() => {
      useDashboardStore.setState({
        rows: sampleRows,
        selectedMetric: "impressions",
        selectedParish: undefined,
        status: "loaded",
        error: undefined,
      });
    });

    render(<MetricsGrid />);

    const sortBanner = screen.getByText(/Sorted by/i);
    expect(sortBanner).toHaveTextContent("Sorted by Impressions.");

    const renderedRows = screen.getAllByRole("row");
    expect(renderedRows).toHaveLength(sampleRows.length + 1);

    const dataRows = renderedRows.slice(1);
    const parishesInOrder = dataRows.map((row) => within(row).getAllByRole("cell")[3].textContent);
    expect(parishesInOrder).toEqual(["Metairie", "Baton Rouge", "Shreveport"]);

    sampleRows.forEach(({ parish }) => {
      expect(screen.getByText(parish)).toBeInTheDocument();
    });

    const parishSortButton = screen.getByRole("button", { name: /sort by parish/i });
    fireEvent.click(parishSortButton);

    expect(sortBanner).toHaveTextContent("Sorted by Parish.");

    const resortedParishes = screen
      .getAllByRole("row")
      .slice(1)
      .map((row) => within(row).getAllByRole("cell")[3].textContent);
    expect(resortedParishes).toEqual(["Baton Rouge", "Metairie", "Shreveport"]);

    const metairieRow = screen.getByText("Metairie").closest("tr");
    expect(metairieRow).not.toBeNull();

    if (metairieRow) {
      fireEvent.click(metairieRow);
    }

    expect(useDashboardStore.getState().selectedParish).toBe("Metairie");
  });

  it("updates the sort order when the selected metric changes", () => {
    const sampleRows: MetricRow[] = [
      {
        date: "2024-10-01",
        platform: "Meta",
        campaign: "Fall Outreach",
        parish: "Baton Rouge",
        impressions: 200,
        clicks: 40,
        spend: 50,
        conversions: 5,
        roas: 4,
      },
      {
        date: "2024-10-02",
        platform: "Google",
        campaign: "Search Push",
        parish: "Metairie",
        impressions: 350,
        clicks: 20,
        spend: 60,
        conversions: 6,
        roas: 3,
      },
      {
        date: "2024-10-03",
        platform: "LinkedIn",
        campaign: "Professional Outreach",
        parish: "Shreveport",
        impressions: 100,
        clicks: 60,
        spend: 20,
        conversions: 2,
        roas: 2,
      },
    ];

    act(() => {
      useDashboardStore.setState({
        rows: sampleRows,
        selectedMetric: "impressions",
        selectedParish: undefined,
        status: "loaded",
        error: undefined,
      });
    });

    render(<MetricsGrid />);

    let parishesInOrder = screen
      .getAllByRole("row")
      .slice(1)
      .map((row) => within(row).getAllByRole("cell")[3].textContent);
    expect(parishesInOrder).toEqual(["Metairie", "Baton Rouge", "Shreveport"]);

    act(() => {
      useDashboardStore.setState({ selectedMetric: "clicks" });
    });

    parishesInOrder = screen
      .getAllByRole("row")
      .slice(1)
      .map((row) => within(row).getAllByRole("cell")[3].textContent);
    expect(parishesInOrder).toEqual(["Shreveport", "Baton Rouge", "Metairie"]);
  });
});
