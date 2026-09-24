import { Route, Routes } from 'react-router';
import { AppShell } from './components/AppShell.tsx';
import { AuthGate } from './features/auth/AuthGate.tsx';
import DashboardPage from './pages/DashboardPage.tsx';
import NotFoundPage from './pages/NotFoundPage.tsx';
import ReviewDetailPage from './pages/ReviewDetailPage.tsx';
import ReviewHistoryPage from './pages/ReviewHistoryPage.tsx';

/** Route table behind the sign-in gate. Router and auth state come from main.tsx (or tests). */
export default function App() {
  return (
    <AuthGate>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="reviews" element={<ReviewHistoryPage />} />
          <Route path="reviews/:reviewId" element={<ReviewDetailPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </AuthGate>
  );
}
