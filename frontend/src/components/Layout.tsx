/**
 * Layout component — wraps all pages with Navbar.
 */

import { Outlet } from "react-router-dom";
import Navbar from "@/components/Navbar";
import MailingSignup from "@/components/MailingSignup";

export default function Layout() {
  return (
    <div className="app-shell">
      <Navbar />
      <main className="main-content">
        <Outlet />
      </main>
      <MailingSignup />
    </div>
  );
}
