import { Suspense, lazy, useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { LandingPage } from './LandingPage'
import { ProtectedRoute } from './ProtectedRoute'
import { LoginPage } from '../features/auth/LoginPage'
import { ActivatePage } from '../features/auth/ActivatePage'
import { TeacherSignupPage } from '../features/auth/TeacherSignupPage'
import { StudentShell } from '../features/student/StudentShell'
import { TeacherShell } from '../features/teacher/TeacherShell'
import { AdminShell } from '../features/admin/AdminShell'

// Dev-only design comparison tool. React.lazy() code-splits it into its own chunk, and the route
// below only exists in the Routes tree when import.meta.env.DEV is true - checked against the
// real `vite build` output: DesignPreview never appears in the main index-*.js bundle, and in
// production the route simply does not exist (visiting /__design-preview 404s/falls through -
// there is no route to match, not a hidden-but-reachable one). Verified nuance, not overclaimed:
// Rollup still emits DesignPreview-*.js/.css as separate, orphaned files in dist/assets/ (normal
// code-splitting behavior) - unreferenced by anything and unreachable via the app's navigation,
// but technically present as static files on the CDN if someone already knew the exact hashed
// filename. Judged not worth extra build-config complexity to eliminate entirely - see
// docs/DESIGN.md's Design Preview section.
const DesignPreview = lazy(() => import('../dev/DesignPreview').then((m) => ({ default: m.DesignPreview })))

export function App() {
  const hydrate = useAuth((s) => s.hydrate)

  useEffect(() => {
    hydrate()
  }, [hydrate])

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        {import.meta.env.DEV && (
          <Route path="/__design-preview" element={<Suspense fallback={null}><DesignPreview /></Suspense>} />
        )}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/activate" element={<ActivatePage />} />
        <Route path="/teacher-signup" element={<TeacherSignupPage />} />
        <Route
          path="/student/*"
          element={
            <ProtectedRoute role="student">
              <StudentShell />
            </ProtectedRoute>
          }
        />
        <Route
          path="/teacher/*"
          element={
            <ProtectedRoute role="teacher">
              <TeacherShell />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/*"
          element={
            <ProtectedRoute role="admin">
              <AdminShell />
            </ProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}
