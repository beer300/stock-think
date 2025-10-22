// my-nextjs-frontend/app/page.tsx
'use client';

import { useState } from 'react';
import styles from './page.module.css';

// --- TYPE DEFINITIONS ---
// Define the structure for a single trading decision
interface Decision {
  symbol: string;
  action: string;
  confidence: string;
  quantity: string;
}

// Define the structure for the portfolio details
// Record<string, string> allows for any string key with a string value.
type Portfolio = Record<string, string>;


// --- THE COMPONENT ---
export default function Home() {
  // --- STATE MANAGEMENT with TypeScript ---
  const [reasoning, setReasoning] = useState<string>('');
  const [summary, setSummary] = useState<string>('');
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Parses the raw string output from the Python script to populate the component's state.
   * @param output The raw string response from the backend.
   */
  const parseOutput = (output: string) => {
    // Extract the <thinking> block for reasoning
    const reasoningMatch = output.match(/<thinking>([\s\S]*?)<\/thinking>/);
    setReasoning(reasoningMatch ? reasoningMatch[1].trim() : 'No reasoning block found.');

    const decisionText = reasoningMatch
      ? output.substring(output.indexOf('</thinking>') + 11).trim()
      : output; // Fallback if <thinking> block is not found

    const lines = decisionText.split('\n').filter(line => line.trim() !== '');

    // --- Parse Summary and Decisions ---
    const decisionsHeaderIndex = lines.findIndex(line => line.includes('--- FINAL DECISIONS ---'));
    if (decisionsHeaderIndex !== -1) {
      const summaryLines = lines.slice(0, decisionsHeaderIndex);
      setSummary(summaryLines.join('\n').trim());

      const decisionsArray: Decision[] = [];
      // Start parsing after the table header and separator lines
      for (let i = decisionsHeaderIndex + 3; i < lines.length && !lines[i].startsWith('Portfolio state has been saved'); i++) {
        if (lines[i].startsWith('|')) {
          const parts = lines[i].split('|').map(p => p.trim()).filter(Boolean);
          if (parts.length === 4) {
            decisionsArray.push({
              symbol: parts[0],
              action: parts[1],
              confidence: parts[2],
              quantity: parts[3],
            });
          }
        }
      }
      setDecisions(decisionsArray);
    }

    // --- Parse Final Portfolio Status ---
    const portfolioHeaderIndex = lines.findIndex(line => line.includes('5. Final Portfolio Status...'));
    if (portfolioHeaderIndex !== -1) {
      const portfolioDetails: Portfolio = {};
      // Start parsing from the line after the header
      for (let i = portfolioHeaderIndex + 1; i < lines.length && !lines[i].includes('Portfolio state has been saved'); i++) {
        const [key, ...valueParts] = lines[i].split(':');
        if (key && valueParts.length > 0) {
          portfolioDetails[key.trim()] = valueParts.join(':').trim();
        }
      }
      setPortfolio(portfolioDetails);
    }
  };

  /**
   * Handles the button click to trigger the trading process.
   */
  const handleTrade = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/trade', {
        method: 'POST',
      });

      const data = await response.json();

      if (!response.ok) {
        // Use the error message from the API response if available
        throw new Error(data.error || 'Failed to fetch trading decision from the server.');
      }

      parseOutput(data.output);

    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('An unexpected error occurred.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className={styles.main}>
      <div className={styles.container}>
        <h1 className={styles.title}>AI Trading Assistant</h1>
        <p className={styles.description}>
          Click the button to run the AI trading logic. The portfolio state is saved and loaded between runs.
        </p>

        <button onClick={handleTrade} disabled={loading} className={styles.tradeButton}>
          {loading ? 'Processing...' : 'Execute Next Trade Cycle'}
        </button>

        {error && <div className={styles.error}><pre>Error: {error}</pre></div>}

        {/* Only render results container if not loading and no error */}
        {!loading && !error && (
          <>
            {reasoning && (
              <div className={styles.resultsContainer}>
                <h2>AI's Thought Process</h2>
                <pre className={styles.codeBlock}>{reasoning}</pre>
              </div>
            )}

            {summary && (
              <div className={styles.resultsContainer}>
                <h2>Strategy Summary</h2>
                <p>{summary}</p>
              </div>
            )}

            {decisions.length > 0 && (
              <div className={styles.resultsContainer}>
                <h2>Final Decisions</h2>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>SYMBOL</th>
                      <th>ACTION</th>
                      <th>CONFIDENCE</th>
                      <th>QUANTITY</th>
                    </tr>
                  </thead>
                  <tbody>
                    {decisions.map((d, index) => (
                      <tr key={index}>
                        <td>{d.symbol}</td>
                        <td>{d.action}</td>
                        <td>{d.confidence}</td>
                        <td>{d.quantity}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {portfolio && Object.keys(portfolio).length > 0 && (
              <div className={styles.resultsContainer}>
                <h2>Final Portfolio Status</h2>
                <ul className={styles.portfolioList}>
                  {Object.entries(portfolio).map(([key, value]) => (
                    <li key={key}><strong>{key}:</strong> {value}</li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}