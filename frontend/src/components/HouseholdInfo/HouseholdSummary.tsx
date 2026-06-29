/**
 * Household Summary Dashboard
 * Displays aggregate statistics and charts
 */
import React, { useState } from 'react';
import { Card, Row, Col, Statistic, Tag, Divider, Collapse } from 'antd';
import {
  UserOutlined,
  HomeOutlined,
  TeamOutlined,
  FireOutlined,
  GoldOutlined,
  EnvironmentOutlined,
} from '@ant-design/icons';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import type { HouseholdSummary } from '../../types/household';
import HouseholdVariablePanel from './HouseholdVariablePanel';

interface HouseholdSummaryDashboardProps {
  summary: HouseholdSummary;
  calculationId?: string;
}

const HouseholdSummaryDashboard: React.FC<HouseholdSummaryDashboardProps> = ({
  summary,
  calculationId,
}) => {
  // Prepare caste distribution chart data
  const casteData = Object.entries(summary.caste_distribution).map(
    ([name, value]) => ({ name, value })
  );

  // Prepare prosperity distribution chart data
  const prosperityData = Object.entries(summary.prosperity_distribution).map(
    ([name, value]) => ({ name, value })
  );

  // Colors for pie charts
  const CASTE_COLORS = ['#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1', '#13c2c2'];
  const PROSPERITY_COLORS = {
    'सम्पन्न': '#52c41a',
    'मध्यम': '#1890ff',
    'विपन्न': '#faad14',
    'अति विपन्न': '#f5222d',
  };

  return (
    <div>
      {/* Summary Cards */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} md={8} lg={6}>
          <Card>
            <Statistic
              title="Total Households"
              value={summary.total_households}
              prefix={<HomeOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8} lg={6}>
          <Card>
            <Statistic
              title="Total Population"
              value={summary.total_population}
              prefix={<TeamOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
            <div style={{ marginTop: 8, fontSize: 12, color: '#666' }}>
              Male: {summary.total_male} | Female: {summary.total_female}
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8} lg={6}>
          <Card>
            <Statistic
              title="Forest Dependent"
              value={summary.forest_dependent_households}
              prefix={<EnvironmentOutlined />}
              suffix={`/ ${summary.total_households}`}
              valueStyle={{ color: '#52c41a' }}
            />
            <div style={{ marginTop: 8, fontSize: 12, color: '#666' }}>
              {((summary.forest_dependent_households / summary.total_households) * 100).toFixed(1)}%
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8} lg={6}>
          <Card>
            <Statistic
              title="Avg Land Area"
              value={summary.avg_land_area ? Number(summary.avg_land_area).toFixed(2) : 0}
              suffix="units"
              prefix={<GoldOutlined />}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
      </Row>

      <Divider>Livestock Summary</Divider>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Total Cows/Oxen"
              value={summary.total_cow_ox}
              valueStyle={{ color: '#8b4513' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Total Buffaloes"
              value={summary.total_buffalo}
              valueStyle={{ color: '#2f4f4f' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Total Goats/Sheep"
              value={summary.total_goat_sheep}
              valueStyle={{ color: '#696969' }}
            />
          </Card>
        </Col>
      </Row>

      <Divider>Forest Product Demands (Yearly)</Divider>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} md={8}>
          <Card>
            <Statistic
              title="Firewood (दाउरा)"
              value={Number(summary.total_firewood_demand_bhari).toFixed(1)}
              suffix="भारी"
              prefix={<FireOutlined />}
              valueStyle={{ color: '#ff4d4f' }}
            />
            <div style={{ marginTop: 8, fontSize: 12, color: '#666' }}>
              {(Number(summary.total_firewood_demand_bhari) * 25).toFixed(0)} kg
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card>
            <Statistic
              title="Grass (घाँस)"
              value={Number(summary.total_grass_demand_bhari).toFixed(1)}
              suffix="भारी"
              valueStyle={{ color: '#52c41a' }}
            />
            <div style={{ marginTop: 8, fontSize: 12, color: '#666' }}>
              {(Number(summary.total_grass_demand_bhari) * 25).toFixed(0)} kg
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card>
            <Statistic
              title="Bedding (सोत्तर)"
              value={Number(summary.total_bedding_demand_bhari).toFixed(1)}
              suffix="भारी"
              valueStyle={{ color: '#faad14' }}
            />
            <div style={{ marginTop: 8, fontSize: 12, color: '#666' }}>
              {(Number(summary.total_bedding_demand_bhari) * 25).toFixed(0)} kg
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card>
            <Statistic
              title="Timber (काठ)"
              value={Number(summary.total_timber_demand_cft).toFixed(1)}
              suffix="cft"
              valueStyle={{ color: '#8b4513' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card>
            <Statistic
              title="Poles (पोल)"
              value={summary.total_pole_demand}
              suffix="poles"
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
      </Row>

      <Divider>Distribution Analysis</Divider>

      <Row gutter={[16, 16]}>
        {/* Caste Distribution */}
        <Col xs={24} lg={12}>
          <Card title="Caste Classification Distribution" size="small">
            {casteData.length > 0 ? (
              <>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={casteData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, percent }) =>
                        `${name} (${(percent * 100).toFixed(0)}%)`
                      }
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {casteData.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={CASTE_COLORS[index % CASTE_COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                <div style={{ marginTop: 16 }}>
                  {casteData.map((item, index) => (
                    <Tag
                      key={item.name}
                      color={CASTE_COLORS[index % CASTE_COLORS.length]}
                      style={{ marginBottom: 8 }}
                    >
                      {item.name}: {item.value}
                    </Tag>
                  ))}
                </div>
              </>
            ) : (
              <p>No caste data available</p>
            )}
          </Card>
        </Col>

        {/* Prosperity Distribution */}
        <Col xs={24} lg={12}>
          <Card title="Prosperity Level Distribution" size="small">
            {prosperityData.length > 0 ? (
              <>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={prosperityData}>
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="value" fill="#1890ff">
                      {prosperityData.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={PROSPERITY_COLORS[entry.name as keyof typeof PROSPERITY_COLORS] || '#1890ff'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <div style={{ marginTop: 16 }}>
                  {prosperityData.map((item) => (
                    <Tag
                      key={item.name}
                      color={PROSPERITY_COLORS[item.name as keyof typeof PROSPERITY_COLORS]}
                      style={{ marginBottom: 8 }}
                    >
                      {item.name}: {item.value}
                    </Tag>
                  ))}
                </div>
              </>
            ) : (
              <p>No prosperity data available</p>
            )}
          </Card>
        </Col>
      </Row>

      <Divider>Notes</Divider>

      <Card size="small">
        <p style={{ marginBottom: 8 }}>
          <strong>1 भारी = 25 kg</strong>
        </p>
        <p style={{ marginBottom: 8 }}>
          All demands are calculated on a yearly basis.
        </p>
        <p style={{ marginBottom: 0 }}>
          Formulas:
        </p>
        <ul style={{ marginTop: 8, paddingLeft: 20, fontSize: 12, color: '#666' }}>
          <li>Firewood: (population × 250 + cattle × 600) kg/year ÷ 25</li>
          <li>Grass: (cow×20 + buffalo×30 + goat×5) kg/day × 365 ÷ 25</li>
          <li>Bedding: (cow + buffalo) × 10 kg/day × 365 ÷ 25</li>
        </ul>
      </Card>

      {calculationId && (
        <div style={{ marginTop: 24 }}>
          <HouseholdVariablePanel
            calculationId={calculationId}
            tabKey="summary"
            onInsert={(varStr) => {
              const ta = document.getElementById('summary-notes') as HTMLTextAreaElement;
              if (ta) {
                const start = ta.selectionStart;
                const end = ta.selectionEnd;
                ta.value = ta.value.substring(0, start) + varStr + ta.value.substring(end);
                ta.focus();
                ta.selectionStart = ta.selectionEnd = start + varStr.length;
              }
            }}
          />
          <div style={{
            border: '1px solid #d9d9d9',
            borderRadius: 6,
            padding: 12,
            background: '#fafafa',
            marginTop: 12,
          }}>
            <h4 style={{ margin: '0 0 8px 0', fontSize: 13 }}>
              अतिरिक्त विवरण / नोट (Additional Notes)
            </h4>
            <textarea
              id="summary-notes"
              rows={3}
              style={{
                width: '100%',
                border: '1px solid #d9d9d9',
                borderRadius: 4,
                padding: '8px 12px',
                fontSize: 13,
                lineHeight: 1.6,
                fontFamily: 'inherit',
                resize: 'vertical',
              }}
              placeholder="चर सम्मिलित गर्न माथिको 'सम्मिलित' बटन प्रयोग गर्नुहोस्।"
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default HouseholdSummaryDashboard;
