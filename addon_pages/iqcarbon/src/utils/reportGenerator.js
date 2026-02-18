export function generateReport(data, metrics) {
  return `
CARBONIQ MONITORING REPORT
Generated: ${new Date().toLocaleDateString()}

═══════════════════════════════════════════════════

EXECUTIVE SUMMARY
═══════════════════════════════════════════════════

Total CO2 Injected: ${metrics.totalInjection} kg
Total CO2 Produced: ${metrics.totalProduction} kg
Net CO2 Captured: ${metrics.netCapture} kg
Storage Efficiency: ${metrics.efficiency}%

Reporting Period: ${data[0]?.date} to ${data[data.length - 1]?.date}
Data Points Analyzed: ${metrics.dataPoints}

═══════════════════════════════════════════════════

CARBON CREDIT ESTIMATION
═══════════════════════════════════════════════════

Estimated Carbon Credits: ${metrics.estimatedCredits} credits
Estimated Market Value: $${metrics.estimatedValue} USD
(Based on average market rate of $15/credit)

Note: This is a preliminary estimate. Actual carbon 
credits require verification under approved methodologies
(e.g., Verra VCS, Gold Standard).

═══════════════════════════════════════════════════

DETAILED DATA
═══════════════════════════════════════════════════

${data.map(d => `${d.date}: Injection ${d.injection}kg | Production ${d.production}kg | Net ${d.net.toFixed(2)}kg`).join('\n')}

═══════════════════════════════════════════════════

RECOMMENDATIONS
═══════════════════════════════════════════════════

✓ Storage efficiency is ${metrics.efficiency > 90 ? 'excellent' : metrics.efficiency > 80 ? 'good' : 'acceptable'}
${metrics.efficiency < 80 ? '⚠ Consider investigating production/leakage sources' : ''}
✓ Continue monitoring for credit verification purposes
✓ Maintain detailed records for auditing

═══════════════════════════════════════════════════
End of Report
  `.trim();
}
