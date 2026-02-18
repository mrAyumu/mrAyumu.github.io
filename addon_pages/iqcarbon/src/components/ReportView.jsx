import React from 'react';
import { Download } from 'lucide-react';
import { generateReport } from '../utils/reportGenerator';

export default function ReportView({ data, metrics }) {
  const handleDownload = () => {
    const report = generateReport(data, metrics);
    const blob = new Blob([report], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `carboniq-report-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ background: 'white', borderRadius: '12px', padding: '32px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h3 style={{ fontSize: '20px', fontWeight: 600, color: '#111827' }}>Carbon Monitoring Report</h3>
        <button
          onClick={handleDownload}
          style={{
            padding: '8px 16px',
            background: '#16a34a',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontWeight: 500
          }}
        >
          <Download size={18} />
          Download Report
        </button>
      </div>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', color: '#374151' }}>
        <div>
          <h4 style={{ fontWeight: 600, fontSize: '18px', marginBottom: '12px' }}>Executive Summary</h4>
          <div style={{ background: '#f9fafb', padding: '16px', borderRadius: '8px' }}>
            <p style={{ marginBottom: '8px' }}><strong>Total CO2 Injected:</strong> {metrics.totalInjection} kg</p>
            <p style={{ marginBottom: '8px' }}><strong>Total CO2 Produced:</strong> {metrics.totalProduction} kg</p>
            <p style={{ marginBottom: '8px' }}><strong>Net CO2 Captured:</strong> {metrics.netCapture} kg</p>
            <p><strong>Storage Efficiency:</strong> {metrics.efficiency}%</p>
          </div>
        </div>

        <div>
          <h4 style={{ fontWeight: 600, fontSize: '18px', marginBottom: '12px' }}>Carbon Credit Estimation</h4>
          <div style={{ background: '#f0fdf4', padding: '16px', borderRadius: '8px' }}>
            <p style={{ marginBottom: '8px' }}><strong>Estimated Carbon Credits:</strong> {metrics.estimatedCredits} credits</p>
            <p style={{ marginBottom: '8px' }}><strong>Estimated Market Value:</strong> ${metrics.estimatedValue} USD</p>
            <p style={{ fontSize: '14px', color: '#4b5563', marginTop: '8px' }}>
              * Based on average market rate of $15/credit. Actual credits require verification under approved methodologies.
            </p>
          </div>
        </div>

        <div>
          <h4 style={{ fontWeight: 600, fontSize: '18px', marginBottom: '12px' }}>Recommendations</h4>
          <div style={{ background: '#eff6ff', padding: '16px', borderRadius: '8px' }}>
            <p style={{ marginBottom: '8px' }}>✓ Storage efficiency is {metrics.efficiency > 90 ? 'excellent' : metrics.efficiency > 80 ? 'good' : 'acceptable'}</p>
            {metrics.efficiency < 80 && <p style={{ marginBottom: '8px' }}>⚠ Consider investigating production/leakage sources</p>}
            <p style={{ marginBottom: '8px' }}>✓ Continue monitoring for credit verification purposes</p>
            <p>✓ Maintain detailed records for auditing</p>
          </div>
        </div>
      </div>
    </div>
  );
}
