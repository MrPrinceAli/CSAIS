/** Kerangka isi saat detail incident dimuat di dalam jendela pop-up. */
export default function Loading() {
  return (
    <div className="im-loading" aria-busy="true">
      <span className="im-sk h-4 w-40" />
      <span className="im-sk h-8 w-3/4" />
      <span className="im-sk h-4 w-1/2" />
      <div className="grid gap-4 pt-4 lg:grid-cols-[280px_minmax(0,1fr)_280px]">
        <span className="im-sk h-64" />
        <span className="im-sk h-96" />
        <span className="im-sk h-48" />
      </div>
    </div>
  );
}
