import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Competitor Intelligence Tracker — SOHO",
  description: "Monitor competitor hotel websites and estimate organic search traffic",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50">
        <nav className="bg-white border-b border-slate-200 px-6 py-3 flex items-center gap-6 shadow-sm">
          <span className="font-bold text-brand-700 text-lg tracking-tight">
            SOHO · Competitor Intelligence
          </span>
          <a href="/" className="text-sm text-slate-600 hover:text-brand-600 transition-colors">
            Overview
          </a>
          <a href="/comparison" className="text-sm text-slate-600 hover:text-brand-600 transition-colors">
            Traffic Comparison
          </a>
          <a href="/keywords" className="text-sm text-slate-600 hover:text-brand-600 transition-colors">
            Keywords
          </a>
          <a href="/tech" className="text-sm text-slate-600 hover:text-brand-600 transition-colors">
            Tech Stack
          </a>
          <a href="/changes" className="text-sm text-slate-600 hover:text-brand-600 transition-colors">
            Change Log
          </a>
        </nav>

        <main className="max-w-7xl mx-auto px-6 py-8">{children}</main>

        <footer className="border-t border-slate-200 bg-white mt-12 px-6 py-4 text-center">
          <p className="text-xs text-slate-500">
            ⚠️ Traffic data is estimated from search engine rankings and public keyword volume data.
            It does <strong>not</strong> represent actual analytics. Accuracy range: ±7–11%.
          </p>
        </footer>
      </body>
    </html>
  );
}
