import { NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';

export async function POST() {
    // This promise-based function to run the Python script remains the same
    const runTradingScript = (): Promise<string> => {
        return new Promise((resolve, reject) => {
            const scriptPath = path.resolve(process.cwd(), '..', 'python_scripts', 'main.py');
            const pythonProcess = spawn('python3', [scriptPath]);
            let stdout = '';
            let stderr = '';
            pythonProcess.stdout.on('data', (data) => {
                stdout += data.toString();
            });
            pythonProcess.stderr.on('data', (data) => {
                stderr += data.toString();
            });
            pythonProcess.on('close', (code) => {
                if (code !== 0) {
                    console.error(`Python script exited with code ${code}: ${stderr}`);
                    return reject(new Error(stderr || `Python script failed with code ${code}`));
                }
                resolve(stdout);
            });
            pythonProcess.on('error', (error) => {
                console.error('Failed to start Python process:', error);
                reject(error);
            });
        });
    };

    try {
        const rawOutput = await runTradingScript();
        console.log("--- RAW PYTHON SCRIPT OUTPUT ---");
        console.log(rawOutput);
        console.log("--- END OF RAW OUTPUT ---");
        // ---vvv--- NEW ROBUST PARSING LOGIC ---vvv---
        // Find the start of the JSON object.
        const jsonStart = rawOutput.indexOf('{');

        if (jsonStart === -1) {
            console.error("Could not find a valid JSON object in the Python script output.");
            console.error("Raw Output:", rawOutput); // Log the problematic output
            throw new Error("Invalid or incomplete output from the AI trading script.");
        }

        // Extract the substring from the first '{' to the end.
        const jsonString = rawOutput.substring(jsonStart);
        // ---^^^----------------------------------^^^---

        // Return the CLEANED output to the frontend.
        return NextResponse.json({ output: jsonString });

    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'An unknown error occurred.';
        return NextResponse.json({ error: errorMessage }, { status: 500 });
    }
}