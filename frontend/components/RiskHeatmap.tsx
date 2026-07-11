export type RiskCell = { seat: string; score: number };

export function RiskHeatmap({ cells = [] }: { cells?: RiskCell[] }) {
  return (
    <div className="grid grid-cols-5 gap-2">
      {cells.map((cell) => (
        <div key={cell.seat} className="rounded p-2 text-center" style={{ background: `rgba(239,68,68,${Math.min(cell.score / 100, 1)})` }}>
          <span className="text-sm font-medium">{cell.seat}</span>
          <div className="text-xs">{cell.score}</div>
        </div>
      ))}
    </div>
  );
}
