import { Routes, Route } from 'react-router-dom';
import { OverviewPage } from './pages/OverviewPage';
import { AffiliatesPage } from './pages/AffiliatesPage';
import { AffiliateDetailPage } from './pages/AffiliateDetailPage';
import { HierarchyPage } from './pages/HierarchyPage';
import { MaccPage } from './pages/MaccPage';
import { CostsPage } from './pages/CostsPage';
import { TcoPage } from './pages/TcoPage';
import { RateOptimizationPage } from './pages/RateOptimizationPage';
import { AiConsumptionPage } from './pages/AiConsumptionPage';
import { LicensesPage } from './pages/LicensesPage';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<OverviewPage />} />
      <Route path="/affiliates" element={<AffiliatesPage />} />
      <Route path="/affiliates/:id" element={<AffiliateDetailPage />} />
      <Route path="/hierarchy" element={<HierarchyPage />} />
      <Route path="/macc" element={<MaccPage />} />
      <Route path="/costs" element={<CostsPage />} />
      <Route path="/tco" element={<TcoPage />} />
      <Route path="/rate-optimization" element={<RateOptimizationPage />} />
      <Route path="/ai" element={<AiConsumptionPage />} />
      <Route path="/licenses" element={<LicensesPage />} />
    </Routes>
  );
}
