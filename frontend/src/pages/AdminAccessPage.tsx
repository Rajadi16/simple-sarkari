import { useState } from "react";
import type { FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";

export default function AdminAccessPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [token, setToken] = useState("");
  const from = (location.state as { from?: string } | null)?.from || "/admin";

  const submit = (event: FormEvent) => {
    event.preventDefault();
    localStorage.setItem("reviewer_token", token.trim());
    navigate(from, { replace: true });
  };

  return <div className="page-stack narrow-page access-page"><div><p className="eyebrow">Reviewer access</p><h1>Enter your workspace token.</h1><p className="lede">Admin tools are protected because they can approve content and start ingestion jobs.</p></div><form className="form-panel" onSubmit={submit}><label>Reviewer token<input required type="password" value={token} onChange={(event) => setToken(event.target.value)} autoComplete="current-password" /></label><button className="button primary" type="submit">Continue to workspace</button></form><p className="form-help">Ask the backend owner for the reviewer token. It is never sent to the frontend build or stored in source code.</p></div>;
}