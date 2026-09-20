/**
 * JanVaani — App root with React Router routes.
 */

import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "@/components/Layout";
import HomePage from "@/pages/HomePage";
import CircularPage from "@/pages/CircularPage";
import AdminDashboard from "@/pages/AdminDashboard";
import ReviewPage from "@/pages/ReviewPage";
import IngestPage from "@/pages/IngestPage";
import AdminAccessPage from "@/pages/AdminAccessPage";
import AdminGate from "@/components/AdminGate";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          {/* Public */}
          <Route path="/" element={<HomePage />} />
          <Route path="/circular/:id" element={<CircularPage />} />

          <Route path="/admin/access" element={<AdminAccessPage />} />
          <Route element={<AdminGate />}>
            <Route path="/admin" element={<AdminDashboard />} />
            <Route path="/admin/reviews" element={<ReviewPage />} />
            <Route path="/admin/ingest" element={<IngestPage />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
