import ParishMap from "../components/ParishMap";

const ParishMapDetail = () => {
  return (
    <div className="dashboard-grid single-panel">
      <section className="panel full-width">
        <header className="panel-header">
          <h2>Parish heatmap</h2>
          <p className="muted">Explore the choropleth in a focused, full-width view.</p>
        </header>
        <ParishMap height={520} />
      </section>
    </div>
  );
};

export default ParishMapDetail;
