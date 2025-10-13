import { act, fireEvent, render, screen, within } from "@testing-library/react";
import MetricsGrid from "./MetricsGrid";
import useDashboardStore, { MetricRow } from "../state/useDashboardStore";

describe("MetricsGrid", () => {
  const initialState = useDashboardStore.getState();

  beforeEach(() => {
    useDashboardStore.setState(initialState, true);
  });

  it("renders sorted rows and allows selecting a parish", () => {
    const sampleRows: MetricRow[] = [
      {
        date: "2024-10-01",
        platform: "Meta",
        campaign: "Fall Outreach",
        parish: "Baton Rouge",
        impressions: 200,
        clicks: 20,
        spend: 50,
        conversions: 5,
        roas: 4,
      },
      {
        date: "2024-10-02",
        platform: "Google",
        campaign: "Search Push",
        parish: "Metairie",
        impressions: 150,
        clicks: 25,
        spend: 60,
        conversions: 6,
        roas: 3,
      },
      {
        date: "2024-10-03",
        platform: "LinkedIn",
        campaign: "Professional Outreach",
        parish: "Shreveport",
        impressions: 50,
        clicks: 5,
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

    const renderedRows = screen.getAllByRole("row");
    expect(renderedRows).toHaveLength(sampleRows.length + 1);

    const firstDataRow = renderedRows[1];
    const cells = within(firstDataRow).getAllByRole("cell");
    expect(cells[3]).toHaveTextContent("Baton Rouge");

    sampleRows.forEach(({ parish }) => {
      expect(screen.getByText(parish)).toBeInTheDocument();
    });

    const metairieRow = screen.getByText("Metairie").closest("tr");
    expect(metairieRow).not.toBeNull();

    if (metairieRow) {
      fireEvent.click(metairieRow);
    }

    expect(useDashboardStore.getState().selectedParish).toBe("Metairie");
  });
});
