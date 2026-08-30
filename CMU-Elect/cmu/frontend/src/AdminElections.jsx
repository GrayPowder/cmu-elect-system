import React, {useEffect, useState} from "react";
import {Link, NavLink, useNavigate} from "react-router-dom";
import {api, clearAuth, mediaUrl} from "./api";
import logo from "./assets/cmu-elect-logo.png";

const CATEGORIES = [
  ["student", "Student"],
  ["alumni", "Alumni"],
  ["faculty", "Faculty"],
];

function toLocalInputValue(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const pad = number => String(number).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function toApiDateTime(value) {
  if (!value) return "";
  return new Date(value).toISOString();
}

function displayDate(value) {
  return value ? new Date(value).toLocaleString() : "—";
}

function AdminHeader() {
  const nav = useNavigate();

  async function logout() {
    try { await api("/auth/logout/", {method: "POST"}); } catch (_) {}
    clearAuth();
    nav("/admin/login", {replace: true});
  }

  return <header className="topbar">
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
  </header>;
}

function ElectionForm({election, onClose, onSaved}) {
  const [form, setForm] = useState({
    name: election?.name || "",
    description: election?.description || "",
    start_datetime: toLocalInputValue(election?.start_datetime),
    end_datetime: toLocalInputValue(election?.end_datetime),
    eligible_voter_category: election?.eligible_voter_category || "student",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function update(field, value) {
    setForm(current => ({...current, [field]: value}));
  }

  async function submit(event) {
    event.preventDefault();
    setError("");
    if (!form.name.trim()) {
      setError("Election name cannot be empty or contain only spaces.");
      return;
    }
    if (new Date(form.start_datetime) >= new Date(form.end_datetime)) {
      setError("End date/time must be after the start date/time.");
      return;
    }
    setLoading(true);
    try {
      const payload = {
        name: form.name.trim(),
        description: form.description.trim(),
        start_datetime: toApiDateTime(form.start_datetime),
        end_datetime: toApiDateTime(form.end_datetime),
        eligible_voter_category: form.eligible_voter_category,
      };
      if (election) {
        await api(`/admin/elections/${election.id}/`, {method: "PATCH", body: JSON.stringify(payload)});
      } else {
        await api("/admin/elections/", {method: "POST", body: JSON.stringify(payload)});
      }
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return <div className="modal-backdrop" onMouseDown={event => event.target === event.currentTarget && onClose()}>
    <section className="admin-modal">
      <div className="modal-header">
        <div><h2>{election ? "Edit Election" : "Create Election"}</h2><p>Election schedule controls when voting is allowed.</p></div>
        <button className="modal-close" type="button" onClick={onClose}>×</button>
      </div>
      <form onSubmit={submit}>
        <label>Election name</label>
        <input className="standalone-input" value={form.name} onChange={e => update("name", e.target.value)} required maxLength={120} />
        <label>Description</label>
        <textarea className="standalone-input" value={form.description} onChange={e => update("description", e.target.value)} rows="4" />
        <div className="form-grid-2">
          <div><label>Start date and time</label><input className="standalone-input" type="datetime-local" value={form.start_datetime} onChange={e => update("start_datetime", e.target.value)} required /></div>
          <div><label>End date and time</label><input className="standalone-input" type="datetime-local" value={form.end_datetime} onChange={e => update("end_datetime", e.target.value)} required /></div>
        </div>
        <label>Eligible voter category</label>
        <select className="standalone-input" value={form.eligible_voter_category} onChange={e => update("eligible_voter_category", e.target.value)}>
          {CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        {error && <div className="error">{error}</div>}
        <div className="modal-actions">
          <button type="button" className="secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="primary modal-primary" disabled={loading}>{loading ? "Saving..." : election ? "Save Changes" : "Create Election"}</button>
        </div>
      </form>
    </section>
  </div>;
}

function ElectionDetails({election, onClose}) {
  return <div className="modal-backdrop" onMouseDown={event => event.target === event.currentTarget && onClose()}>
    <section className="admin-modal small-modal">
      <div className="modal-header">
        <div><h2>Election Details</h2><p>{election.name}</p></div>
        <button className="modal-close" type="button" onClick={onClose}>×</button>
      </div>
      <div className="detail-list">
        <div><span>Description</span><strong>{election.description || "No description"}</strong></div>
        <div><span>Eligible voters</span><strong>{CATEGORIES.find(([value]) => value === election.eligible_voter_category)?.[1] || election.eligible_voter_category}</strong></div>
        <div><span>Start</span><strong>{displayDate(election.start_datetime)}</strong></div>
        <div><span>End</span><strong>{displayDate(election.end_datetime)}</strong></div>
        <div><span>Status</span><strong className={`status-badge ${election.status}`}>{election.status}</strong></div>
        <div><span>Voting currently allowed</span><strong>{election.is_open ? "Yes" : "No"}</strong></div>
        <div><span>Created</span><strong>{displayDate(election.created_date)}</strong></div>
      </div>
      <div className="modal-actions"><button className="secondary" onClick={onClose}>Close</button></div>
    </section>
  </div>;
}

function PositionForm({election, position, onClose, onSaved}) {
  const [name, setName] = useState(position?.name || "");
  const [order, setOrder] = useState(position?.order ?? 0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    if (!name.trim()) {
      setError("Position name is required.");
      return;
    }
    if (Number(order) < 0) {
      setError("Position order cannot be negative.");
      return;
    }

    setLoading(true);
    try {
      const payload = {name: name.trim(), order: Number(order)};
      if (position) {
        await api(`/admin/positions/${position.id}/`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
      } else {
        await api(`/admin/elections/${election.id}/positions/`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return <div className="modal-backdrop" onMouseDown={event => event.target === event.currentTarget && onClose()}>
    <section className="admin-modal small-modal">
      <div className="modal-header">
        <div><h2>{position ? "Edit Position" : "Add Position"}</h2><p>{election.name}</p></div>
        <button className="modal-close" type="button" onClick={onClose}>×</button>
      </div>
      <form onSubmit={submit}>
        <label>Position name</label>
        <input
          className="standalone-input"
          value={name}
          onChange={event => setName(event.target.value)}
          placeholder="e.g. President"
          maxLength={80}
          required
        />
        <label>Display order</label>
        <input
          className="standalone-input"
          type="number"
          min="0"
          value={order}
          onChange={event => setOrder(event.target.value)}
        />
        {error && <div className="error">{error}</div>}
        <div className="modal-actions">
          <button type="button" className="secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="primary modal-primary" disabled={loading}>{loading ? "Saving..." : position ? "Save Changes" : "Add Position"}</button>
        </div>
      </form>
    </section>
  </div>;
}

function CandidateForm({election, position, candidate, onClose, onSaved}) {
  const [name, setName] = useState(candidate?.name || "");
  const [partyList, setPartyList] = useState(candidate?.party_list || "");
  const [platform, setPlatform] = useState(candidate?.platform || "");
  const [photo, setPhoto] = useState(null);
  const [removePhoto, setRemovePhoto] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    if (!name.trim()) {
      setError("Candidate name cannot be empty or contain only spaces.");
      return;
    }
    if (photo && photo.size > 5 * 1024 * 1024) {
      setError("Candidate photo must be 5 MB or smaller.");
      return;
    }
    if (photo && removePhoto) {
      setError("Choose a new photo or remove the current photo, not both.");
      return;
    }
    setLoading(true);
    try {
      const payload = new FormData();
      payload.append("name", name.trim());
      payload.append("party_list", partyList.trim());
      payload.append("platform", platform.trim());
      if (photo) payload.append("photo", photo);
      if (candidate && removePhoto) payload.append("remove_photo", "true");

      if (candidate) {
        await api(`/admin/candidates/${candidate.id}/`, {method: "PATCH", body: payload});
      } else {
        await api(`/admin/elections/${election.id}/positions/${position.id}/candidates/`, {method: "POST", body: payload});
      }
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return <div className="modal-backdrop" onMouseDown={event => event.target === event.currentTarget && onClose()}>
    <section className="admin-modal small-modal">
      <div className="modal-header">
        <div><h2>{candidate ? "Edit Candidate" : "Add Candidate"}</h2><p>{election.name} · {position.name}</p></div>
        <button className="modal-close" type="button" onClick={onClose}>×</button>
      </div>
      <form onSubmit={submit}>
        <label>Candidate name</label>
        <input className="standalone-input" value={name} onChange={event => setName(event.target.value)} placeholder="e.g. Juan Dela Cruz" maxLength={120} required />
        <label>Party List</label>
        <input className="standalone-input" value={partyList} onChange={event => setPartyList(event.target.value)} placeholder="e.g. Student Unity Party" maxLength={120} />
        <label>Candidate Photo</label>
        {candidate?.photo && !removePhoto && <div className="candidate-photo-preview"><img src={mediaUrl(candidate.photo)} alt={`${candidate.name} candidate`} /></div>}
        <input className="standalone-input" type="file" accept="image/jpeg,image/png,image/webp" onChange={event => { setPhoto(event.target.files?.[0] || null); setRemovePhoto(false); }} />
        <small className="field-help">Optional. JPG, PNG, or WebP. Maximum 5 MB.</small>
        {candidate?.photo && <label className="checkbox-row"><input type="checkbox" checked={removePhoto} onChange={event => { setRemovePhoto(event.target.checked); if (event.target.checked) setPhoto(null); }} /> Remove current photo</label>}
        <label>Biography / Platform</label>
        <textarea className="standalone-input" value={platform} onChange={event => setPlatform(event.target.value)} rows="5" placeholder="Candidate biography or platform" />
        {error && <div className="error">{error}</div>}
        <div className="modal-actions">
          <button type="button" className="secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="primary modal-primary" disabled={loading}>{loading ? "Saving..." : candidate ? "Save Changes" : "Add Candidate"}</button>
        </div>
      </form>
    </section>
  </div>;
}

function CandidateManagement({election, position, onClose}) {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [editing, setEditing] = useState(null);
  const [creating, setCreating] = useState(false);

  async function loadCandidates() {
    setLoading(true);
    setError("");
    try {
      setCandidates(await api(`/admin/elections/${election.id}/positions/${position.id}/candidates/`));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadCandidates(); }, [election.id, position.id]);

  async function deleteCandidate(candidate) {
    if (!window.confirm(`Delete "${candidate.name}" from ${position.name}?`)) return;
    try {
      await api(`/admin/candidates/${candidate.id}/`, {method: "DELETE"});
      await loadCandidates();
      setSuccess("Candidate deleted successfully.");
    } catch (err) {
      setError(err.message);
    }
  }

  function saved() {
    setCreating(false);
    setEditing(null);
    setSuccess("Candidate saved successfully.");
    loadCandidates();
  }

  return <div className="modal-backdrop" onMouseDown={event => event.target === event.currentTarget && onClose()}>
    <section className="admin-modal position-modal">
      <div className="modal-header">
        <div><h2>Candidate Management</h2><p>{election.name} · {position.name}</p></div>
        <button className="modal-close" type="button" onClick={onClose}>×</button>
      </div>
      <div className="position-toolbar">
        <span>Manage candidates for this position.</span>
        <button className="primary modal-primary" onClick={() => setCreating(true)}>+ Add Candidate</button>
      </div>
      {error && <div className="error">{error}</div>}
      {success && <div className="success" role="status">{success}</div>}
      {loading ? <div className="loading-state"><span className="spinner" /> Loading candidates...</div> : candidates.length === 0 ? <div className="empty-state">No candidates found. Add the first candidate for this position.</div> :
        <div className="table-scroll">
          <table className="admin-table position-table">
            <thead><tr><th>Photo</th><th>Candidate</th><th>Party List</th><th>Biography / Platform</th><th>Actions</th></tr></thead>
            <tbody>{candidates.map(candidate => <tr key={candidate.id}>
              <td>{candidate.photo ? <img className="candidate-table-photo" src={mediaUrl(candidate.photo)} alt="" /> : "—"}</td>
              <td><strong>{candidate.name}</strong></td>
              <td>{candidate.party_list || "Independent / No party list"}</td>
              <td>{candidate.platform || "No biography/platform provided"}</td>
              <td><div className="table-actions">
                <button className="link-button" onClick={() => setEditing(candidate)}>Edit</button>
                <button className="link-button danger-link" onClick={() => deleteCandidate(candidate)}>Delete</button>
              </div></td>
            </tr>)}</tbody>
          </table>
        </div>}
      <div className="modal-actions"><button className="secondary" onClick={onClose}>Close</button></div>
    </section>
    {creating && <CandidateForm election={election} position={position} onClose={() => setCreating(false)} onSaved={saved} />}
    {editing && <CandidateForm election={election} position={position} candidate={editing} onClose={() => setEditing(null)} onSaved={saved} />}
  </div>;
}

function PositionManagement({election, onClose}) {
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [editing, setEditing] = useState(null);
  const [creating, setCreating] = useState(false);
  const [candidatesPosition, setCandidatesPosition] = useState(null);

  async function loadPositions() {
    setLoading(true);
    setError("");
    try {
      setPositions(await api(`/admin/elections/${election.id}/positions/`));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadPositions(); }, [election.id]);

  async function deletePosition(position) {
    if (!window.confirm(`Delete "${position.name}" from this election?`)) return;
    try {
      await api(`/admin/positions/${position.id}/`, {method: "DELETE"});
      await loadPositions();
      setSuccess("Position deleted successfully.");
    } catch (err) {
      setError(err.message);
    }
  }

  function saved() {
    setCreating(false);
    setEditing(null);
    setSuccess("Position saved successfully.");
    loadPositions();
  }

  return <div className="modal-backdrop" onMouseDown={event => event.target === event.currentTarget && onClose()}>
    <section className="admin-modal position-modal">
      <div className="modal-header">
        <div><h2>Position Management</h2><p>{election.name}</p></div>
        <button className="modal-close" type="button" onClick={onClose}>×</button>
      </div>
      <div className="position-toolbar">
        <span>Manage the positions voters will see in this election.</span>
        <button className="primary modal-primary" onClick={() => setCreating(true)}>+ Add Position</button>
      </div>
      {error && <div className="error">{error}</div>}
      {success && <div className="success" role="status">{success}</div>}
      {loading ? <div className="loading-state"><span className="spinner" /> Loading positions...</div> : positions.length === 0 ? <div className="empty-state">No positions found. Add the first position for this election.</div> :
        <div className="table-scroll">
          <table className="admin-table position-table">
            <thead><tr><th>Order</th><th>Position</th><th>Actions</th></tr></thead>
            <tbody>{positions.map(position => <tr key={position.id}>
              <td>{position.order}</td>
              <td><strong>{position.name}</strong></td>
              <td><div className="table-actions">
                <button className="link-button" onClick={() => setCandidatesPosition(position)}>Candidates</button>
                <button className="link-button" onClick={() => setEditing(position)}>Edit</button>
                <button className="link-button danger-link" onClick={() => deletePosition(position)}>Delete</button>
              </div></td>
            </tr>)}</tbody>
          </table>
        </div>}
      <div className="modal-actions"><button className="secondary" onClick={onClose}>Close</button></div>
    </section>
    {creating && <PositionForm election={election} onClose={() => setCreating(false)} onSaved={saved} />}
    {editing && <PositionForm election={election} position={editing} onClose={() => setEditing(null)} onSaved={saved} />}
    {candidatesPosition && <CandidateManagement election={election} position={candidatesPosition} onClose={() => setCandidatesPosition(null)} />}
  </div>;
}

export default function AdminElections() {
  const [elections, setElections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [formElection, setFormElection] = useState(null);
  const [creating, setCreating] = useState(false);
  const [details, setDetails] = useState(null);
  const [positionsElection, setPositionsElection] = useState(null);

  async function loadElections() {
    setLoading(true);
    setError("");
    try {
      setElections(await api("/admin/elections/"));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadElections(); }, []);

  async function viewDetails(election) {
    try {
      setDetails(await api(`/admin/elections/${election.id}/`));
    } catch (err) {
      setError(err.message);
    }
  }

  async function deleteElection(election) {
    if (election.status === "active") return;
    if (!window.confirm(`Delete "${election.name}"? This cannot be undone.`)) return;
    try {
      await api(`/admin/elections/${election.id}/`, {method: "DELETE"});
      await loadElections();
      setSuccess("Election deleted successfully.");
    } catch (err) {
      setError(err.message);
    }
  }

  function saved() {
    setCreating(false);
    setFormElection(null);
    setSuccess("Election saved successfully.");
    loadElections();
  }

  return <div>
    <AdminHeader />
    <main className="dashboard admin-users-page">
      <div className="admin-page-heading">
        <div><h1>Election Management</h1><p>Create and manage election schedules, positions, and eligible voter categories.</p></div>
        <button className="primary create-button" onClick={() => setCreating(true)}>+ Create Election</button>
      </div>
      {error && <div className="error">{error}</div>}
      {success && <div className="success" role="status">{success}</div>}
      <section className="admin-table-wrap">
        {loading ? <div className="loading-state"><span className="spinner" /> Loading elections...</div> : elections.length === 0 ? <div className="empty-state">No elections found.</div> : <div className="table-scroll">
          <table className="admin-table">
            <thead><tr><th>Election</th><th>Eligible voters</th><th>Start</th><th>End</th><th>Status</th><th>Actions</th></tr></thead>
            <tbody>{elections.map(election => <tr key={election.id}>
              <td><strong>{election.name}</strong><small>{election.description || "No description"}</small></td>
              <td>{CATEGORIES.find(([value]) => value === election.eligible_voter_category)?.[1] || election.eligible_voter_category}</td>
              <td>{displayDate(election.start_datetime)}</td>
              <td>{displayDate(election.end_datetime)}</td>
              <td><span className={`status-badge ${election.status}`}>{election.status}</span><small>{election.is_open ? "Voting open" : "Voting closed"}</small></td>
              <td><div className="table-actions">
                <button className="link-button" onClick={() => setPositionsElection(election)}>Manage Positions &amp; Candidates</button>
                <button className="link-button" onClick={() => viewDetails(election)}>Details</button>
                <button className="link-button" onClick={() => setFormElection(election)}>Edit</button>
                <button className="link-button danger-link" disabled={election.status === "active"} onClick={() => deleteElection(election)}>{election.status === "active" ? "Delete Locked" : "Delete"}</button>
              </div></td>
            </tr>)}</tbody>
          </table>
        </div>}
      </section>
    </main>
    {creating && <ElectionForm onClose={() => setCreating(false)} onSaved={saved} />}
    {formElection && <ElectionForm election={formElection} onClose={() => setFormElection(null)} onSaved={saved} />}
    {details && <ElectionDetails election={details} onClose={() => setDetails(null)} />}
    {positionsElection && <PositionManagement election={positionsElection} onClose={() => setPositionsElection(null)} />}
  </div>;
}
