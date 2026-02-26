import React, { useState } from 'react';
import Header from './components/Header.jsx';
import Dashboard from './components/Dashboard.jsx';
import ReportView from './components/ReportView.jsx';
import { processData } from './utils/dataProcessor.js';
import { Upload, FileText, TrendingUp, Download, BarChart3, AlertCircle } from 'lucide-react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

export default function App() {
  const [data, setData] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [error, setError] = useState(null);
  const [uploading, setUploading] = useState(false);

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploading(true);
    setError(null);

    try {
      // Validate file type
      if (!file.name.endsWith('.csv')) {
        throw new Error('Please upload a CSV file');
      }

      const text = await file.text();
      
      // Check if file is empty
      if (!text.trim()) {
        throw new Error('The CSV file is empty');
      }

      const lines = text.split('\n').filter(line => line.trim());
      
      if (lines.length < 2) {
        throw new Error('CSV file must have at least a header row and one data row');
      }

      // Parse header
      const headers = lines[0].split(',').map(h => h.trim().toLowerCase());
      
      console.log('CSV Headers found:', headers);

      // Validate required columns
      const hasDate = headers.some(h => h.includes('date'));
      const hasInjection = headers.some(h => h.includes('injection') || h.includes('inject'));
      const hasProduction = headers.some(h => h.includes('production') || h.includes('produce'));

      if (!hasDate || !hasInjection || !hasProduction) {
        throw new Error(
          `Missing required columns. Found: ${headers.join(', ')}. ` +
          `Need columns containing: 'date', 'injection', 'production'`
        );
      }

      // Parse data rows
      const parsed = lines.slice(1).map((line, index) => {
        const values = line.split(',').map(v => v.trim());
        const obj = {};
        headers.forEach((header, i) => {
          obj[header] = values[i] || '';
        });
        return obj;
      }).filter(row => {
        // Filter out empty rows
        return Object.values(row).some(val => val !== '');
      });

      if (parsed.length === 0) {
        throw new Error('No valid data rows found in CSV');
      }

      console.log('Parsed rows:', parsed.length);
      console.log('Sample row:', parsed[0]);

      processData(parsed);
      setUploading(false);
      
    } catch (err) {
      console.error('Upload error:', err);
      setError(err.message);
      setUploading(false);
    }

    // Reset file input
    e.target.value = '';
  };

  const processData = (rawData) => {
    try {
      // Find the actual column names (case-insensitive, flexible matching)
      const firstRow = rawData[0];
      const keys = Object.keys(firstRow);
      
      const dateKey = keys.find(k => k.toLowerCase().includes('date'));
      const injectionKey = keys.find(k => 
        k.toLowerCase().includes('injection') || 
        k.toLowerCase().includes('inject') ||
        k.toLowerCase().includes('co2_injection')
      );
      const productionKey = keys.find(k => 
        k.toLowerCase().includes('production') || 
        k.toLowerCase().includes('produce') ||
        k.toLowerCase().includes('co2_production')
      );

      console.log('Using columns:', { dateKey, injectionKey, productionKey });

      const processed = rawData.map(row => {
        const injection = parseFloat(row[injectionKey]) || 0;
        const production = parseFloat(row[productionKey]) || 0;
        
        return {
          date: row[dateKey] || 'Unknown',
          injection: injection,
          production: production,
          net: injection - production
        };
      });

      // Calculate metrics
      const totalInjection = processed.reduce((sum, d) => sum + d.injection, 0);
      const totalProduction = processed.reduce((sum, d) => sum + d.production, 0);
      const netCapture = totalInjection - totalProduction;
      const efficiency = totalInjection > 0 ? ((netCapture / totalInjection) * 100).toFixed(1) : 0;
      
      // Carbon credit estimation (1 metric ton CO2 = 1 credit, avg $15/credit)
      const estimatedCredits = (netCapture / 1000).toFixed(2);
      const estimatedValue = (estimatedCredits * 15).toFixed(2);

      setData(processed);
      setMetrics({
        totalInjection: totalInjection.toFixed(2),
        totalProduction: totalProduction.toFixed(2),
        netCapture: netCapture.toFixed(2),
        efficiency,
        estimatedCredits,
        estimatedValue,
        dataPoints: processed.length
      });
      setError(null);

      console.log('Processing complete! Metrics:', {
        totalInjection,
        totalProduction,
        netCapture,
        efficiency
      });

    } catch (err) {
      console.error('Processing error:', err);
      setError('Error processing data: ' + err.message);
    }
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
