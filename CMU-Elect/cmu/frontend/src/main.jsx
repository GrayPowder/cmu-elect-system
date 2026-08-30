import React, {useEffect, useState} from "react";
import {createRoot} from "react-dom/client";
import {
  BrowserRouter, Routes, Route, Navigate, Link, NavLink,
  useNavigate, useLocation, useParams
} from "react-router-dom";
import {api, clearAuth, mediaUrl} from "./api";
import AdminUsers from "./AdminUsers";
import AdminElections from "./AdminElections";
import AdminAnalytics from "./AdminAnalytics";
import VoterAnalytics from "./VoterAnalytics";
import "./styles.css";
import logo from "./assets/cmu-elect-logo.png";
import cmu from "./assets/image-removebg-preview 1.png";
import cover from "./assets/cover blue.png";
import emailIcon from "./assets/Email.png";
import lockIcon from "./assets/Lock.png";
import studentIcon from "./assets/Student Male@2x.png";
import teacherIcon from "./assets/Teacher.png";
import chartIcon from "./assets/chart.png";
import profileIcon from "./assets/Profile.png";
import dashboardBg from "./assets/grey cover.png";
import AdminAuditLogs from "./AdminAuditLogs";

function RequireAuth({children}) {
  const token = localStorage.getItem("token");
  return token ? children : <Navigate to="/login" replace />;
}

function RequirePasswordChanged({children}) {
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  if (!localStorage.getItem("token")) return <Navigate to="/login" replace />;
  if (user.must_change_password) return <Navigate to="/change-password" replace />;
  return children;
}

function RequireAdmin({children}) {
  const token = localStorage.getItem("token");
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  if (!token) return <Navigate to="/admin/login" replace />;
  if (!user.is_admin) return <Navigate to="/unauthorized" replace />;
  return children;
}



function AuthShell({children}) {
  return (
    <div
      className="auth-page"
      style={{backgroundImage: `url("${cover}")`}}
    >
      <section className="auth-brand">

        <div className="brand-logos">
          <img src={logo} className="brand-elect" />
          <img src={cmu} className="brand-cmu" />
        </div>

        <h1>CMU-ELECT</h1>

        <p>
          There's nothing better than being transparent to the people.
        </p>

      </section>

      {children}
    </div>
  );
}

function AuthCard({title, children, backToLogin=true}) {
  return <section className="auth-card">
    <h1>{title}</h1>
    {children}
    {backToLogin && <Link className="back-login" to="/login">← back to login</Link>}
  </section>;
}

function Login() {
  const nav = useNavigate();
  const [role, setRole] = useState("student");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await api("/auth/login/", {
        method: "POST",
        body: JSON.stringify({email: email.trim(), password, role}),
      });
      localStorage.setItem("token", data.token);
      localStorage.setItem("user", JSON.stringify(data.user));
      nav(data.user.must_change_password ? "/change-password" : "/dashboard");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return <AuthShell>
    <form className="auth-card login-card" onSubmit={submit}>
      <h1>Welcome!</h1>
      <p>Sign in to cast your voice and become an instrument for change.</p>
      <h3>Are you a/an?</h3>
      <div className="role-buttons">
        {["student", "alumni", "faculty"].map(r => <button
          type="button"
          key={r}
          className={`role role-${r} ${role === r ? "selected" : ""}`}
          onClick={() => { setRole(r); setError(""); }}
        >{r[0].toUpperCase() + r.slice(1)}</button>)}
      </div>

      <label>Login Identifier or CMU Email</label>
      <div className="input-wrap">
        <img src={emailIcon} />
        <input type="text" value={email} onChange={e => setEmail(e.target.value)} placeholder="enter your identifier or email" required />
      </div>

      <label>Password</label>
      <div className="input-wrap">
        <img src={lockIcon} />
        <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="enter your password" required />
      </div>

      {error && <div className="error">{error}</div>}
      <button className="primary" disabled={loading}>{loading ? "Signing In..." : "Sign In"}</button>
      <Link className="forgot-link" to="/forgot-password">Forgot Password?</Link>
      <Link className="forgot-link" to="/admin/login">Administrator Login</Link>
    </form>
  </AuthShell>;
}


function AdminLogin() {
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await api("/auth/admin/login/", {
        method: "POST",
        body: JSON.stringify({email: email.trim(), password}),
      });
      localStorage.setItem("token", data.token);
      localStorage.setItem("user", JSON.stringify(data.user));
      nav("/admin", {replace: true});
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return <AuthShell>
    <form className="auth-card login-card" onSubmit={submit}>
      <h1>Administrator Login</h1>
      <p>Sign in to manage CMU-ELECT securely.</p>
      <label>Administrator Email</label>
      <div className="input-wrap">
        <img src={emailIcon} />
        <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="enter administrator email" required />
      </div>
      <label>Password</label>
      <div className="input-wrap">
        <img src={lockIcon} />
        <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="enter password" required />
      </div>
      {error && <div className="error">{error}</div>}
      <button className="primary" disabled={loading}>{loading ? "Signing In..." : "Sign In"}</button>
      <Link className="back-login" to="/login">← voter login</Link>
    </form>
  </AuthShell>;
}

function Unauthorized() {
  return <AuthShell>
    <AuthCard title="UNAUTHORIZED" backToLogin={false}>
      <p>You do not have permission to access the administrator area.</p>
      <Link className="primary" to="/login">Return to login</Link>
    </AuthCard>
  </AuthShell>;
}

function AdminDashboard() {
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/admin/dashboard/")
      .then(setData)
      .catch(e => setError(e.message));
  }, []);

  async function logout() {
    try { await api("/auth/logout/", {method: "POST"}); } catch (_) {}
    clearAuth();
    nav("/admin/login", {replace: true});
  }

  return <div>
    <header className="topbar">
      <div className="topbar-brand">
        <img src={logo} alt="CMU-ELECT Logo" />
        <span>CMU-ELECT ADMIN</span>
      </div>
      <nav className="main-nav">
        <span className="user-chip">{data?.user?.email}</span>
        <NavLink to="/admin" end className={({isActive}) => `admin-nav-link${isActive ? " active" : ""}`}>Dashboard</NavLink>
        <NavLink to="/admin/users" className={({isActive}) => `admin-nav-link${isActive ? " active" : ""}`}>Voters</NavLink>
        <NavLink to="/admin/elections" className={({isActive}) => `admin-nav-link${isActive ? " active" : ""}`}>Elections</NavLink>
        <NavLink to="/admin/results" className={({isActive}) => `admin-nav-link${isActive ? " active" : ""}`}>Results</NavLink>
        <NavLink to="/admin/analytics" className={({isActive}) => `admin-nav-link${isActive ? " active" : ""}`}>Analytics</NavLink>
        <NavLink to="/admin/audit-logs" className={({isActive}) => `admin-nav-link${isActive ? " active" : ""}`}>Audit Logs</NavLink>
        <button onClick={logout}>Logout</button>
      </nav>
    </header>
    <main className="dashboard">
      <div className="result-title">
        <h1>Administrator Dashboard</h1>
        <p>Secure administrator area.</p>
      </div>
      {error && <div className="error">{error}</div>}
      <div className="position-grid">
        {data?.modules?.filter(module => !["positions", "candidates"].includes(module.key)).map(module => (
          <Link className="position" to={module.path} key={module.key}>
            <span>{module.name}</span>
          </Link>
        ))}
      </div>
    </main>
  </div>;
}

function AdminModulePlaceholder({name}) {
  return <div>
    <header className="topbar">
      <div className="topbar-brand"><span>CMU-ELECT ADMIN</span></div>
      <nav><NavLink to="/admin" end className={({isActive}) => `admin-nav-link${isActive ? " active" : ""}`}>Dashboard</NavLink></nav>
    </header>
    <main className="dashboard">
      <div className="result-title"><h1>{name}</h1><p>This administrator module is reserved for its dedicated implementation phase.</p></div>
    </main>
  </div>;
}


function ForgotPassword() {
  const nav = useNavigate();
  const [step, setStep] = useState("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function requestCode(e) {
    e.preventDefault();
    setError(""); setMessage(""); setLoading(true);
    try {
      const data = await api("/auth/forgot-password/", {
        method: "POST", body: JSON.stringify({email: email.trim()})
      });
      setMessage(data.detail);
      setStep("code");
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }

  async function verifyCode(e) {
    e.preventDefault();
    setError(""); setMessage(""); setLoading(true);
    try {
      const data = await api("/auth/verify-code/", {
        method: "POST", body: JSON.stringify({email: email.trim(), code})
      });
      sessionStorage.setItem("cmu_elect_reset_email", email.trim().toLowerCase());
      sessionStorage.setItem("cmu_elect_reset_token", data.reset_token);
      nav("/reset-password");
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }

  async function resendCode() {
    setError(""); setMessage("");
    try {
      const data = await api("/auth/resend-code/", {
        method: "POST", body: JSON.stringify({email: email.trim()})
      });
      setMessage(data.detail);
    } catch (err) { setError(err.message); }
  }

  if (step === "code") return <AuthShell>
    <AuthCard title="VERIFICATION">
      <p className="small-label">ENTER VERIFICATION CODE</p>
      <form onSubmit={verifyCode}>
        <input className="code-input" inputMode="numeric" maxLength="6" value={code}
          onChange={e => setCode(e.target.value.replace(/\D/g, ""))} placeholder="000000" required />
        <p className="resend-copy">Didn't receive a code? <button type="button" onClick={resendCode}>Resend</button></p>
        {message && <div className="info">{message}</div>}
        {error && <div className="error">{error}</div>}
        <button className="primary" disabled={loading}>{loading ? "Verifying..." : "Verify"}</button>
      </form>
    </AuthCard>
  </AuthShell>;

  return <AuthShell>
    <AuthCard title="FORGOT PASSWORD">
      <p className="forgot-copy">Enter your CMU email and we'll send you a verification code.</p>
      <form onSubmit={requestCode}>
        <div className="input-wrap"><img src={emailIcon}/><input type="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="enter your email" required /></div>
        {message && <div className="info">{message}</div>}
        {error && <div className="error">{error}</div>}
        <button className="primary" disabled={loading}>{loading ? "Sending..." : "SUBMIT"}</button>
      </form>
    </AuthCard>
  </AuthShell>;
}

function ResetPassword() {
  const nav = useNavigate();
  const [email, setEmail] = useState(() => sessionStorage.getItem("cmu_elect_reset_email") || "");
  const [resetToken] = useState(() => sessionStorage.getItem("cmu_elect_reset_token") || "");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!email || !resetToken) nav("/forgot-password", {replace: true});
  }, [email, resetToken, nav]);

  async function submit(e) {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      await api("/auth/reset-password/", {
        method: "POST",
        body: JSON.stringify({email, reset_token: resetToken, password, confirm_password: confirmPassword})
      });
      sessionStorage.removeItem("cmu_elect_reset_email");
      sessionStorage.removeItem("cmu_elect_reset_token");
      nav("/login", {replace: true});
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }

  return <AuthShell>
    <AuthCard title="RESET PASSWORD">
      <form onSubmit={submit}>
        <label>New password</label>
        <div className="input-wrap"><img src={lockIcon}/><input type="password" minLength="8" value={password} onChange={e=>setPassword(e.target.value)} placeholder="at least 8 characters" required /></div>
        <label>Confirm password</label>
        <div className="input-wrap"><img src={lockIcon}/><input type="password" minLength="8" value={confirmPassword} onChange={e=>setConfirmPassword(e.target.value)} placeholder="repeat your new password" required /></div>
        {error && <div className="error">{error}</div>}
        <button className="primary" disabled={loading}>{loading ? "Saving..." : "Reset Password"}</button>
      </form>
    </AuthCard>
  </AuthShell>;
}

function ChangePassword() {
  const nav = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      const data = await api("/auth/change-password/", {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
          confirm_password: confirmPassword,
        })
      });
      const user = JSON.parse(localStorage.getItem("user") || "{}");
      localStorage.setItem("token", data.token);
      localStorage.setItem("user", JSON.stringify({...user, must_change_password: data.must_change_password}));
      setCurrentPassword(""); setNewPassword(""); setConfirmPassword("");
      nav("/dashboard", {replace: true});
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }

  return <AuthShell>
    <AuthCard title="CHANGE PASSWORD" backToLogin={false}>
      <p className="forgot-copy">Your administrator provided an initial password. Change it before accessing the voting system.</p>
      <form onSubmit={submit}>
        <label>Current password</label>
        <div className="input-wrap"><img src={lockIcon}/><input type="password" value={currentPassword} onChange={e=>setCurrentPassword(e.target.value)} required /></div>
        <label>New password</label>
        <div className="input-wrap"><img src={lockIcon}/><input type="password" minLength="8" value={newPassword} onChange={e=>setNewPassword(e.target.value)} placeholder="at least 8 characters" required /></div>
        <label>Confirm new password</label>
        <div className="input-wrap"><img src={lockIcon}/><input type="password" minLength="8" value={confirmPassword} onChange={e=>setConfirmPassword(e.target.value)} placeholder="repeat your new password" required /></div>
        {error && <div className="error">{error}</div>}
        <button className="primary" disabled={loading}>{loading ? "Saving..." : "Change Password"}</button>
      </form>
      <button className="cancel-button" onClick={()=>{clearAuth();nav("/login", {replace: true})}}>Log out</button>
    </AuthCard>
  </AuthShell>;
}


function Layout({children}) {
  const nav = useNavigate();
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  async function logout() {
    try { await api("/auth/logout/", {method: "POST"}); } catch (_) {}
    clearAuth();
    nav("/login");
  }
  return <>
  <header className="topbar">
  <div className="topbar-brand">
    <img src={logo} alt="CMU-ELECT Logo" />
    <span>CMU-ELECT</span>
  </div>

  <nav className="main-nav">
    <span className="user-chip">{user.email}</span>
    <Link to="/dashboard">Home</Link>
    <button onClick={logout}>Logout</button>
  </nav>
</header>
    {children}
  </>;
}

function Profile() {
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  const category = user.role ? user.role.charAt(0).toUpperCase() + user.role.slice(1) : "Voter";

  return (
    <Layout>
      <main className="dashboard profile-page">
        <div className="page-heading-card">
          <div>
            <span className="eyebrow">ACCOUNT</span>
            <h1>My Profile</h1>
            <p>Review your CMU-ELECT account information and security options.</p>
          </div>
        </div>
        <section className="profile-grid">
          <article className="profile-card profile-identity">
            <div className="profile-avatar">{(user.username || user.email || "V").charAt(0).toUpperCase()}</div>
            <h2>{user.username || "Voter"}</h2>
            <span className={`category-badge ${user.role || "student"}`}>{category}</span>
            <p className="profile-muted">Your account is managed by a CMU-ELECT administrator.</p>
          </article>
          <article className="profile-card">
            <div className="section-heading"><div><h2>Account information</h2><p>Details currently associated with your voter account.</p></div></div>
            <div className="profile-details">
              <div><span>Login identifier</span><strong>{user.username || "—"}</strong></div>
              <div><span>CMU email</span><strong>{user.email || "—"}</strong></div>
              <div><span>Voter category</span><strong>{category}</strong></div>
              <div><span>Account status</span><strong className="status-badge active">Active</strong></div>
            </div>
            <div className="profile-actions">
              <Link className="secondary" to="/change-password">Change Password</Link>
              <Link className="primary profile-primary" to="/dashboard">Back to Dashboard</Link>
            </div>
          </article>
        </section>
      </main>
    </Layout>
  );
}

function Dashboard() {
  const [elections, setElections] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const user = JSON.parse(localStorage.getItem("user") || "{}");

  useEffect(() => {
    setLoading(true);
    api("/elections/")
      .then(setElections)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  function statusLabel(status) {
    if (status === "not_started") return "NOT STARTED";
    if (status === "ended") return "ENDED";
    return "ACTIVE";
  }

  return (
    <Layout>
      <div className="dashboard-background" style={{backgroundImage: `url("${dashboardBg}")`}}>
        <main className="dashboard">
          <div className="hero">
            <div>
              <h1>VOTER DASHBOARD</h1>
              <p>Welcome, {user.username || "Voter"}. View elections you are eligible to participate in.</p>
            </div>
            <img src={user.role === "faculty" || user.role === "alumni" ? teacherIcon : studentIcon} />
          </div>

          {error && <div className="error">{error}</div>}
          {loading && <div className="loading-state"><span className="spinner" /> Loading elections...</div>}

          {!loading && !error && elections.length === 0 && (
            <div className="message">No elections are currently available for your voter category.</div>
          )}

          {!loading && !error && elections.length > 0 && (
            <div className="section-heading voter-elections-heading">
              <div>
                <span className="eyebrow">ELECTIONS</span>
                <h2>Available Elections</h2>
                <p>Choose an election to review its details and voting options.</p>
              </div>
            </div>
          )}

          <div className="election-list">
            {elections.map(election => (
              <section className="election-card" key={election.id}>
                <div className="election-heading">
                  <div>
                    <h2>{election.name}</h2>
                    <span className={election.status === "active" && election.is_open ? "open" : "closed"}>
                      {statusLabel(election.status)}
                    </span>
                  </div>
                  {election.status === "ended" && (
                    <Link className="results-link" to={`/results/${election.id}`}>Results</Link>
                  )}
                </div>

                {election.description && <p>{election.description}</p>}

                <div className="election-meta">
                  <span><strong>Voting period:</strong> {new Date(election.start_datetime).toLocaleString()} — {new Date(election.end_datetime).toLocaleString()}</span>
                  <span><strong>Availability:</strong> {
                    election.voting_availability === "available"
                      ? "Voting Available"
                      : election.voting_availability === "not_started"
                        ? "Voting Not Yet Available"
                        : "Voting Ended"
                  }</span>
                </div>

                <div className="modal-actions election-card-actions">
                  <Link className="primary election-details-button" to={`/elections/${election.id}`}>View Election Details</Link>
                  <Link className="secondary" to={`/analytics/${election.id}`}>Live Analytics</Link>
                </div>
              </section>
            ))}
          </div>
        </main>
      </div>
    </Layout>
  );
}

function ElectionDetails() {
  const { electionId } = useParams();
  const [election, setElection] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api(`/elections/${electionId}/`)
      .then(setElection)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [electionId]);

  if (loading) return <Layout><main className="dashboard"><div className="loading-state"><span className="spinner" /> Loading election...</div></main></Layout>;

  return (
    <Layout>
      <main className="dashboard">
        <div className="result-title">
          <h1>{election?.name || "Election Details"}</h1>
          <p>Review the election information, positions, and candidates.</p>
        </div>

        {error && <div className="error">{error}</div>}

        {election && (
          <>
            <section className="election-card">
              <h2>{election.name}</h2>
              <p>{election.description || "No description provided."}</p>
              <div className="election-meta">
                <span><strong>Status:</strong> {election.status === "not_started" ? "Not Started" : election.status === "ended" ? "Ended" : "Active"}</span>
                <span><strong>Voting period:</strong> {new Date(election.start_datetime).toLocaleString()} — {new Date(election.end_datetime).toLocaleString()}</span>
                <span><strong>Availability:</strong> {
                  election.voting_availability === "available"
                    ? "Voting Available"
                    : election.voting_availability === "not_started"
                      ? "Voting Not Yet Available"
                      : "Voting Ended"
                }</span>
              </div>
            </section>

            <div className="position-grid">
              {election.positions.map(position => (
                <section className="position election-detail-position" key={position.id}>
                  <div>
                    <h2>{position.name}</h2>
                    {position.candidates.length === 0
                      ? <p>No candidates are available.</p>
                      : <ul>
                          {position.candidates.map(candidate => (
                            <li key={candidate.id}><strong>{candidate.name}</strong>{candidate.party_list ? ` · ${candidate.party_list}` : ""}</li>
                          ))}
                        </ul>}
                  </div>
                </section>
              ))}
            </div>

            <div className="modal-actions">
              <Link className="secondary" to="/dashboard">Back to Dashboard</Link>
              {election.is_open && election.positions.some(position => position.candidates.length > 0) && (
                <Link className="primary proceed-ballot-button" to={`/vote/${election.id}`}>Proceed to Ballot</Link>
              )}
            </div>
          </>
        )}
      </main>
    </Layout>
  );
}

function BallotPage() {
  const { electionId } = useParams();
  const nav = useNavigate();
  const [election, setElection] = useState(null);
  const [selections, setSelections] = useState({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api(`/elections/${electionId}/`)
      .then(data => {
        if (!data.is_open) {
          setError(data.status === "not_started"
            ? "Voting for this election has not started."
            : "Voting for this election has ended.");
        }
        setElection(data);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [electionId]);

  function selectCandidate(positionId, candidateId) {
    setSelections(current => ({...current, [positionId]: candidateId}));
  }

  function review() {
    setError("");
    if (!election?.is_open) return;
    if (Object.keys(selections).length === 0) {
      setError("Please select at least one candidate before continuing.");
      return;
    }
    nav(`/vote/${election.id}/review`, {state: {election, selections}});
  }

  if (loading) return <Layout><main className="dashboard"><div className="loading-state"><span className="spinner" /> Loading ballot...</div></main></Layout>;

  return (
    <Layout>
      <main className="dashboard">
        <div className="result-title">
          <h1>{election?.name || "Ballot"}</h1>
          <p>Select candidates for the positions you wish to vote for, then review your ballot.</p>
        </div>

        {error && <div className="error">{error}</div>}

        {election && election.is_open && (
          <>
            {election.positions.map(position => (
              <section className="election-card ballot-position" key={position.id}>
                <h2>{position.name}</h2>
                <div className="candidate-list">
                  {position.candidates.map(candidate => (
                    <article
                      className={`candidate ${selections[position.id] === candidate.id ? "chosen" : ""}`}
                      onClick={() => selectCandidate(position.id, candidate.id)}
                      key={candidate.id}
                    >
                      <img src={candidate.photo ? mediaUrl(candidate.photo) : profileIcon} alt="" />
                      <div>
                        {candidate.party_list && <span className="party">{candidate.party_list}</span>}
                        <h2>{candidate.name}</h2>
                        {candidate.department && <p>{candidate.department}</p>}
                        {candidate.platform && <p><b>Platform:</b> {candidate.platform}</p>}
                      </div>
                      <button type="button" onClick={e => {e.stopPropagation(); selectCandidate(position.id, candidate.id);}}>
                        {selections[position.id] === candidate.id ? "Selected" : "Select"}
                      </button>
                    </article>
                  ))}
                </div>
              </section>
            ))}

            <div className="modal-actions">
              <Link className="secondary" to={`/elections/${election.id}`}>Back</Link>
              <button className="primary" onClick={review}>Review Ballot</button>
            </div>
          </>
        )}
      </main>
    </Layout>
  );
}

function ReviewBallot() {
  const { electionId } = useParams();
  const nav = useNavigate();
  const location = useLocation();
  const state = location.state;
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!state?.election || String(state.election.id) !== String(electionId)) {
    return <Layout><main className="center"><div className="error">Your ballot session is no longer available. Please return to the election and start again.</div><Link className="primary" to={`/vote/${electionId}`}>Return to Ballot</Link></main></Layout>;
  }

  const {election, selections} = state;

  async function submit() {
    setSubmitting(true);
    setError("");
    try {
      const votes = Object.entries(selections).map(([position_id, candidate_id]) => ({
        position_id: Number(position_id),
        candidate_id: Number(candidate_id),
      }));
      const data = await api("/votes/", {
        method: "POST",
        body: JSON.stringify({election_id: Number(election.id), votes}),
      });
      nav(`/vote/${election.id}/confirmation`, {state: {confirmation: data}});
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Layout>
      <main className="dashboard">
        <div className="result-title">
          <h1>Review Ballot</h1>
          <p>Check your selections before submitting your vote.</p>
        </div>

        <section className="election-card">
          <h2>{election.name}</h2>
          {Object.entries(selections).map(([positionId, candidateId]) => {
            const position = election.positions.find(p => p.id === Number(positionId));
            const candidate = position?.candidates.find(c => c.id === Number(candidateId));
            return position && candidate ? (
              <div className="review-row" key={positionId}>
                <strong>{position.name}</strong>
                <span>{candidate.name}</span>
              </div>
            ) : null;
          })}
        </section>

        {error && <div className="error">{error}</div>}

        <div className="modal-actions">
          <button className="secondary" onClick={() => nav(`/vote/${election.id}`)}>Back</button>
          <button className="primary" onClick={submit} disabled={submitting}>
            {submitting ? "Submitting..." : "Submit Vote"}
          </button>
        </div>
      </main>
    </Layout>
  );
}

function VoteConfirmation() {
  const location = useLocation();
  const confirmation = location.state?.confirmation;

  return (
    <Layout>
      <main className="dashboard">
        <div className="result-title">
          <h1>Vote Successfully Submitted</h1>
          <p>Your ballot was recorded successfully.</p>
        </div>
        <section className="election-card">
          <h2>{confirmation?.election?.name || "Election"}</h2>
          <p><strong>Submission timestamp:</strong> {confirmation?.submitted_at ? new Date(confirmation.submitted_at).toLocaleString() : "Recorded"}</p>
          <p>Your selections have been securely recorded.</p>
        </section>
        <div className="modal-actions">
          <Link className="primary" to="/dashboard">Return to Dashboard</Link>
        </div>
      </main>
    </Layout>
  );
}

function ResultsContent({data}) {
  return <div className="results-content">
    <div className="result-summary">
      <div><span>Election</span><strong>{data.election.name}</strong></div>
    </div>
    {data.results.map(result => (
      <section className="result" key={result.position_id}>
        <div className="result-heading">
          <div>
            <h2>{result.position}</h2>
            <span>Final result percentages</span>
          </div>
          {result.winners.length > 0 && (
            <div className="winner-box">
              <span>Winner{result.winners.length > 1 ? "s" : ""}</span>
              <strong>{result.winners.map(w => w.candidate).join(", ")}</strong>
            </div>
          )}
        </div>
        <div className="result-candidates">
          {result.candidates.map(candidate => (
            <div className="result-candidate" key={candidate.id}>
              <span>{candidate.candidate}</span>
              <strong>{Number(candidate.percentage).toFixed(2)}%</strong>
            </div>
          ))}
        </div>
      </section>
    ))}
  </div>;
}

function Results() {
  const {electionId}=useParams();
  const [data,setData]=useState(null);
  const [error,setError]=useState("");
  useEffect(()=>{
    api(`/elections/${electionId}/results/`)
      .then(setData)
      .catch(e=>setError(e.message));
  },[electionId]);

  return <Layout>
    <main className="dashboard">
      <div className="result-title">
        <h1>Election Results</h1>
        <p>Official results calculated from recorded votes.</p>
      </div>
      {error && <div className="error">{error}</div>}
      {data && <ResultsContent data={data}/>}
    </main>
  </Layout>;
}

function AdminResults() {
  const [elections,setElections]=useState([]);
  const [selectedId,setSelectedId]=useState("");
  const [data,setData]=useState(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);

  useEffect(()=>{
    api("/admin/elections/")
      .then(items=>{
        setElections(items);
        if (items.length) setSelectedId(String(items[0].id));
      })
      .catch(e=>setError(e.message));
  },[]);

  useEffect(()=>{
    if (!selectedId) return;
    setLoading(true);
    setError("");
    api(`/elections/${selectedId}/results/`)
      .then(setData)
      .catch(e=>{setData(null);setError(e.message);})
      .finally(()=>setLoading(false));
  },[selectedId]);

  async function logout() {
    try { await api("/auth/logout/", {method:"POST"}); } catch (_) {}
    clearAuth();
    window.location.href = "/admin/login";
  }

  return <div>
    <header className="topbar">
      <div className="topbar-brand">
        <img src={logo} alt="CMU-ELECT Logo" />
        <span>CMU-ELECT ADMIN</span>
      </div>
      <nav>
        <NavLink to="/admin" end className={({isActive}) => `admin-nav-link${isActive ? " active" : ""}`}>Dashboard</NavLink>
        <button onClick={logout}>Logout</button>
      </nav>
    </header>
    <main className="dashboard">
      <div className="result-title">
        <h1>Election Results</h1>
        <p>Accurate results calculated from actual vote records.</p>
      </div>
      <section className="result-selector">
        <label htmlFor="result-election">Select election</label>
        <select id="result-election" className="standalone-input" value={selectedId} onChange={e=>setSelectedId(e.target.value)}>
          {elections.map(e=><option key={e.id} value={e.id}>{e.name} — {e.status}</option>)}
        </select>
      </section>
      {loading && <div className="loading-state"><span className="spinner" /> Loading results...</div>}
      {error && <div className="error">{error}</div>}
      {data && <ResultsContent data={data}/>}
      {!loading && !error && !data && elections.length === 0 && <div className="message">No elections are available yet.</div>}
    </main>
  </div>;
}

function App(){
  return <Routes>
    <Route path="/login" element={<Login/>}/>
    <Route path="/forgot-password" element={<ForgotPassword/>}/>
    <Route path="/reset-password" element={<ResetPassword/>}/>
    <Route path="/admin/login" element={<AdminLogin/>}/>
    <Route path="/unauthorized" element={<Unauthorized/>}/>
    <Route path="/admin" element={<RequireAdmin><AdminDashboard/></RequireAdmin>}/>
    <Route path="/admin/users" element={<RequireAdmin><AdminUsers/></RequireAdmin>}/>
    <Route path="/admin/elections" element={<RequireAdmin><AdminElections/></RequireAdmin>}/>
    <Route path="/admin/positions" element={<RequireAdmin><AdminModulePlaceholder name="Position Management"/></RequireAdmin>}/>
    <Route path="/admin/candidates" element={<RequireAdmin><AdminModulePlaceholder name="Candidate Management"/></RequireAdmin>}/>
    <Route path="/admin/results" element={<RequireAdmin><AdminResults/></RequireAdmin>}/>
    <Route path="/admin/analytics" element={<RequireAdmin><AdminAnalytics/></RequireAdmin>}/>
    <Route path="/admin/audit-logs" element={<RequireAdmin><AdminAuditLogs/></RequireAdmin>}/>
    <Route path="/change-password" element={<RequireAuth><ChangePassword/></RequireAuth>}/>
    <Route path="/dashboard" element={<RequireAuth><RequirePasswordChanged><Dashboard/></RequirePasswordChanged></RequireAuth>}/>
    <Route path="/profile" element={<RequireAuth><RequirePasswordChanged><Profile/></RequirePasswordChanged></RequireAuth>}/>
    <Route path="/elections/:electionId" element={<RequireAuth><RequirePasswordChanged><ElectionDetails/></RequirePasswordChanged></RequireAuth>}/>
    <Route path="/vote/:electionId" element={<RequireAuth><RequirePasswordChanged><BallotPage/></RequirePasswordChanged></RequireAuth>}/>
    <Route path="/vote/:electionId/review" element={<RequireAuth><RequirePasswordChanged><ReviewBallot/></RequirePasswordChanged></RequireAuth>}/>
    <Route path="/vote/:electionId/confirmation" element={<RequireAuth><RequirePasswordChanged><VoteConfirmation/></RequirePasswordChanged></RequireAuth>}/>
    <Route path="/results/:electionId" element={<RequireAuth><RequirePasswordChanged><Results/></RequirePasswordChanged></RequireAuth>}/>
    <Route path="/analytics/:electionId" element={<RequireAuth><RequirePasswordChanged><VoterAnalytics/></RequirePasswordChanged></RequireAuth>}/>
    <Route path="*" element={<Navigate to="/login" replace/>}/>
  </Routes>;
}

createRoot(document.getElementById("root")).render(<BrowserRouter><App/></BrowserRouter>);
