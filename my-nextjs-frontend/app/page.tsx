// my-nextjs-frontend/app/page.tsx
'use client';

import { useState } from 'react';
import styles from './page.module.css';

// --- Import charting components ---
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale, // Use TimeScale for accurate time-based charts
  Filler,   // Import Filler for gradient fills
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import 'chartjs-adapter-date-fns'; // Adapter for time scale functionality

// --- Register Chart.js components we will use ---
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale, // Register the time scale
  Filler    // Register the filler plugin
);


// --- TYPE DEFINITIONS ---
// Defines the structure for a single trading decision
interface Decision {
  symbol: string;
  action: string;
  confidence: string;
  quantity: string;
}

// Defines the structure for the portfolio details (string keys, string values)
type Portfolio = Record<string, string>;

// Defines the structure for a single historical data point for the chart
interface HistoryPoint {
  timestamp: string; // ISO 8601 format string (e.g., "2023-10-27T10:00:00Z")
  value: number;
}


// --- Reusable Chart Component ---
function PortfolioChart({ data }: { data: HistoryPoint[] }) {
  const chartData = {
    // Labels are not needed when using a time scale with {x, y} data points
    datasets: [
      {
        fill: true, // Enable the gradient fill
        label: 'Portfolio Value ($)',
        data: data.map(point => ({ x: new Date(point.timestamp), y: point.value })), // Convert timestamp string to Date object
        borderColor: 'rgb(75, 192, 192)',
        backgroundColor: 'rgba(75, 192, 192, 0.2)', // Fallback color
        tension: 0.1,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false, // Allows chart to fill container height
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: true,
        text: 'Portfolio Value Over Time',
        font: { size: 18 }
      },
    },
    scales: {
      x: {
        type: 'time' as const, // Set the x-axis to a time scale
        time: {
          tooltipFormat: 'MMM dd, yyyy HH:mm', // Format for tooltips
          unit: 'minute' as const, // Dynamically set this based on data span for better results
        },
        title: {
          display: true,
          text: 'Date'
        },
        grid: {
          display: false, // Cleaner look
        }
      },
      y: {
        title: {
          display: true,
          text: 'Value ($)'
        },
        ticks: {
          // Format ticks to include a dollar sign
          callback: function (value: string | number) {
            return '$' + value;
          }
        }
      }
    }
  };

  return <Line options={options} data={chartData} />;
}


// --- THE MAIN PAGE COMPONENT ---
export default function Home() {
  // --- STATE MANAGEMENT ---
  const [reasoning, setReasoning] = useState<string>('');
  const [summary, setSummary] = useState<string>('');
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Parses the raw string output from the Python script to populate all component states.
   * @param output The raw string response from the backend.
   */
  const parseOutput = (output: string) => {
    // Reset states to avoid showing stale data from previous runs
    setReasoning(''); setSummary(''); setDecisions([]); setPortfolio(null); setHistory([]);

    const reasoningMatch = output.match(/<thinking>([\s\S]*?)<\/thinking>/);
    setReasoning(reasoningMatch ? reasoningMatch[1].trim() : 'No reasoning block found.');
    const decisionText = reasoningMatch ? output.substring(output.indexOf('</thinking>') + 11).trim() : output;
    const lines = decisionText.split('\n').filter(line => line.trim() !== '');

    // --- Parse Summary and Decisions ---
    const decisionsHeaderIndex = lines.findIndex(line => line.includes('--- FINAL DECISIONS ---'));
    if (decisionsHeaderIndex !== -1) {
      // Logic to parse summary and decisions table
    }

    // --- Parse Final Portfolio Status ---
    const portfolioHeaderIndex = lines.findIndex(line => line.includes('5. Final Portfolio Status...'));
    if (portfolioHeaderIndex !== -1) {
      const portfolioDetails: Portfolio = {};
      for (let i = portfolioHeaderIndex + 1; i < lines.length && !lines[i].includes('---'); i++) {
        const [key, ...valueParts] = lines[i].split(':');
        if (key && valueParts.length > 0) {
          portfolioDetails[key.trim()] = valueParts.join(':').trim();
        }
      }
      setPortfolio(portfolioDetails);
    }

    // --- Parse Portfolio History ---
    const historyHeaderIndex = lines.findIndex(line => line.includes('--- PORTFOLIO HISTORY ---'));
    if (historyHeaderIndex !== -1 && lines[historyHeaderIndex + 1]) {
      try {
        const historyJsonString = lines[historyHeaderIndex + 1];
        const historyData: HistoryPoint[] = JSON.parse(historyJsonString);
        if (Array.isArray(historyData)) {
          setHistory(historyData);
        }
      } catch (e) {
        console.error("Failed to parse portfolio history JSON:", e);
      }
    }
  };

  /**
   * Handles the button click to trigger the trading process via the API.
   */
  const handleTrade = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/trade', { method: 'POST' });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch trading decision from the server.');
      }
      parseOutput(data.output);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className={styles.main}>
      <div className={styles.container}>
        <h1 className={styles.title}>AI Trading Assistant</h1>
        <p className={styles.description}>
          Click the button to run the AI trading logic. The portfolio state and value history are saved and loaded between runs.
        </p>

        <button onClick={handleTrade} disabled={loading} className={styles.tradeButton}>
          {loading ? 'Processing...' : 'Execute Next Trade Cycle'}
        </button>

        {loading && <p className={styles.loadingText}>Fetching market data and thinking...</p>}
        {error && <div className={styles.error}><pre>Error: {error}</pre></div>}

        {!loading && !error && (
          <>
            {/* --- Render the chart if there's enough data (at least 2 points) --- */}
            {history.length > 1 && (
              <div className={styles.chartContainer}>
                <PortfolioChart data={history} />
              </div>
            )}

            {portfolio && Object.keys(portfolio).length > 0 && (
              <div className={styles.resultsContainer}>
                <h2>Current Portfolio Status</h2>
                <ul className={styles.portfolioList}>
                  {Object.entries(portfolio).map(([key, value]) => (
                    <li key={key}><strong>{key}:</strong> {value}</li>
                  ))}
                </ul>
              </div>
            )}

            {decisions.length > 0 && (
              <div className={styles.resultsContainer}>
                <h2>AI Decisions for this Cycle</h2>
                <table className={styles.table}>
                  {/* ... table rendering ... */}
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