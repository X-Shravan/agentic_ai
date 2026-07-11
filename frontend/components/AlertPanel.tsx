export type AlertItem = { id: string; studentId: string; severity: string; message: string };

export function AlertPanel({ alerts = [] }: { alerts?: AlertItem[] }) {
  return (
    <aside className="space-y-3">
      <h2 className="text-lg font-semibold">Live Alerts</h2>
      {alerts.map((alert) => (
        <div key={alert.id} className="rounded-md border-l-4 border-red-500 bg-red-50 p-3">
          <strong>{alert.studentId}</strong> — {alert.severity}: {alert.message}
        </div>
      ))}
    </aside>
  );
}
