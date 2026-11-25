import Link from 'next/link';
import { FiActivity, FiFileText, FiGrid, FiShield } from 'react-icons/fi';

export function Navbar() {
  return (
    <nav className="sticky top-0 z-40 border-b border-white/10 bg-slate-950/75 px-6 py-4 text-slate-100 backdrop-blur-2xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
        <Link href="/dashboard" className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-cyan-400/15 text-cyan-300 shadow-lg shadow-cyan-500/10">
            <FiShield className="h-6 w-6" />
          </div>
          <div>
            <span className="block text-lg font-black text-gradient-cyan">AI Exam Surveillance</span>
            <span className="text-xs text-slate-500">Enterprise Monitoring Console</span>
          </div>
        </Link>
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Link href="/dashboard" className="flex items-center gap-2 rounded-2xl border border-cyan-400/20 bg-cyan-400/10 px-4 py-2 text-cyan-100 transition hover:bg-cyan-400/15">
            <FiGrid /> Dashboard
          </Link>
          <Link href="/reports" className="flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-slate-300 transition hover:bg-white/10 hover:text-white">
            <FiFileText /> Reports
          </Link>
          <span className="hidden items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-4 py-2 text-emerald-200 sm:flex">
            <FiActivity className="animate-pulse" /> Live
          </span>
        </div>
      </div>
    </nav>
  );
}
