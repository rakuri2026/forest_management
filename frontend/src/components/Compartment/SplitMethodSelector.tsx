import React from 'react';

interface SplitMethodSelectorProps {
  method: 'parallel' | 'grid' | 'custom';
  onMethodChange: (method: 'parallel' | 'grid' | 'custom') => void;
}

export function SplitMethodSelector({
  method,
  onMethodChange,
}: SplitMethodSelectorProps) {
  const methods = [
    {
      id: 'parallel',
      name: 'Parallel Strips',
      description: 'Split into equal-width parallel strips',
      icon: (
        <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      ),
    },
    {
      id: 'grid',
      name: 'Grid Pattern',
      description: 'Split into grid cells (rows x columns)',
      icon: (
        <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
        </svg>
      ),
    },
  ];

  return (
    <div className="space-y-3">
      <label className="block text-sm font-medium text-gray-700">
        Split Method
      </label>
      <div className="grid grid-cols-2 gap-3">
        {methods.map((m) => (
          <div
            key={m.id}
            onClick={() => onMethodChange(m.id as 'parallel' | 'grid')}
            className={`p-4 border-2 rounded-lg cursor-pointer transition-all ${
              method === m.id
                ? 'border-green-500 bg-green-50 ring-2 ring-green-200'
                : 'border-gray-200 hover:border-green-300'
            }`}
          >
            <div className={`mx-auto w-12 h-12 mb-2 ${
              method === m.id ? 'text-green-600' : 'text-gray-500'
            }`}>
              {m.icon}
            </div>
            <h4 className={`text-center font-medium ${
              method === m.id ? 'text-green-900' : 'text-gray-900'
            }`}>
              {m.name}
            </h4>
            <p className="text-xs text-center mt-1 text-gray-500">
              {m.description}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
