import React, {useEffect, useState} from "react";
import {Link, useNavigate, useParams} from "react-router-dom";
import {api, clearAuth} from "./api";
import logo from "./assets/cmu-elect-logo.png";

function MetricCard({label, value, detail}) {
  return <div className="analytics-metric-card">
    <span>{label}</span>
    <strong>{value}</strong>
    {detail && <small>{detail}</small>}
  </div>;
}

function TurnoutVisual({participants, eligible, percentage}) {
  const safePercentage = Math.max(0, Math.min(100, Number(percentage) || 0));
  return <div className="turnout-layout">
    <div className="turnout-ring" style={{background: `conic-gradient(#3348c4 ${safePercentage}%, #e9edf5 0)`}} aria-label={`Turnout ${safePercentage}%`}>
      <div className="turnout-ring-center">
        <strong>{safePercentage.toFixed(2)}%</strong>
        <span>Turnout</span>
      </div>
    </div>
    <div className="turnout-details">
      <div><span>Participants</span><strong>{participants}</strong></div>
      <div><span>Eligible voters</span><strong>{eligible}</strong></div>
      <p>Aggregate participation only. Candidate vote standings are not displayed during the election.</p>
    </div>
  </div>;
}

export default function VoterAnalytics() {
  const {electionId} = useParams();
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);

  useEffect(() => {
    let cancelled = false;
    let timer;
    async function load() {
      try {
        const next = await api(`/elections/${electionId}/analytics/`);
        if (cancelled) return;
        setData(next);
        setError("");
        setLastUpdated(new Date(next.updated_at));
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) timer = window.setTimeout(load, 2000);
      }
    }
    load();
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [electionId]);

  async function logout() {
    try { await api("/auth/logout/", {method: "POST"}); } catch (_) {}
    clearAuth();
    nav("/login");
  }

  const metrics = data?.metrics;
  const election = data?.election;

  return <>
    <header className="topbar">
      <div className="topbar-brand"><img src={logo} alt="CMU-ELECT Logo" /><span>CMU-ELECT</span></div>
      <nav className="main-nav">
        <span className="user-chip">{user.email}</span>
        <Link to="/dashboard">Home</Link>
        <button onClick={logout}>Logout</button>
      </nav>
    </header>
    <main className="dashboard analytics-page">
      <div className="admin-page-heading">
        <div>
          <h1>Real-Time Election Analytics</h1>
          <p>Live aggregate election activity without candidate standings.</p>
        </div>
        {data && <div className="analytics-live-status"><span className="live-dot" /> Live · updates every 2 seconds{lastUpdated && <small>Last update: {lastUpdated.toLocaleTimeString()}</small>}</div>}
      </div>

      <div className="modal-actions analytics-back-actions">
        <Link className="secondary" to="/dashboard">Back to Dashboard</Link>
        {election?.status === "ended" && <Link className="primary" to={`/results/${electionId}`}>Official Results</Link>}
      </div>

      {error && <div className="error">{error}</div>}
      {!data && !error && <div className="center">Loading analytics...</div>}

      {data && metrics && election && <>
        <section className="election-card analytics-election-summary">
          <h2>{election.name}</h2>
          <p>This dashboard provides aggregate participation information. Live candidate vote counts, percentages, rankings, and standings are not displayed.</p>
        </section>

        <div className="analytics-metrics-grid">
          <MetricCard label="Eligible voters" value={metrics.total_eligible_voters} detail={election.eligible_voter_category} />
          <MetricCard label="Participants" value={metrics.participants} detail="Unique voters who voted" />
          <MetricCard label="Turnout" value={`${Number(metrics.turnout_percentage).toFixed(2)}%`} detail="Participants ÷ eligible voters" />
          <MetricCard label="Positions" value={metrics.position_count} detail="Configured election positions" />
        </div>

        <div className="analytics-grid-two">
          <section className="analytics-panel">
            <div className="analytics-panel-heading"><div><h2>Turnout</h2><p>Current voter participation</p></div></div>
            <TurnoutVisual participants={metrics.participants} eligible={metrics.total_eligible_voters} percentage={metrics.turnout_percentage} />
          </section>

          <section className="analytics-panel">
            <div className="analytics-panel-heading"><div><h2>Election Statistics</h2><p>Current configuration and aggregate activity</p></div></div>
            <div className="analytics-stat-list">
              <div><span>Status</span><strong className={`status-badge ${election.status}`}>{election.status}</strong></div>
              <div><span>Schedule</span><strong>{election.schedule_status.replace("_", " ")}</strong></div>
              <div><span>Eligible category</span><strong>{election.eligible_voter_category}</strong></div>
              <div><span>Positions</span><strong>{metrics.position_count}</strong></div>
              <div><span>Candidates</span><strong>{metrics.candidate_count}</strong></div>
            </div>
          </section>
        </div>
      </>}
    </main>
  </>;
}
