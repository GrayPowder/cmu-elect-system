import React, {useCallback, useEffect, useState} from "react";
import {NavLink, useNavigate} from "react-router-dom";
import {api, clearAuth} from "./api";
import logo from "./assets/cmu-elect-logo.png";

function MetricCard({label, value, detail}) {
  return (
    <section className="analytics-metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
    </section>
  );
}

function TurnoutVisual({participants, eligible, percentage}) {
  const safePercentage = Math.max(0, Math.min(100, Number(percentage) || 0));
  return (
    <div className="turnout-layout">
      <div
        className="turnout-ring"
        style={{background: `conic-gradient(#3348c4 ${safePercentage}%, #e9edf5 0)`}}
        aria-label={`Turnout ${safePercentage}%`}
      >
        <div className="turnout-ring-center">
          <strong>{safePercentage.toFixed(2)}%</strong>
          <span>turnout</span>
        </div>
      </div>
      <div className="turnout-details">
        <div><span>Participants</span><strong>{participants}</strong></div>
        <div><span>Eligible voters</span><strong>{eligible}</strong></div>
        <p>Participation is counted once per voter. Candidate vote standings are not displayed during the election.</p>
      </div>
    </div>
  );
}

export default function AdminAnalytics() {
  const nav = useNavigate();
  const [elections, setElections] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);

  const loadElections = useCallback(async () => {
    const items = await api("/admin/elections/");
    setElections(items);
    setSelectedId(current => current || (items.length ? String(items[0].id) : ""));
  }, []);

  const loadAnalytics = useCallback(async (showLoading = false) => {
    if (!selectedId) return;
    if (showLoading) setLoading(true);
    try {
      const result = await api(`/admin/elections/${selectedId}/analytics/`);
      setData(result);
      setLastUpdated(new Date(result.updated_at));
      setError("");
    } catch (err) {
      setError(err.message);
      if (showLoading) setData(null);
    } finally {
      if (showLoading) setLoading(false);
    }
  }, [selectedId]);

  useEffect(() => {
    loadElections().catch(err => {
      setError(err.message);
      setLoading(false);
    });
  }, [loadElections]);

  useEffect(() => {
    if (!selectedId) {
      setLoading(false);
      return undefined;
    }

    loadAnalytics(true);
    const interval = window.setInterval(() => loadAnalytics(false), 2000);
    return () => window.clearInterval(interval);
  }, [selectedId, loadAnalytics]);

  async function logout() {
    try { await api("/auth/logout/", {method: "POST"}); } catch (_) {}
    clearAuth();
    nav("/admin/login", {replace: true});
  }

  const metrics = data?.metrics;
  const election = data?.election;

  return (
    <div>
      <header className="topbar">
        <div className="topbar-brand">
          <img src={logo} alt="CMU-ELECT Logo" />
          <span>CMU-ELECT ADMIN</span>
        </div>
        <nav className="main-nav">
          <NavLink to="/admin" end className={({isActive}) => `admin-nav-link${isActive ? " active" : ""}`}>Dashboard</NavLink>
          <NavLink to="/admin/users" className={({isActive}) => `admin-nav-link${isActive ? " active" : ""}`}>Voters</NavLink>
          <NavLink to="/admin/elections" className={({isActive}) => `admin-nav-link${isActive ? " active" : ""}`}>Elections</NavLink>
          <NavLink to="/admin/results" className={({isActive}) => `admin-nav-link${isActive ? " active" : ""}`}>Results</NavLink>
          <NavLink to="/admin/analytics" className={({isActive}) => `admin-nav-link${isActive ? " active" : ""}`}>Analytics</NavLink>
          <NavLink to="/admin/audit-logs" className={({isActive}) => `admin-nav-link${isActive ? " active" : ""}`}>Audit Logs</NavLink>
          <button onClick={logout}>Logout</button>
        </nav>
      </header>

      <main className="dashboard analytics-page">
        <div className="admin-page-heading">
          <div>
            <h1>Real-Time Data Analytics</h1>
            <p>Live aggregate election activity without candidate standings.</p>
          </div>
          {data && (
            <div className="analytics-live-status">
              <span className="live-dot" /> Live · updates every 2 seconds
              {lastUpdated && <small>Last update: {lastUpdated.toLocaleTimeString()}</small>}
            </div>
          )}
        </div>

        <section className="result-selector analytics-selector">
          <label htmlFor="analytics-election">Select election</label>
          <select
            id="analytics-election"
            className="standalone-input"
            value={selectedId}
            onChange={e => setSelectedId(e.target.value)}
          >
            {elections.map(item => (
              <option key={item.id} value={item.id}>{item.name} — {item.status}</option>
            ))}
          </select>
        </section>

        {error && <div className="error">{error}</div>}
        {loading && <div className="center"><span className="spinner" /> Loading analytics...</div>}
        {!loading && !data && !error && <div className="message">No elections are available yet.</div>}

        {data && metrics && election && (
          <>
            <div className="analytics-metrics-grid">
              <MetricCard label="Eligible voters" value={metrics.total_eligible_voters} detail={election.eligible_voter_category} />
              <MetricCard label="Participants" value={metrics.participants} detail="Unique voters who voted" />
              <MetricCard label="Turnout" value={`${Number(metrics.turnout_percentage).toFixed(2)}%`} detail="Participants ÷ eligible voters" />
              <MetricCard label="Positions" value={metrics.position_count} detail="Configured election positions" />
            </div>

            <div className="analytics-grid-two">
              <section className="analytics-panel">
                <div className="analytics-panel-heading">
                  <div><h2>Turnout</h2><p>Current voter participation</p></div>
                </div>
                <TurnoutVisual
                  participants={metrics.participants}
                  eligible={metrics.total_eligible_voters}
                  percentage={metrics.turnout_percentage}
                />
              </section>

              <section className="analytics-panel">
                <div className="analytics-panel-heading">
                  <div><h2>Election Statistics</h2><p>Current configuration and activity</p></div>
                </div>
                <div className="analytics-stat-list">
                  <div><span>Status</span><strong className={`status-badge ${election.status}`}>{election.status}</strong></div>
                  <div><span>Schedule</span><strong>{election.schedule_status.replace("_", " ")}</strong></div>
                  <div><span>Eligible category</span><strong>{election.eligible_voter_category}</strong></div>
                  <div><span>Positions</span><strong>{metrics.position_count}</strong></div>
                  <div><span>Candidates</span><strong>{metrics.candidate_count}</strong></div>
                  <div><span>Total vote entries</span><strong>{metrics.total_votes}</strong></div>
                </div>
              </section>
            </div>


          </>
        )}
      </main>
    </div>
  );
}
