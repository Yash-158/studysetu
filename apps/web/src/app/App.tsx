import { useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { LandingPage } from './LandingPage'
import { ProtectedRoute } from './ProtectedRoute'
import { LoginPage } from '../features/auth/LoginPage'
import { ActivatePage } from '../features/auth/ActivatePage'
import { StudentShell } from '../features/student/StudentShell'
import { TeacherShell } from '../features/teacher/TeacherShell'
import { AdminShell } from '../features/admin/AdminShell'

export function App() {
  const hydrate = useAuth((s) => s.hydrate)

  useEffect(() => {
    hydrate()
  }, [hydrate])

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/activate" element={<ActivatePage />} />
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
