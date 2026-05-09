import React, { useState } from 'react';

export interface TabItem {
  id: string;
  label: string;
  icon?: React.ReactNode;
}

export interface TabGroup {
  id: string;
  label: string;
  icon?: React.ReactNode;
  tabs: TabItem[];
}

interface VerticalSidebarProps {
  groups: TabGroup[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
  className?: string;
}

export function VerticalSidebar({ groups, activeTab, onTabChange, className = '' }: VerticalSidebarProps) {
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});

  const toggleGroup = (groupId: string) => {
    setCollapsedGroups(prev => ({
      ...prev,
      [groupId]: !prev[groupId]
    }));
  };

  const isGroupCollapsed = (groupId: string) => collapsedGroups[groupId] ?? false;

  const isTabInGroup = (groupId: string, tabId: string) => {
    const group = groups.find(g => g.id === groupId);
    return group?.tabs.some(t => t.id === tabId);
  };

  const findGroupForTab = (tabId: string) => {
    return groups.find(g => g.tabs.some(t => t.id === tabId));
  };

  return (
    <div className={`flex flex-col h-full bg-white border-r border-gray-200 ${className}`}>
      {groups.map(group => {
        const isCollapsed = isGroupCollapsed(group.id);
        const activeInGroup = group.tabs.some(t => t.id === activeTab);
        
        return (
          <div key={group.id} className="border-b border-gray-100">
            <button
              onClick={() => toggleGroup(group.id)}
              className={`w-full flex items-center justify-between px-4 py-3 text-left text-sm font-medium transition-colors ${
                activeInGroup 
                  ? 'bg-green-50 text-green-700' 
                  : 'text-gray-700 hover:bg-gray-50'
              }`}
            >
              <div className="flex items-center gap-2">
                {group.icon && <span className="w-4 h-4">{group.icon}</span>}
                <span>{group.label}</span>
              </div>
              <svg
                className={`w-4 h-4 transition-transform ${isCollapsed ? '-rotate-90' : 'rotate-0'}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            
            {!isCollapsed && (
              <div className="pb-2">
                {group.tabs.map(tab => {
                  const isActive = tab.id === activeTab;
                  const groupForTab = findGroupForTab(tab.id);
                  const tabGroupCollapsed = groupForTab ? isGroupCollapsed(groupForTab.id) : false;
                  
                  // Don't render if the tab's group is collapsed
                  if (tabGroupCollapsed) return null;
                  
                  return (
                    <button
                      key={tab.id}
                      onClick={() => onTabChange(tab.id)}
                      className={`w-full flex items-center gap-2 px-4 py-2 text-left text-sm transition-colors ${
                        isActive
                          ? 'bg-green-100 text-green-800 border-r-2 border-green-500'
                          : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                      }`}
                    >
                      {tab.icon && <span className="w-4 h-4">{tab.icon}</span>}
                      <span>{tab.label}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function createTabGroups(_unifiedMappingEnabled: boolean = false): TabGroup[] {
  const forestDataTabs = [
    { id: 'analysis', label: 'Analysis' },
    { id: 'subareas', label: 'Sub-Areas' },
    { id: 'compartments', label: 'Compartments' },
    { id: 'yearlyactivities', label: 'Yearly Activities' },
  ];

  return [
    {
      id: 'forest-data',
      label: 'Forest Data',
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
        </svg>
      ),
      tabs: [
        { id: 'analysis', label: 'Analysis' },
        { id: 'subareas', label: 'Sub-Areas' },
        { id: 'compartments', label: 'Compartments' },
        { id: 'yearlyactivities', label: 'Yearly Activities' },
      ]
    },
    {
      id: 'sampling-model',
      label: 'Sampling & Model',
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      ),
      tabs: [
        { id: 'sampling', label: 'Sampling' },
        { id: 'treemodel', label: 'Tree Model' },
        { id: 'treemapping', label: 'Tree Mapping' },
        { id: 'fieldbook', label: 'Fieldbook' },
      ]
    },
    {
      id: 'data-maps',
      label: 'Data & Maps',
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0121 18.382V7.618a1 1 0 01-.553-.894L15 4m0 13V4m0 0L9 7" />
        </svg>
      ),
      tabs: [
        { id: 'biodiversity', label: 'Biodiversity' },
        { id: 'maps', label: 'Maps' },
        { id: 'usergroup', label: 'User Group Map' },
        { id: 'fieldinventory', label: 'Field Inventory' },
        { id: 'totalinventory', label: 'Total Inventory' },
      ]
    },
  ];
}