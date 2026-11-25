import { FiDownload, FiFileText, FiRefreshCw } from 'react-icons/fi';
import { Navbar } from '../components/Navbar';
import { usePollingResource } from '../hooks/usePollingResource';
import { API_URL, getReports } from '../services/api';

export default function ReportsPage() {
  const reports = usePollingResource(getReports, { intervalMs: 30000, initialData: [] });

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <Navbar />
      <main className="mx-auto max-w-7xl space-y-6 px-6 py-10">
        <header className="flex flex-col gap-4 rounded-3xl border border-white/10 bg-white/[0.03] p-6 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-cyan-300">Reports</p>
            <h1 className="mt-2 text-3xl font-black text-white">Generated reports from the existing backend</h1>
            <p className="mt-2 text-sm text-slate-400">This page reuses the `/api/reports` contract and keeps download behavior unchanged.</p>
          </div>
          <button onClick={() => void reports.refetch()} className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-semibold text-slate-100 transition hover:bg-white/10">
            <FiRefreshCw className={reports.status === 'loading' ? 'animate-spin' : ''} /> Refresh
          </button>
        </header>

        <section className="glass-panel rounded-3xl p-6">
          {reports.isLoading ? (
            <div className="py-12 text-center text-slate-400">Loading reports...</div>
          ) : (reports.data?.length ?? 0) === 0 ? (
            <div className="rounded-3xl border border-dashed border-white/10 bg-white/[0.03] p-10 text-center">
              <FiFileText className="mx-auto mb-4 h-10 w-10 text-slate-500" />
              <h2 className="text-lg font-bold text-white">No reports available</h2>
              <p className="mt-2 text-sm text-slate-400">Generate a report from the backend to see it listed here.</p>
            </div>
          ) : (
            <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
              {reports.data?.map((report, index) => (
                <article key={String(report.report_id ?? index)} className="rounded-3xl border border-white/10 bg-slate-900/70 p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-sm font-semibold uppercase tracking-[0.18em] text-cyan-300">Report {index + 1}</p>
                      <h2 className="mt-2 text-lg font-bold text-white">{String(report.report_id ?? 'Untitled report')}</h2>
                    </div>
                    <FiFileText className="mt-1 h-5 w-5 text-cyan-300" />
                  </div>
                  <p className="mt-4 text-sm text-slate-400">Session: {String(report.session_id ?? '—')}</p>
                  <p className="mt-2 text-sm text-slate-400">Generated: {String(report.generated_at ?? report.created_at ?? '—')}</p>
                  <div className="mt-5 flex items-center gap-3">
                    <a href={`${API_URL}/reports/${encodeURIComponent(String(report.report_id ?? ''))}/download`} className="inline-flex items-center gap-2 rounded-2xl bg-cyan-400 px-4 py-2 text-sm font-bold text-slate-950 transition hover:bg-cyan-300">
                      <FiDownload /> Download
                    </a>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
