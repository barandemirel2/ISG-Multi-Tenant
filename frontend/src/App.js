import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { ThemeProvider } from "@/context/ThemeContext";
import { BrandProvider, useBrand } from "@/context/BrandContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import ErrorBoundary from "@/components/ErrorBoundary";
import BrandAuthSync from "@/components/BrandAuthSync";
import CookieConsent from "@/components/CookieConsent";
import LoginPage from "@/pages/LoginPage";
import RegisterPage from "@/pages/RegisterPage";
import BrandSelectionPage from "@/pages/BrandSelectionPage";
import DashboardPage from "@/pages/DashboardPage";
import NewAuditPage from "@/pages/NewAuditPage";
import AuditFormPage from "@/pages/AuditFormPage";
import DofPage from "@/pages/DofPage";
import EmergencyPlanPage from "@/pages/EmergencyPlanPage";
import EmployeeTrainingPage from "@/pages/EmployeeTrainingPage";
import EmployeePanelPage from "@/pages/EmployeePanelPage";
import EmployeeHealthPage from "@/pages/EmployeeHealthPage";
import PeriodicControlsPage from "@/pages/PeriodicControlsPage";
import { Toaster } from "@/components/ui/sonner";
import { isPublicRegistrationEnabled } from "@/lib/registrationVisibility";

import UatChecklistPage from "@/pages/UatChecklistPage";

function RootRedirect() {
  const { user, checked } = useAuth();
  const { selectedBrand } = useBrand();
  if (!checked) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (!selectedBrand) return <Navigate to="/brand-selection" replace />;
  return <Navigate to="/dashboard" replace />;
}

// P0 — Public registration route gate. Mirrors the frontend flag
// ``isPublicRegistrationEnabled()`` (UX-only). The authoritative
// security boundary lives in the backend
// (``ENABLE_PUBLIC_REGISTRATION``); this gate simply ensures that
// navigating directly to ``/register`` does not surface the
// registration form when the operator has not opted in.
//
// When closed (the production/default posture) we redirect to
// ``/login`` so the user lands on a usable surface. ``/login`` does
// NOT redirect to ``/register`` so there is no infinite loop.
function RegisterGate() {
  if (!isPublicRegistrationEnabled()) {
    return <Navigate to="/login" replace />;
  }
  return <RegisterPage />;
}

function App() {
  return (
    <div className="App">
      <ErrorBoundary>
        <ThemeProvider>
          <BrandProvider>
            <BrowserRouter>
              <AuthProvider>
                <ErrorBoundary>
                  <BrandAuthSync />
                  <Routes>
                    <Route path="/" element={<RootRedirect />} />
                    <Route path="/login" element={<LoginPage />} />
                    <Route path="/register" element={<RegisterGate />} />
                    <Route path="/brand-selection" element={<ProtectedRoute><BrandSelectionPage /></ProtectedRoute>} />
                    <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
                    <Route path="/audits/new" element={<ProtectedRoute><NewAuditPage /></ProtectedRoute>} />
                    <Route path="/audits/:id" element={<ProtectedRoute><AuditFormPage /></ProtectedRoute>} />
                    <Route path="/dof" element={<ProtectedRoute><DofPage /></ProtectedRoute>} />
                    <Route path="/uat" element={<ProtectedRoute><UatChecklistPage /></ProtectedRoute>} />

                    {/* Çalışan Paneli Modülü & Alt Sayfaları */}
                    <Route path="/employees" element={<Navigate to="/employees/list" replace />} />
                    <Route path="/employees/list" element={<ProtectedRoute><EmployeePanelPage subpage="list" /></ProtectedRoute>} />
                    <Route path="/employees/job-descriptions" element={<ProtectedRoute><EmployeePanelPage subpage="job-descriptions" /></ProtectedRoute>} />

                    {/* Acil Durum Eylem Planı Modülü & Alt Sayfaları */}
                    <Route path="/emergency-plan" element={<Navigate to="/emergency-plan/plan" replace />} />
                    <Route path="/emergency-plan/plan" element={<ProtectedRoute><EmergencyPlanPage subpage="plan" /></ProtectedRoute>} />
                    <Route path="/emergency-plan/teams" element={<ProtectedRoute><EmergencyPlanPage subpage="teams" /></ProtectedRoute>} />
                    <Route path="/emergency-plan/layout" element={<ProtectedRoute><EmergencyPlanPage subpage="layout" /></ProtectedRoute>} />
                    <Route path="/emergency-plan/drills" element={<ProtectedRoute><EmergencyPlanPage subpage="drills" /></ProtectedRoute>} />

                    {/* Çalışan Eğitimi Modülü & Alt Sayfaları */}
                    <Route path="/employee-training" element={<Navigate to="/employee-training/basic" replace />} />
                    <Route path="/employee-training/basic" element={<ProtectedRoute><EmployeeTrainingPage subpage="basic" /></ProtectedRoute>} />
                    <Route path="/employee-training/orientation" element={<ProtectedRoute><EmployeeTrainingPage subpage="orientation" /></ProtectedRoute>} />
                    <Route path="/employee-training/hygiene" element={<ProtectedRoute><EmployeeTrainingPage subpage="hygiene" /></ProtectedRoute>} />
                    <Route path="/employee-training/additional" element={<ProtectedRoute><EmployeeTrainingPage subpage="additional" /></ProtectedRoute>} />
                    <Route path="/employee-training/toolbox" element={<ProtectedRoute><EmployeeTrainingPage subpage="toolbox" /></ProtectedRoute>} />
                    <Route path="/employee-training/emergency" element={<ProtectedRoute><EmployeeTrainingPage subpage="emergency" /></ProtectedRoute>} />
                    <Route path="/employee-training/emergency-team" element={<ProtectedRoute><EmployeeTrainingPage subpage="emergency-team" /></ProtectedRoute>} />
                    <Route path="/employee-training/risk-team" element={<ProtectedRoute><EmployeeTrainingPage subpage="risk-team" /></ProtectedRoute>} />
                    <Route path="/employee-training/first-aid" element={<ProtectedRoute><EmployeeTrainingPage subpage="first-aid" /></ProtectedRoute>} />
                    <Route path="/employee-training/entry" element={<ProtectedRoute><EmployeeTrainingPage subpage="entry" /></ProtectedRoute>} />

                    {/* Çalışan Sağlık Gözetim Modülü & Alt Sayfaları */}
                    <Route path="/employee-health" element={<Navigate to="/employee-health/entry-reports" replace />} />
                    <Route path="/employee-health/entry-reports" element={<ProtectedRoute><EmployeeHealthPage subpage="entry-reports" /></ProtectedRoute>} />
                    <Route path="/employee-health/periodic-reports" element={<ProtectedRoute><EmployeeHealthPage subpage="periodic-reports" /></ProtectedRoute>} />

                    {/* Periyodik Kontroller Modülü & Alt Sayfaları */}
                    <Route path="/periodic-controls" element={<Navigate to="/periodic-controls/inspection" replace />} />
                    <Route path="/periodic-controls/inspection" element={<ProtectedRoute><PeriodicControlsPage subpage="inspection" /></ProtectedRoute>} />
                    <Route path="/periodic-controls/maintenance" element={<ProtectedRoute><PeriodicControlsPage subpage="maintenance" /></ProtectedRoute>} />

                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                  <Toaster position="top-right" richColors />
                  <CookieConsent />
                </ErrorBoundary>
              </AuthProvider>
            </BrowserRouter>
          </BrandProvider>
        </ThemeProvider>
      </ErrorBoundary>
    </div>
  );
}

export default App;
