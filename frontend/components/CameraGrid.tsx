export type Camera = { id: string; name: string; status: 'online' | 'offline' };

export function CameraGrid({ cameras = [] }: { cameras?: Camera[] }) {
  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {cameras.map((camera) => (
        <article key={camera.id} className="rounded-lg border p-4 shadow-sm">
          <h3 className="font-semibold">{camera.name}</h3>
          <p className="text-sm text-slate-500">Status: {camera.status}</p>
        </article>
      ))}
    </section>
  );
}
