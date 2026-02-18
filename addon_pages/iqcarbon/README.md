# CarbonIQ

CO2 Injection & Carbon Credit Tracking Dashboard

## Features

- 📊 Real-time CO2 monitoring dashboard
- 📈 Visual analytics with charts
- 💰 Carbon credit estimation
- 📄 Downloadable reports
- 📤 CSV data import

## Getting Started

### Prerequisites

- Node.js 18+ and npm

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/carboniq.git
cd carboniq
```

2. Install dependencies:
```bash
npm install
```

3. Start development server:
```bash
npm run dev
```

4. Open your browser to `http://localhost:5173`

## Building for Production
```bash
npm run build
```

The production build will be in the `dist/` folder.

## Deploying to GitHub Pages

1. Update `vite.config.js` with your repository name:
```javascript
base: '/your-repo-name/',
```

2. Deploy:
```bash
npm run deploy
```

## CSV Format

Your CSV should have these columns:
- **date**: Period identifier (any format)
- **co2_injection**: CO2 injected in kg
- **co2_production**: CO2 produced/leaked in kg

## Tech Stack

- React 18
- Vite
- Recharts (charts)
- Lucide React (icons)
