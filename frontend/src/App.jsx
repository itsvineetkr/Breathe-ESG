import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'

import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Upload from './pages/Upload'
import Uploads from './pages/Uploads'
import ReviewQueue from './pages/ReviewQueue'
import Reports from './pages/Reports'
import AuditLogs from './pages/AuditLogs'
import Team from './pages/Team'
import Settings from './pages/Settings'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Protected */}
          <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/upload" element={<ProtectedRoute requireAdmin><Upload /></ProtectedRoute>} />
          <Route path="/uploads/:type" element={<ProtectedRoute><Uploads /></ProtectedRoute>} />
          <Route path="/review" element={<ProtectedRoute><ReviewQueue status="pending_review" /></ProtectedRoute>} />
          <Route path="/approved" element={<ProtectedRoute><ReviewQueue status="approved" /></ProtectedRoute>} />
          <Route path="/rejected" element={<ProtectedRoute><ReviewQueue status="rejected" /></ProtectedRoute>} />
          <Route path="/reports" element={<ProtectedRoute><Reports /></ProtectedRoute>} />
          <Route path="/audit" element={<ProtectedRoute requireAdmin><AuditLogs /></ProtectedRoute>} />
          <Route path="/team" element={<ProtectedRoute requireAdmin><Team /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute requireAdmin><Settings /></ProtectedRoute>} />

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
