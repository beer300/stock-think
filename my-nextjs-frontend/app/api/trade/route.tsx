// my-nextjs-frontend/app/api/trade/route.ts
import { NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';

// This function will handle POST requests to /api/trade
export async function POST() {
    // A promise-based function to run the Python script
    const runTradingScript = (): Promise<string> => {
        return new Promise((resolve, reject) => {
            // Define the path to the Python script relative to the entire project structure.
            // process.cwd() is the root of the Next.js app (`/my-nextjs-frontend`).
            // We go one level up ('..') and then into `/python_scripts`.
            const scriptPath = path.resolve(process.cwd(), '..', 'python_scripts', 'trading_assistant.py');

            // Use 'python3' or 'python' depending on your system configuration
            const pythonProcess = spawn('python3', [scriptPath]);

            let stdout = '';
            let stderr = '';

            // Capture standard output
            pythonProcess.stdout.on('data', (data) => {
                stdout += data.toString();
            });

            // Capture standard error
            pythonProcess.stderr.on('data', (data) => {
                stderr += data.toString();
            });

            // Handle the script exit event
            pythonProcess.on('close', (code) => {
                if (code !== 0) {
                    console.error(`Python script exited with code ${code}: ${stderr}`);
                    // Reject the promise with the error message from stderr
                    return reject(new Error(stderr || `Python script failed with code ${code}`));
                }
                // Resolve the promise with the captured standard output
                resolve(stdout);
            });

            // Handle potential errors when spawning the process
            pythonProcess.on('error', (error) => {
                console.error('Failed to start Python process:', error);
                reject(error);
            });
        });
    };

    try {
        // Await the result from the Python script
        const output = await runTradingScript();
        // Return the output in a JSON response with a 200 OK status
        return NextResponse.json({ output });
    } catch (error) {
        // If an error occurs, return it in a JSON response with a 500 Internal Server Error status
        const errorMessage = error instanceof Error ? error.message : 'An unknown error occurred.';
        return NextResponse.json({ error: errorMessage }, { status: 500 });
    }
}