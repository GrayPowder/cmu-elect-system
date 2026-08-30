import React, {useCallback, useEffect, useState} from "react";
import {Link, NavLink, useNavigate} from "react-router-dom";
import {api, clearAuth} from "./api";
import logo from "./assets/cmu-elect-logo.png";

export default function AdminAuditLogs() {
  const nav = useNavigate();
  const [logs,setLogs]=useState([]), [actions,setActions]=useState([]), [targets,setTargets]=useState([]);
  const [search,setSearch]=useState(""), [action,setAction]=useState(""), [target,setTarget]=useState(""), [sort,setSort]=useState("desc");
  const [loading,setLoading]=useState(true), [error,setError]=useState("");
  const load=useCallback(async()=>{
    setLoading(true);
    try { const q=new URLSearchParams(); if(search.trim())q.set("search",search.trim()); if(action)q.set("action",action); if(target)q.set("target_model",target); q.set("sort",sort); const d=await api(`/admin/audit-logs/?${q.toString()}`); setLogs(d.logs||[]); setActions(d.actions||[]); setTargets(d.target_models||[]); setError(""); }
    catch(e){setError(e.message);} finally{setLoading(false);}
  },[search,action,target,sort]);
  useEffect(()=>{load();},[load]);
  async function logout(){try{await api("/auth/logout/",{method:"POST"});}catch(_){} clearAuth(); nav("/admin/login",{replace:true});}
  return <div>
    <header className="topbar"><div className="topbar-brand"><img src={logo} alt="CMU-ELECT Logo"/><span>CMU-ELECT ADMIN</span></div><nav className="main-nav"><NavLink to="/admin" end className={({isActive}) => `admin-nav-link${isActive ? " active" : ""}`}>Dashboard</NavLink><NavLink to="/admin/users" className={({isActive}) => `admin-nav-link${isActive ? " active" : ""}`}>Voters</NavLink><NavLink to="/admin/elections" className={({isActive}) => `admin-nav-link${isActive ? " active" : ""}`}>Elections</NavLink><NavLink to="/admin/results" className={({isActive}) => `admin-nav-link${isActive ? " active" : ""}`}>Results</NavLink><NavLink to="/admin/analytics" className={({isActive}) => `admin-nav-link${isActive ? " active" : ""}`}>Analytics</NavLink><NavLink to="/admin/audit-logs" className={({isActive}) => `admin-nav-link${isActive ? " active" : ""}`}>Audit Logs</NavLink><button onClick={logout}>Logout</button></nav></header>
    <main className="dashboard"><div className="admin-page-heading"><div><h1>Audit Logs</h1><p>Review important system, administrator, voter, voting, and security events.</p></div></div>
      <section className="result-selector audit-filters"><input className="standalone-input" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search action, actor, target, or description"/><select className="standalone-input" value={action} onChange={e=>setAction(e.target.value)}><option value="">All actions</option>{actions.map(x=><option key={x}>{x}</option>)}</select><select className="standalone-input" value={target} onChange={e=>setTarget(e.target.value)}><option value="">All targets</option>{targets.map(x=><option key={x}>{x}</option>)}</select><select className="standalone-input" value={sort} onChange={e=>setSort(e.target.value)}><option value="desc">Newest first</option><option value="asc">Oldest first</option></select></section>
      {error&&<div className="error">{error}</div>}{loading&&<div className="center"><span className="spinner" /> Loading audit logs...</div>}{!loading&&!logs.length&&<div className="message">No audit events match the current filters.</div>}
      {!loading&&logs.length>0&&<section className="analytics-panel"><div className="audit-table-wrap"><table className="audit-table"><thead><tr><th>Date</th><th>Actor</th><th>Action</th><th>Target</th><th>Description</th></tr></thead><tbody>{logs.map(log=><tr key={log.id}><td>{new Date(log.timestamp).toLocaleString()}</td><td>{log.actor}</td><td><span className="audit-action">{log.action}</span></td><td>{log.target_model ? `${log.target_model} ${log.target_object_id}` : "—"}</td><td>{log.description||"—"}</td></tr>)}</tbody></table></div></section>}
    </main></div>;
}
