'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import styles from './page.module.css';

// --- Import charting components ---
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, TimeScale, Filler, ScriptableContext
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


// --- Reusable Chart Component (MODIFIED) ---
function PortfolioChart({ data }: { data: HistoryPoint[] }) {

  const createGradient = (ctx: CanvasRenderingContext2D) => {
    const gradient = ctx.createLinearGradient(0, 0, 0, 400);

    if (typeof window !== 'undefined') {
      const primaryBlueRgb = getComputedStyle(document.documentElement).getPropertyValue('--primary-blue-rgb').trim();
      gradient.addColorStop(0, `rgba(${primaryBlueRgb}, 0.4)`);
      gradient.addColorStop(1, `rgba(${primaryBlueRgb}, 0)`);
    } else {
      gradient.addColorStop(0, 'rgba(0, 122, 255, 0.4)');
      gradient.addColorStop(1, 'rgba(0, 122, 255, 0)');
    }

    return gradient;
  };

  const chartData = useMemo(() => ({
    datasets: [{
      label: 'Portfolio Value ($)',
      data: data.map(point => ({ x: new Date(point.timestamp), y: point.value })),
      fill: true,
      backgroundColor: (context: ScriptableContext<"line">) => {
        const ctx = context.chart.ctx;
        if (!ctx) return 'rgba(75, 192, 192, 0.2)'; // Fallback
        return createGradient(ctx);
      },
      borderColor: 'var(--primary-blue)',
      segment: {
        borderColor: (ctx: any) => {
          const y1 = ctx.p0.parsed.y;
          const y2 = ctx.p1.parsed.y;
          if (y2 > y1) return 'var(--success)';
          if (y2 < y1) return 'var(--danger)';
          return 'var(--gray-400)';
        }
      },
      tension: 0.2,
      pointRadius: 2,
      pointHoverRadius: 6,
      pointBackgroundColor: 'var(--primary-blue)',
    }],
  }), [data]);

  const options = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
        labels: { color: 'var(--foreground)', font: { size: 14 } }
      },
      title: {
        display: false, // Title is now handled in the component's header
      },
      tooltip: {
        mode: 'index' as const,
        intersect: false,
        backgroundColor: 'var(--container-bg)',
        titleColor: 'var(--foreground)',
        bodyColor: 'var(--gray-400)',
        borderColor: 'var(--border-color)',
        borderWidth: 1,
      }
    },
    scales: {
      x: {
        type: 'time' as const,
        time: { tooltipFormat: 'MMM dd, yyyy HH:mm', unit: 'minute' as const },
        title: { display: true, text: 'Date', color: 'var(--foreground)' },
        grid: { color: 'var(--border-color)' },
        ticks: { color: 'var(--gray-400)' }
      },
      y: {
        title: { display: true, text: 'Value ($)', color: 'var(--foreground)' },
        grid: { color: 'var(--border-color)' },
        ticks: {
          color: 'var(--gray-400)',
          callback: (value: string | number) => '$' + Number(value).toLocaleString()
        },
      },
    },
  }), []);

  return <Line options={options} data={chartData} />;
}


// --- MAIN PAGE COMPONENT ---
export default function Home() {
  const [reasoning, setReasoning] = useState<string>('');
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [portfolioSummary, setPortfolioSummary] = useState<PortfolioSummary | null>(null);
  const [portfolioPositions, setPortfolioPositions] = useState<Position[]>([]);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [tradeHistory, setTradeHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'reasoning' | 'history'>('reasoning');
  const [timeRange, setTimeRange] = useState<'all' | '72h'>('all');

  const parseOutput = (output: string) => {
    try {
      const data = JSON.parse(output);
      setReasoning(data.reasoning || 'No reasoning provided.');
      setDecisions(data.decisions || []);
      setPortfolioSummary(data.portfolio_summary || null);
      setPortfolioPositions(data.portfolio_positions || []);
      setHistory(data.history || []);
      setTradeHistory(data.trade_history || []);
    } catch (e) {
      console.error("Failed to parse JSON output from backend:", e);
      setError("Failed to parse the data from the AI. The output might be malformed.");
      setReasoning(''); setDecisions([]); setPortfolioSummary(null); setPortfolioPositions([]); setHistory([]);
    }
  };

  const handleTrade = useCallback(async () => {
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
  }, []);

  useEffect(() => {
    handleTrade();
    const FOUR_MINUTES_IN_MS = 4 * 60 * 1000;
    const intervalId = setInterval(handleTrade, FOUR_MINUTES_IN_MS);
    return () => clearInterval(intervalId);
  }, [handleTrade]);

  const getPnlClass = (pnl: string) => {
    const value = parseFloat(pnl.replace(/[^-\d.]/g, ''));
    if (value > 0) return styles.pnlPositive;
    if (value < 0) return styles.pnlNegative;
    return '';
  };

  const filteredHistory = useMemo(() => {
    if (timeRange === '72h') {
      const seventyTwoHoursAgo = new Date(Date.now() - 72 * 60 * 60 * 1000);
      return history.filter(point => new Date(point.timestamp) >= seventyTwoHoursAgo);
    }
    return history;
  }, [history, timeRange]);

  const MemoizedPortfolioChart = useMemo(() => <PortfolioChart data={filteredHistory} />, [filteredHistory]);

  return (
    <main className={styles.main}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>AI Trading Assistant</h1>
          <p className={styles.description}>
            AI-driven analysis and automated trade execution, refreshing every 4 minutes.
          </p>
        </div>
        <div className={styles.status}>
          {loading && <div className={styles.loadingIndicator}>Running Analysis...</div>}
        </div>
      </header>

      {error && <div className={styles.error}><pre>Error: {error}</pre></div>}

      <div className={styles.dashboardLayout}>

        {/* --- MAIN CONTENT --- */}
        <div className={styles.mainContent}>
          <div className={styles.card}>
            <div className={styles.chartHeader}>
              <h2>Portfolio Performance</h2>
              <div className={styles.timeWindowControls}>
                <button
                  onClick={() => setTimeRange('72h')}
                  className={timeRange === '72h' ? styles.activeTimeButton : styles.timeButton}
                >
                  72H
                </button>
                <button
                  onClick={() => setTimeRange('all')}
                  className={timeRange === 'all' ? styles.activeTimeButton : styles.timeButton}
                >
                  All Time
                </button>
              </div>
            </div>
            <div className={styles.chartContainer}>
              {filteredHistory.length > 1 ? (
                MemoizedPortfolioChart
              ) : (
                <div className={styles.placeholder}>
                  {loading ? <p>Running first analysis cycle...</p> : <p>Waiting for more data to generate the portfolio chart.</p>}
                </div>
              )}
            </div>
          </div>

          {decisions.length > 0 && (
            <div className={styles.card}>
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
        </div>


        {/* --- SIDEBAR --- */}
        <div className={styles.sidebar}>
          {portfolioSummary && (
            <div className={styles.card}>
              <h2>Portfolio Summary</h2>
              <ul className={styles.portfolioList}>
                {Object.entries(portfolioSummary).map(([key, value]) => (
                  <li key={key}><span>{key.replace(/_/g, ' ')}</span> <strong>{value}</strong></li>
                ))}
              </ul>
            </div>
          )}

          {portfolioPositions.length > 0 && (
            <div className={styles.card}>
              <h2>Current Positions</h2>
              <div className={styles.tableContainer}>
                <table className={`${styles.table} ${styles.positionsTable}`}>
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
                        <td data-label="SIDE">{pos.side}</td>
                        <td data-label="COIN">{pos.coin}</td>
                        <td data-label="LEVERAGE">{pos.leverage}</td>
                        <td data-label="NOTIONAL">{pos.notional}</td>
                        <td data-label="EXIT PLAN">{pos.exit_plan}</td>
                        <td data-label="UNREAL P&L" className={getPnlClass(pos.unreal_pnl)}>{pos.unreal_pnl}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className={styles.card}>
            <div className={styles.tabHeader}>
              <button
                className={`${styles.tabButton} ${activeTab === 'reasoning' ? styles.activeTab : ''}`}
                onClick={() => setActiveTab('reasoning')}
              >
                AI's Thought Process
              </button>
              <button
                className={`${styles.tabButton} ${activeTab === 'history' ? styles.activeTab : ''}`}
                onClick={() => setActiveTab('history')}
              >
                Trade History
              </button>
            </div>

            <div className={styles.tabContent}>
              {activeTab === 'reasoning' && (
                <pre className={styles.codeBlock}>{reasoning || "No reasoning available for this cycle."}</pre>
              )}

              {activeTab === 'history' && (
                <div className={styles.tradeHistory}>
                  {tradeHistory.length > 0 ? tradeHistory.slice().reverse().map((trade, index) => (
                    <div key={index} className={styles.tradeHistoryItem}>
                      <div className={styles.tradeHistoryHeader}>
                        <span className={styles.tradeTimestamp}>{new Date(trade.timestamp).toLocaleString()}</span>
                        <span className={styles.portfolioValue}>${trade.portfolio_value.toLocaleString()}</span>
                      </div>
                      <details className={styles.tradeDetails}>
                        <summary>View Details</summary>
                        <div className={styles.tradeDecisions}>
                          {trade.decisions.map((decision: Decision, dIndex: number) => (
                            <div key={dIndex} className={styles.decision}>
                              <strong>{decision.symbol}:</strong> {decision.action} {decision.quantity} ({decision.confidence})
                            </div>
                          ))}
                        </div>
                        <pre className={styles.reasoningDetail}>{trade.reasoning}</pre>
                      </details>
                    </div>
                  )) : <p>No trade history available.</p>}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}