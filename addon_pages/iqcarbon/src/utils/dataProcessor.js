export function processData(rawData) {
  const processed = rawData.map(row => ({
    date: row.date || row.Date,
    injection: parseFloat(row.co2_injection || row.injection || 0),
    production: parseFloat(row.co2_production || row.production || 0),
    net: parseFloat(row.co2_injection || row.injection || 0) - parseFloat(row.co2_production || row.production || 0)
  }));

  const totalInjection = processed.reduce((sum, d) => sum + d.injection, 0);
  const totalProduction = processed.reduce((sum, d) => sum + d.production, 0);
  const netCapture = totalInjection - totalProduction;
  const efficiency = totalInjection > 0 ? ((netCapture / totalInjection) * 100).toFixed(1) : 0;
  
  const estimatedCredits = (netCapture / 1000).toFixed(2);
  const estimatedValue = (estimatedCredits * 15).toFixed(2);

  return {
    processedData: processed,
    calculatedMetrics: {
      totalInjection: totalInjection.toFixed(2),
      totalProduction: totalProduction.toFixed(2),
      netCapture: netCapture.toFixed(2),
      efficiency,
      estimatedCredits,
      estimatedValue,
      dataPoints: processed.length
    }
  };
}
