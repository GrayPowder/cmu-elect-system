import React, {useEffect, useMemo, useState} from "react";
import {Link, NavLink, useNavigate} from "react-router-dom";
import {api, clearAuth} from "./api";
import logo from "./assets/cmu-elect-logo.png";

const CATEGORIES = [
  ["", "All categories"],
  ["student", "Student"],
  ["alumni", "Alumni"],
  ["faculty", "Faculty"],
];

const STATUSES = [
  ["", "All statuses"],
  ["active", "Active"],
  ["inactive", "Inactive"],
];

function generatePassword() {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%";
  const values = new Uint32Array(16);
  crypto.getRandomValues(values);
  return Array.from(values, value => alphabet[value % alphabet.length]).join("");
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

function VoterForm({voter, onClose, onSaved}) {
  const editing = Boolean(voter);
  const [form, setForm] = useState(() => ({
    name: voter?.name || "",
    identifier: voter?.identifier || "",
    email: voter?.email || "",
    category: voter?.category || "student",
    status: voter?.status || "active",
    password: "",
  }));
  const [generated, setGenerated] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function update(key, value) {
    setForm(current => ({...current, [key]: value}));
  }

  function generate() {
    const password = generatePassword();
    update("password", password);
    setGenerated(true);
  }

  async function submit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const payload = {
        name: form.name.trim(),
        identifier: form.identifier.trim(),
        email: form.email.trim(),
        category: form.category,
        status: form.status,
      };
      if (!editing) payload.password = form.password;

      const data = await api(
        editing ? `/admin/voters/${voter.id}/` : "/admin/voters/",
        {method: editing ? "PATCH" : "POST", body: JSON.stringify(payload)}
      );
      onSaved(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return <div className="modal-backdrop" onMouseDown={event => event.target === event.currentTarget && onClose()}>
    <section className="admin-modal">
      <div className="modal-header">
        <div>
          <h2>{editing ? "Edit Voter" : "Create Voter"}</h2>
          <p>{editing ? "Update the voter's account information." : "Create an account for an authorized voter."}</p>
        </div>
        <button className="modal-close" type="button" onClick={onClose}>×</button>
      </div>

      <form onSubmit={submit}>
        <div className="form-grid">
          <div>
            <label>Name</label>
            <input value={form.name} onChange={e => update("name", e.target.value)} required />
          </div>
          <div>
            <label>Login identifier</label>
            <input value={form.identifier} onChange={e => update("identifier", e.target.value)} required />
          </div>
          <div>
            <label>Email</label>
            <input type="email" value={form.email} onChange={e => update("email", e.target.value)} required />
          </div>
          <div>
            <label>Voter category</label>
            <select value={form.category} onChange={e => update("category", e.target.value)}>
              {CATEGORIES.slice(1).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
            </select>
          </div>
          <div>
            <label>Account status</label>
            <select value={form.status} onChange={e => update("status", e.target.value)}>
              {STATUSES.slice(1).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
            </select>
          </div>
          {!editing && <div className="password-field">
            <label>Initial password</label>
            <div className="password-row">
              <input type="text" value={form.password} onChange={e => {update("password", e.target.value); setGenerated(false);}} minLength="8" required />
              <button type="button" className="secondary" onClick={generate}>Generate</button>
            </div>
            {generated && <p className="password-note">Generated in this browser. It is sent only when the account is created and is never returned by the API.</p>}
          </div>}
        </div>

        {error && <div className="error">{error}</div>}
        <div className="modal-actions">
          <button type="button" className="secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="primary modal-primary" disabled={loading}>{loading ? "Saving..." : editing ? "Save Changes" : "Create Voter"}</button>
        </div>
      </form>
    </section>
  </div>;
}

function PasswordResetModal({voter, onClose, onSaved}) {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [generated, setGenerated] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function generate() {
    const value = generatePassword();
    setPassword(value);
    setConfirmPassword(value);
    setGenerated(true);
  }

  async function submit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api(`/admin/voters/${voter.id}/reset-password/`, {
        method: "POST",
        body: JSON.stringify({password, confirm_password: confirmPassword}),
      });
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
        <div>
          <h2>Reset Voter Password</h2>
          <p>{voter.name} · {voter.identifier}</p>
        </div>
        <button className="modal-close" type="button" onClick={onClose}>×</button>
      </div>
      <form onSubmit={submit}>
        <label>New password</label>
        <div className="password-row">
          <input type="text" value={password} onChange={e => {setPassword(e.target.value); setGenerated(false);}} minLength="8" required />
          <button type="button" className="secondary" onClick={generate}>Generate</button>
        </div>
        <label>Confirm password</label>
        <input className="standalone-input" type="text" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} minLength="8" required />
        {generated && <p className="password-note">Generated in this browser. The API never returns the password.</p>}
        {error && <div className="error">{error}</div>}
        <div className="modal-actions">
          <button type="button" className="secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="primary modal-primary" disabled={loading}>{loading ? "Resetting..." : "Reset Password"}</button>
        </div>
      </form>
    </section>
  </div>;
}

export default function AdminUsers() {
  const [voters, setVoters] = useState([]);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [editing, setEditing] = useState(null);
  const [resetting, setResetting] = useState(null);
  const [creating, setCreating] = useState(false);

  async function loadVoters() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.set("search", search.trim());
      if (category) params.set("category", category);
      if (status) params.set("status", status);
      const data = await api(`/admin/voters/?${params.toString()}`);
      setVoters(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadVoters(); }, []);

  const summary = useMemo(() => ({
    total: voters.length,
    active: voters.filter(voter => voter.status === "active").length,
    inactive: voters.filter(voter => voter.status === "inactive").length,
  }), [voters]);

  function handleSaved() {
    setCreating(false);
    setEditing(null);
    setResetting(null);
    setSuccess("Voter account updated successfully.");
    loadVoters();
  }

  async function toggleStatus(voter) {
    const nextStatus = voter.status === "active" ? "inactive" : "active";
    const action = nextStatus === "active" ? "activate" : "deactivate";
    if (!window.confirm(`Are you sure you want to ${action} ${voter.name}?`)) return;
    try {
      await api(`/admin/voters/${voter.id}/`, {
        method: "PATCH",
        body: JSON.stringify({status: nextStatus}),
      });
      await loadVoters();
      setSuccess(`Voter account ${nextStatus === "active" ? "activated" : "deactivated"} successfully.`);
    } catch (err) {
      setError(err.message);
    }
  }

  return <div>
    <AdminHeader />
    <main className="dashboard admin-users-page">
      <div className="admin-page-heading">
        <div>
          <h1>Voter Account Management</h1>
          <p>Create and manage voter accounts. Public registration is not available.</p>
        </div>
        <button className="primary create-button" onClick={() => setCreating(true)}>+ Create Voter</button>
      </div>

      <div className="admin-summary">
        <div><strong>{summary.total}</strong><span>Displayed</span></div>
        <div><strong>{summary.active}</strong><span>Active</span></div>
        <div><strong>{summary.inactive}</strong><span>Inactive</span></div>
      </div>

      <section className="admin-panel">
        <div className="filter-row">
          <div className="search-box">
            <label>Search voters</label>
            <input value={search} onChange={e => setSearch(e.target.value)} onKeyDown={e => e.key === "Enter" && loadVoters()} placeholder="Name, identifier, or email" />
          </div>
          <div>
            <label>Category</label>
            <select value={category} onChange={e => setCategory(e.target.value)}>
              {CATEGORIES.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
            </select>
          </div>
          <div>
            <label>Status</label>
            <select value={status} onChange={e => setStatus(e.target.value)}>
              {STATUSES.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
            </select>
          </div>
          <button className="secondary filter-button" onClick={loadVoters}>Search / Filter</button>
        </div>
      </section>

      {error && <div className="error">{error}</div>}
      {success && <div className="success" role="status">{success}</div>}

      <section className="admin-table-wrap">
        {loading ? <div className="loading-state"><span className="spinner" /> Loading voters...</div> : voters.length === 0 ? <div className="empty-state">No voter accounts found.</div> : <div className="table-scroll">
          <table className="admin-table">
            <thead>
              <tr><th>Name</th><th>Identifier</th><th>Category</th><th>Status</th><th>Created date</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {voters.map(voter => <tr key={voter.id}>
                <td><strong>{voter.name}</strong><small>{voter.email}</small></td>
                <td>{voter.identifier}</td>
                <td><span className={`category-badge ${voter.category}`}>{voter.category}</span></td>
                <td><span className={`status-badge ${voter.status}`}>{voter.status}</span></td>
                <td>{new Date(voter.created_date).toLocaleString()}</td>
                <td><div className="table-actions">
                  <button className="link-button" onClick={() => setEditing(voter)}>Edit</button>
                  <button className="link-button" onClick={() => setResetting(voter)}>Reset Password</button>
                  <button className={`link-button ${voter.status === "active" ? "danger-link" : ""}`} onClick={() => toggleStatus(voter)}>{voter.status === "active" ? "Deactivate" : "Activate"}</button>
                </div></td>
              </tr>)}
            </tbody>
          </table>
        </div>}
      </section>
    </main>

    {creating && <VoterForm onClose={() => setCreating(false)} onSaved={handleSaved} />}
    {editing && <VoterForm voter={editing} onClose={() => setEditing(null)} onSaved={handleSaved} />}
    {resetting && <PasswordResetModal voter={resetting} onClose={() => setResetting(null)} onSaved={handleSaved} />}
  </div>;
}
