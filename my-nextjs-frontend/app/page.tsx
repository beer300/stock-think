// my-nextjs-frontend/app/page.tsx
'use client';

import { useState } from 'react';
import styles from './page.module.css';

// --- Import charting components ---
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, TimeScale, Filler,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import 'chartjs-adapter-date-fns';

// --- Register Chart.js components ---
ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, TimeScale, Filler
);

// --- TYPE DEFINITIONS ---
interface Decision {
  symbol: string;
  action: string;
  confidence: string;
  quantity: number | string;
  exit_plan: string;
}

interface Position {
  side: string;
  coin: string;
  leverage: string;
  notional: string;
  unreal_pnl: string;
  exit_plan: string;
}

type PortfolioSummary = Record<string, string>;

interface HistoryPoint {
  timestamp: string;
  value: number;
}

// --- Reusable Chart Component ---
function PortfolioChart({ data }: { data: HistoryPoint[] }) {
  const chartData = {
    datasets: [{
      fill: true,
      label: 'Portfolio Value ($)',
      data: data.map(point => ({ x: new Date(point.timestamp), y: point.value })),
      borderColor: 'rgb(75, 192, 192)',
      backgroundColor: 'rgba(75, 192, 192, 0.2)',
      tension: 0.1,
    }],
  };
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'top' as const },
      title: { display: true, text: 'Portfolio Value Over Time', font: { size: 18 } },
    },
    scales: {
      x: {
        type: 'time' as const,
        time: { tooltipFormat: 'MMM dd, yyyy HH:mm', unit: 'minute' as const },
        title: { display: true, text: 'Date' },
        grid: { display: false },
      },
      y: {
        title: { display: true, text: 'Value ($)' },
        ticks: { callback: (value: string | number) => '$' + value },
      },
    },
  };
  return <Line options={options} data={chartData} />;
}

// --- MAIN PAGE COMPONENT ---
export default function Home() {
  const [reasoning, setReasoning] = useState<string>('');
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [portfolioSummary, setPortfolioSummary] = useState<PortfolioSummary | null>(null);
  const [portfolioPositions, setPortfolioPositions] = useState<Position[]>([]);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const parseOutput = (output: string) => {
    try {
      const data = JSON.parse(output);
      setReasoning(data.reasoning || 'No reasoning provided.');
      setDecisions(data.decisions || []);
      setPortfolioSummary(data.portfolio_summary || null);
      setPortfolioPositions(data.portfolio_positions || []);
      setHistory(data.history || []);
    } catch (e) {
      console.error("Failed to parse JSON output from backend:", e);
      setError("Failed to parse the data from the AI. The output might be malformed.");
      // Clear old data to avoid confusion
      setReasoning(''); setDecisions([]); setPortfolioSummary(null); setPortfolioPositions([]); setHistory([]);
    }
  };

  const handleTrade = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/trade', { method: 'POST' });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch trading decision.');
      }
      parseOutput(data.output);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred.');
    } finally {
      setLoading(false);
    }
  };

  // Helper to determine P&L color
  const getPnlClass = (pnl: string) => {
    const value = parseFloat(pnl.replace(/[^-\d.]/g, ''));
    if (value > 0) return styles.pnlPositive;
    if (value < 0) return styles.pnlNegative;
    return '';
  };

  return (
    <main className={styles.main}>
      <div className={styles.container}>
        <h1 className={styles.title}>AI Trading Assistant</h1>
        <p className={styles.description}>
          Click the button to run the AI trading logic. Portfolio state and history are saved between runs.
        </p>
        <button onClick={handleTrade} disabled={loading} className={styles.tradeButton}>
          {loading ? 'Processing...' : 'Execute Next Trade Cycle'}
        </button>
        {loading && <p className={styles.loadingText}>Fetching market data and thinking...</p>}
        {error && <div className={styles.error}><pre>Error: {error}</pre></div>}
        {!loading && !error && (
          <>
            {history.length > 1 && (
              <div className={styles.chartContainer}>
                <PortfolioChart data={history} />
              </div>
            )}

            {portfolioSummary && Object.keys(portfolioSummary).length > 0 && (
              <div className={styles.resultsContainer}>
                <h2>Portfolio Summary</h2>
                <ul className={styles.portfolioList}>
                  {Object.entries(portfolioSummary).map(([key, value]) => (
                    <li key={key}><strong>{key}:</strong> {value}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* NEW: Detailed Portfolio Positions Table */}
            {portfolioPositions.length > 0 && (
              <div className={styles.resultsContainer}>
                <h2>Current Positions</h2>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>SIDE</th>
                      <th>COIN</th>
                      <th>LEVERAGE</th>
                      <th>NOTIONAL</th>
                      <th>EXIT PLAN</th>
                      <th>UNREAL P&L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {portfolioPositions.map((pos, index) => (
                      <tr key={index}>
                        <td>{pos.side}</td>
                        <td>{pos.coin}</td>
                        <td>{pos.leverage}</td>
                        <td>{pos.notional}</td>
                        <td>{pos.exit_plan}</td>
                        <td className={getPnlClass(pos.unreal_pnl)}>{pos.unreal_pnl}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {decisions.length > 0 && (
              <div className={styles.resultsContainer}>
                <h2>AI Decisions for this Cycle</h2>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>SYMBOL</th>
                      <th>ACTION</th>
                      <th>CONFIDENCE</th>
                      <th>QUANTITY</th>
                      <th>EXIT PLAN</th>
                    </tr>
                  </thead>
                  <tbody>
                    {decisions.map((d, index) => (
                      <tr key={index}>
                        <td>{d.symbol}</td>
                        <td>{d.action}</td>
                        <td>{d.confidence}</td>
                        <td>{d.quantity}</td>
                        <td>{d.exit_plan}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {reasoning && (
              <div className={styles.resultsContainer}>
                <h2>AI's Thought Process</h2>
                <pre className={styles.codeBlock}>{reasoning}</pre>
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}