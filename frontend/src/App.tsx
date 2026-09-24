import { Route, Routes } from 'react-router';
import { AppShell } from './components/AppShell.tsx';
import DashboardPage from './pages/DashboardPage.tsx';
import NotFoundPage from './pages/NotFoundPage.tsx';
import ReviewDetailPage from './pages/ReviewDetailPage.tsx';
import ReviewHistoryPage from './pages/ReviewHistoryPage.tsx';

/** Route table. The router itself is provided by main.tsx (or by tests). */
export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="reviews" element={<ReviewHistoryPage />} />
        <Route path="reviews/:reviewId" element={<ReviewDetailPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
