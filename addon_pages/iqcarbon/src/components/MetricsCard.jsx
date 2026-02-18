import React from 'react';

export default function MetricsCard({ title, value, unit, color = '#111827' }) {
  return (
    <div style={{
      background: 'white',
      borderRadius: '12px',
      padding: '24px',
      boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
    }}>
      <p style={{ fontSize: '14px', color: '#6b7280', marginBottom: '4px' }}>{title}</p>
      <p style={{ fontSize: '30px', fontWeight: 'bold', color }}>{value}</p>
      <p style={{ fontSize: '12px', color: '#9ca3af', marginTop: '4px' }}>{unit}</p>
    </div>
  );
}
