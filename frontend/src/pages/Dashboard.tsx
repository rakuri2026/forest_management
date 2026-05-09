import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { forestApi } from '../services/api';
import type { MyForestsResponse } from '../types';

const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const [myForests, setMyForests] = useState<MyForestsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadMyForests = async () => {
      try {
        const data = await forestApi.getMyForests();
        setMyForests(data);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load your forests');
      } finally {
        setIsLoading(false);
      }
    };

    loadMyForests();
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900">
              Welcome, {user?.full_name}
            </h1>
            <p className="mt-2 text-sm text-gray-600">
              Role: <span className="font-medium">{user?.role}</span>
            </p>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 mb-8">
            <div className="bg-white overflow-hidden shadow rounded-lg">
              <div className="px-4 py-5 sm:p-6">
                <h3 className="text-lg font-medium text-gray-900">My Forests</h3>
                {isLoading ? (
                  <p className="mt-2 text-sm text-gray-500">Loading...</p>
                ) : error ? (
                  <p className="mt-2 text-sm text-red-500">{error}</p>
                ) : (
                  <div className="mt-4">
                    <p className="text-3xl font-semibold text-green-600">
                      {myForests?.total_count || 0}
                    </p>
                    <p className="mt-1 text-sm text-gray-500">
                      Total Area: {myForests?.total_area_hectares?.toFixed(2) || 0} hectares
                    </p>
                  </div>
                )}
              </div>
            </div>

            <div className="bg-white overflow-hidden shadow rounded-lg">
              <div className="px-4 py-5 sm:p-6">
                <h3 className="text-lg font-medium text-gray-900">Quick Actions</h3>
                <div className="mt-4 space-y-3">
                  <Link
                    to="/forests"
                    className="block w-full text-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700"
                  >
                    Explore All Forests
                  </Link>
                  <Link
                    to="/my-forests"
                    className="block w-full text-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
                  >
                    View My Forests
                  </Link>
                </div>
              </div>
            </div>
          </div>

          {myForests && myForests.forests.length > 0 && (
            <div className="bg-white shadow overflow-hidden sm:rounded-lg">
              <div className="px-4 py-5 sm:px-6">
                <h3 className="text-lg leading-6 font-medium text-gray-900">
                  Recently Assigned Forests
                </h3>
              </div>
              <div className="border-t border-gray-200">
                <ul className="divide-y divide-gray-200">
                  {myForests.forests.slice(0, 5).map((forest) => (
                    <li key={forest.id} className="px-4 py-4 sm:px-6 hover:bg-gray-50">
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-green-600 truncate">
                            {forest.name}
                          </p>
                          <p className="mt-1 text-sm text-gray-500">
                            Code: {forest.code} | Regime: {forest.regime} | Role: {forest.role}
                          </p>
                        </div>
                        <div className="ml-4 flex-shrink-0">
                          <span className="text-sm text-gray-500">
                            {forest.area_hectares.toFixed(2)} ha
                          </span>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
