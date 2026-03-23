import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { DashboardPage } from "./pages/DashboardPage";
import { NewScanPage } from "./pages/NewScanPage";
import { ScanDetailPage } from "./pages/ScanDetailPage";
import { ScansPage } from "./pages/ScansPage";
import { SessionsPage } from "./pages/SessionsPage";
import { SessionDetailPage } from "./pages/SessionDetailPage";
import { TopViolationsPage } from "./pages/TopViolationsPage";
import { FixTrackerPage } from "./pages/FixTrackerPage";
import { AiMetricsPage } from "./pages/AiMetricsPage";
import { HealthPage } from "./pages/HealthPage";

export function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/new-scan" element={<NewScanPage />} />
          <Route path="/scans" element={<ScansPage />} />
          <Route path="/scans/:scanId" element={<ScanDetailPage />} />
          <Route path="/sessions" element={<SessionsPage />} />
          <Route path="/sessions/:sessionId" element={<SessionDetailPage />} />
          <Route path="/violations" element={<TopViolationsPage />} />
          <Route path="/fix-tracker" element={<FixTrackerPage />} />
          <Route path="/ai-metrics" element={<AiMetricsPage />} />
          <Route path="/health" element={<HealthPage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
