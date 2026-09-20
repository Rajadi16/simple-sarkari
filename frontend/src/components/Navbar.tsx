/**
 * Navbar component — top navigation with links to public and admin pages.
 */

import { Link, NavLink, useNavigate } from "react-router-dom";
import { useState } from "react";

export default function Navbar() {
  const navigate = useNavigate();
  const [hasToken, setHasToken] = useState(() => Boolean(localStorage.getItem("reviewer_token")));
  const linkClass = ({ isActive }: { isActive: boolean }) => isActive ? "nav-link active" : "nav-link";
  const logout = () => { localStorage.removeItem("reviewer_token"); setHasToken(false); navigate("/"); };
  return <header className="site-header"><nav className="site-nav" aria-label="Main navigation">
    <Link to="/" className="brand"><span className="brand-mark">JV</span><span><strong>JanVaani</strong><small>Government circulars, made clear</small></span></Link>
    <div className="nav-links"><NavLink to="/" className={linkClass} end>Explore</NavLink><NavLink to="/admin" className={linkClass} end>Operations</NavLink><NavLink to="/admin/reviews" className={linkClass}>Reviews</NavLink><NavLink to="/admin/ingest" className={linkClass}>Ingest</NavLink></div>
    {hasToken ? <button type="button" className="nav-access nav-button" onClick={logout}>Sign out <span>↗</span></button> : <NavLink to="/admin/access" className="nav-access">Reviewer access <span>↗</span></NavLink>}
  </nav></header>;
}
