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
import Upload from './pages/Upload';
import MyUploads from './pages/MyUploads';
import CalculationDetail from './pages/CalculationDetail';
import InventoryList from './pages/InventoryList';
import InventoryUpload from './pages/InventoryUpload';
import InventoryDetail from './pages/InventoryDetail';
import FieldbookList from './pages/FieldbookList';
import SamplingList from './pages/SamplingList';

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
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="forests" element={<Forests />} />
            <Route path="forests/:id" element={<ForestDetail />} />
            <Route path="my-forests" element={<Dashboard />} />
            <Route path="upload" element={<Upload />} />
            <Route path="my-uploads" element={<MyUploads />} />
            <Route path="calculations/:id" element={<CalculationDetail />} />
            
            {/* Inventory routes */}
            <Route path="inventory" element={<InventoryList />} />
            <Route path="inventory/upload" element={<InventoryUpload />} />
            <Route path="inventory/:id" element={<InventoryDetail />} />

            {/* Fieldbook and Sampling routes */}
            <Route path="fieldbook" element={<FieldbookList />} />
            <Route path="sampling" element={<SamplingList />} />
          </Route>

          {/* Catch all */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
