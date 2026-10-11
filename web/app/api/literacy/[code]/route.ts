import { getAiRegionFlows } from "@/lib/queries";

/** Saran AI satu provinsi per alur D1 - D4: GET /api/literacy/35 (dibuka saat provinsi diklik). */
export const revalidate = 3600;

export async function GET(_request: Request, { params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  if (!/^\d{2}$/.test(code)) return Response.json({ ok: false }, { status: 400 });
  return Response.json({ ok: true, flows: await getAiRegionFlows(code) });
}
