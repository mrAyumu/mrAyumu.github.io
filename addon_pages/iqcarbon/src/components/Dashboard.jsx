import React from 'react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import MetricsCard from './MetricsCard';

export default function Dashboard({ data, metrics }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Metrics Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
        gap: '16px'
      }}>
        <MetricsCard 
          title="Total CO2 Injected" 
          value={metrics.totalInjection} 
          unit="kilograms"
        />
        <MetricsCard 
          title="Net CO2 Captured" 
          value={metrics.netCapture} 
          unit="kilograms"
          color="#16a34a"
        />
        <MetricsCard 
          title="Storage Efficiency" 
          value={`${metrics.efficiency}%`} 
          unit="retention rate"
          color="#2563eb"
        />
        <MetricsCard 
          title="Est. Carbon Credits" 
          value={metrics.estimatedCredits} 
          unit={`$${metrics.estimatedValue} USD value`}
          color="#9333ea"
        />
      </div>

      {/* Charts */}
      <div style={{ background: 'white', borderRadius: '12px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
        <h3 style={{ fontSize: '18px', fontWeight: 600, color: '#111827', marginBottom: '16px' }}>
          CO2 Injection vs Production Trend
        </h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="injection" stroke="#10b981" strokeWidth={2} name="CO2 Injected (kg)" />
            <Line type="monotone" dataKey="production" stroke="#ef4444" strokeWidth={2} name="CO2 Produced (kg)" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div style={{ background: 'white', borderRadius: '12px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
        <h3 style={{ fontSize: '18px', fontWeight: 600, color: '#111827', marginBottom: '16px' }}>
          Net CO2 Capture by Period
        </h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="net" fill="#3b82f6" name="Net Capture (kg)" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
