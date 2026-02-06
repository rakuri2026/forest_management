import React from 'react';
import { Link, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const Layout: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-green-600 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex">
              <div className="flex-shrink-0 flex items-center">
                <Link to="/dashboard" className="text-white text-xl font-bold">
                  Forest Management
                </Link>
              </div>
              <div className="hidden sm:ml-6 sm:flex sm:space-x-8">
                <Link
                  to="/dashboard"
                  className="border-transparent text-white hover:border-white hover:text-white inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
                >
                  Dashboard
                </Link>
                <Link
                  to="/upload"
                  className="border-transparent text-white hover:border-white hover:text-white inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
                >
                  Upload
                </Link>
                <Link
                  to="/my-uploads"
                  className="border-transparent text-white hover:border-white hover:text-white inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
                >
                  My Uploads
                </Link>
                <Link
                  to="/forests"
                  className="border-transparent text-white hover:border-white hover:text-white inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
                >
                  All Forests
                </Link>
                <Link
                  to="/my-forests"
                  className="border-transparent text-white hover:border-white hover:text-white inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
                >
                  My Forests
                </Link>
                <Link
                  to="/fieldbook"
                  className="border-transparent text-white hover:border-white hover:text-white inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
                >
                  Fieldbook
                </Link>
                <Link
                  to="/sampling"
                  className="border-transparent text-white hover:border-white hover:text-white inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
                >
                  Sampling
                </Link>
              </div>
            </div>
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <span className="text-white text-sm mr-4">{user?.email}</span>
                <button
                  onClick={handleLogout}
                  className="relative inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-green-600 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
                >
                  Logout
                </button>
              </div>
            </div>
          </div>
        </div>
      </nav>
      <main>
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;
