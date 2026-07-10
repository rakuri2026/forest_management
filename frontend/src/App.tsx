import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import Forests from './pages/Forests';
import ForestDetail from './pages/ForestDetail';
import MyUploads from './pages/MyUploads';
import CalculationDetail from './pages/CalculationDetail';
import BlockNaming from './pages/BlockNaming';
import InventoryList from './pages/InventoryList';
import InventoryUpload from './pages/InventoryUpload';
import InventoryDetail from './pages/InventoryDetail';
import FieldbookList from './pages/FieldbookList';
import SamplingList from './pages/SamplingList';
import DraftResume from './pages/DraftResume';
import YearlyActivitiesPage from './components/YearlyActivities/YearlyActivitiesPage';
import OperationalPlanPage from './pages/OperationalPlanPage';
import TemplateDesignerPage from './pages/TemplateDesignerPage';
import PublicTemplatesPage from './pages/PublicTemplatesPage';
import AdminTemplatesPage from './pages/AdminTemplatesPage';

const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Protected routes */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            {/* Default route - redirect to My CFOPs */}
            <Route index element={<Navigate to="/my-uploads" replace />} />

            {/* Main routes */}
            <Route path="my-uploads" element={<MyUploads />} />
            <Route path="upload" element={<Navigate to="/my-uploads" replace />} />
            <Route path="drafts/:draftId/resume" element={<DraftResume />} />
            <Route path="calculations/:id" element={<CalculationDetail />} />
            <Route path="calculations/:id/block-naming" element={<BlockNaming />} />
            <Route path="calculations/:id/yearly-activities" element={<YearlyActivitiesPage />} />
            <Route path="calculations/:id/operational-plan" element={<OperationalPlanPage />} />
            <Route path="forests" element={<Forests />} />
            <Route path="forests/:id" element={<ForestDetail />} />

            {/* Inventory routes */}
            <Route path="inventory" element={<InventoryList />} />
            <Route path="inventory/upload" element={<InventoryUpload />} />
            <Route path="inventory/:id" element={<InventoryDetail />} />

            {/* Template routes */}
            <Route path="templates" element={<PublicTemplatesPage />} />
            <Route path="templates/designer/:templateId" element={
              <ProtectedRoute allowedRoles={['super_admin']}>
                <TemplateDesignerPage />
              </ProtectedRoute>
            } />
            <Route path="admin/templates" element={
              <ProtectedRoute allowedRoles={['super_admin']}>
                <AdminTemplatesPage />
              </ProtectedRoute>
            } />

            {/* Legacy routes (redirects for backward compatibility) */}
            <Route path="dashboard" element={<Navigate to="/my-uploads" replace />} />
            <Route path="my-forests" element={<Navigate to="/my-uploads" replace />} />
            <Route path="fieldbook" element={<FieldbookList />} />
            <Route path="sampling" element={<SamplingList />} />
          </Route>

          {/* Catch all - redirect to My CFOPs */}
          <Route path="*" element={<Navigate to="/my-uploads" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
