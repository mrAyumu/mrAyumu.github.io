import React, { useState } from 'react';
import Header from './components/Header.jsx';
import Dashboard from './components/Dashboard.jsx';
import ReportView from './components/ReportView.jsx';
import { processData } from './utils/dataProcessor.js';

export default function App() {
  const [data, setData] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [activeTab, setActiveTab] = useState('dashboard');

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const text = await file.text();
    const lines = text.split('\n').filter(line => line.trim());
    const headers = lines[0].split(',').map(h => h.trim());
    
    const parsed = lines.slice(1).map(line => {
      const values = line.split(',');
      const obj = {};
      headers.forEach((header, i) => {
        obj[header] = values[i]?.trim();
      });
      return obj;
    }).filter(row => row[headers[0]]);

    const { processedData, calculatedMetrics } = processData(parsed);
    setData(processedData);
    setMetrics(calculatedMetrics);
  };

  const loadSampleData = () => {
    const sample = [
      { date: '2025-01', co2_injection: '12500', co2_production: '1200' },
      { date: '2025-02', co2_injection: '13200', co2_production: '1100' },
      { date: '2025-03', co2_injection: '14100', co2_production: '1300' },
      { date: '2025-04', co2_injection: '13800', co2_production: '1250' },
      { date: '2025-05', co2_injection: '15000', co2_production: '1400' },
      { date: '2025-06', co2_injection: '15500', co2_production: '1350' }
    ];
    const { processedData, calculatedMetrics } = processData(sample);
    setData(processedData);
    setMetrics(calculatedMetrics);
  };

  return (
    <div style={{ minHeight: '100vh', background: 'linear-gradient(to bottom right, #f0fdf4, #eff6ff)' }}>
      <Header 
        onFileUpload={handleFileUpload}
        onLoadSample={loadSampleData}
      />
      
      <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '24px' }}>
        <div style={{ display: 'flex', gap: '8px', marginBottom: '24px' }}>
          <button
            onClick={() => setActiveTab('dashboard')}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              fontWeight: 500,
              border: 'none',
              cursor: 'pointer',
              background: activeTab === 'dashboard' ? 'white' : 'transparent',
              color: activeTab === 'dashboard' ? '#16a34a' : '#4b5563',
              boxShadow: activeTab === 'dashboard' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none'
            }}
          >
            📊 Dashboard
          </button>
          <button
            onClick={() => setActiveTab('report')}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              fontWeight: 500,
              border: 'none',
              cursor: 'pointer',
              background: activeTab === 'report' ? 'white' : 'transparent',
              color: activeTab === 'report' ? '#16a34a' : '#4b5563',
              boxShadow: activeTab === 'report' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none'
            }}
          >
            📄 Report
          </button>
        </div>

        {!data ? (
          <div style={{
            background: 'white',
            borderRadius: '12px',
            padding: '48px',
            textAlign: 'center',
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
          }}>
            <div style={{ fontSize: '64px', marginBottom: '16px' }}>📤</div>
            <h3 style={{ fontSize: '20px', fontWeight: 600, color: '#374151', marginBottom: '8px' }}>
              No Data Loaded
            </h3>
            <p style={{ color: '#6b7280', marginBottom: '24px' }}>
              Upload a CSV file or load sample data to get started
            </p>
            <p style={{ fontSize: '14px', color: '#9ca3af' }}>
              Expected CSV columns: date, co2_injection, co2_production (in kg)
            </p>
          </div>
        ) : activeTab === 'dashboard' ? (
          <Dashboard data={data} metrics={metrics} />
        ) : (
          <ReportView data={data} metrics={metrics} />
        )}
      </div>
    </div>
  );

}
