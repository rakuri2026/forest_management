import React, { useState } from 'react';
import { Link, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const Layout: React.FC = () => {
  const { user, logout, toggleRole } = useAuth();
  const [toggling, setToggling] = useState(false);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const handleToggleRole = async () => {
    setToggling(true);
    try {
      await toggleRole();
    } catch {
      // ignore
    } finally {
      setToggling(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-green-600 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex">
              <div className="flex-shrink-0 flex items-center">
                <Link to="/my-uploads" className="text-white text-xl font-bold">
                  Community Forest Management System
                </Link>
              </div>
              <div className="hidden sm:ml-6 sm:flex sm:space-x-8">
                <Link
                  to="/my-uploads"
                  className="border-transparent text-white hover:border-white hover:text-white inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
                >
                  My CFOPs
                </Link>
                <Link
                  to="/forests"
                  className="border-transparent text-white hover:border-white hover:text-white inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
                >
                  Community Forests
                </Link>
                <Link
                  to="/templates"
                  className="border-transparent text-white hover:border-white hover:text-white inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
                >
                  Templates
                </Link>
                {user?.role === 'super_admin' && (
                  <Link
                    to="/admin/templates"
                    className="border-transparent text-white hover:border-white hover:text-white inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
                  >
                    Admin
                  </Link>
                )}
              </div>
            </div>
            <div className="flex items-center">
              <div className="flex-shrink-0 flex items-center gap-2">
                <span className="text-white text-sm">{user?.email}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${user?.role === 'super_admin' ? 'bg-yellow-300 text-yellow-900' : 'bg-blue-300 text-blue-900'}`}>
                  {user?.role === 'super_admin' ? 'Admin' : 'User'}
                </span>
                <button
                  onClick={handleToggleRole}
                  disabled={toggling}
                  className="relative inline-flex items-center px-3 py-1 border border-transparent text-xs font-medium rounded-md text-white bg-green-500 hover:bg-green-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-300 disabled:opacity-50"
                >
                  {toggling ? '...' : 'Switch Role'}
                </button>
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
