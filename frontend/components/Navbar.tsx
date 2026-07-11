export function Navbar() {
  return (
    <nav className="flex items-center justify-between border-b px-6 py-4">
      <span className="text-xl font-bold">AI Exam Surveillance</span>
      <div className="flex gap-4 text-sm"><a href="/dashboard">Dashboard</a><a href="/reports">Reports</a></div>
    </nav>
  );
}
