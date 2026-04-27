import "./App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import HomePage from "./pages/HomePage";
import AppPage from "./pages/AppPage";
import AdminPage from "./pages/AdminPage";
import NPSCsatPage from "./pages/apps/NPSCsatPage";
import ActionIntelligencePage from "./pages/apps/ActionIntelligencePage";

const ProtectedRoute = ({ children, requiredRoles }) => {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-[#F1F5F9]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 border-4 border-[#CC0000] border-t-transparent rounded-full animate-spin" />
          <span className="text-[#475569] text-sm font-medium">Loading HSI Portal...</span>
        </div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (requiredRoles && !requiredRoles.includes(user.role)) return <Navigate to="/" replace />;
  return children;
};

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/" element={<ProtectedRoute><HomePage /></ProtectedRoute>} />
          <Route path="/apps/nps-csat" element={<ProtectedRoute><NPSCsatPage /></ProtectedRoute>} />
          <Route path="/apps/survey-builder" element={<ProtectedRoute><ActionIntelligencePage /></ProtectedRoute>} />
          <Route path="/apps/:appId" element={<ProtectedRoute><AppPage /></ProtectedRoute>} />
          <Route path="/admin" element={<ProtectedRoute requiredRoles={["admin", "super_admin"]}><AdminPage /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
