export type Student = { id: string; seat: string; risk: number };

export function StudentCard({ student }: { student: Student }) {
  return (
    <article className="rounded-lg border p-4">
      <h3 className="font-semibold">Student {student.id}</h3>
      <p>Seat: {student.seat}</p>
      <p>Risk: {student.risk}</p>
    </article>
  );
}
