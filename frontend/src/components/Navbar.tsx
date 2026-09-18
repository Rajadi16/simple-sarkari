/**
 * Navbar component — top navigation with links to public and admin pages.
 */

import { Link } from "react-router-dom";

export default function Navbar() {
  return (
    <nav style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "1rem 2rem",
      backgroundColor: "var(--color-primary)",
      color: "white",
    }}>
      <Link to="/" style={{ color: "white", fontWeight: 700, fontSize: "1.25rem", textDecoration: "none" }}>
        🇮🇳 JanVaani
      </Link>
      <div style={{ display: "flex", gap: "1.5rem" }}>
        <Link to="/" style={{ color: "white", textDecoration: "none" }}>Search</Link>
        <Link to="/admin" style={{ color: "white", textDecoration: "none" }}>Admin</Link>
        <Link to="/admin/reviews" style={{ color: "white", textDecoration: "none" }}>Reviews</Link>
        <Link to="/admin/ingest" style={{ color: "white", textDecoration: "none" }}>Ingest</Link>
      </div>
    </nav>
  );
}
