import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getLedgerStats, getSampleEvidence, verify, type LedgerProof, type VerifyRecord } from "@/lib/queries";
import { formatters, incidentTitle } from "@/lib/format";
import { evidenceRole, getDict, isLang, L, type Lang } from "@/lib/i18n";
import { HashGrid } from "@/components/ui";
import { AttestationSection } from "@/components/attestation-section";
import { MerkleMini } from "@/components/merkle-mini";
import { SearchField } from "@/components/search-field";

function short(hex: string): string {
  return `${hex.slice(0, 10)}…${hex.slice(-6)}`;
}

/** Posisi bukti dalam batch Merkle: akar, daun, hasil verifikasi proof, status penjangkaran. */
/** "anvil-lokal:31337@0xabc..." -> nama jaringan yang enak dibaca. */
function chainName(value: string): string {
  const name = value.split(":")[0];
  return name === "anvil-lokal" ? "Anvil lokal" : name;
}

/** Rincian jangkar: jaringan, blok, transaksi, kontrak; jaringan lokal diberi keterangan. */
function AnchorLine({ ledger, lang }: { ledger: LedgerProof; lang: Lang }) {
  const t = getDict(lang).verify.ledger;
  const [head, contract] = (ledger.anchor_chain ?? "").split("@");
  const [name, chainId] = head.split(":");
  return (
    <div className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 font-mono text-[11.5px]">
      <span className="text-muted">{t.network}</span>
      <span>
        {chainName(name)} · chain {chainId}
        {ledger.anchor_block !== null ? ` · ${t.block} ${ledger.anchor_block}` : ""}
      </span>
      {ledger.anchor_tx ? (
        <>
          <span className="text-muted">tx</span>
          <span className="break-all">{ledger.anchor_tx}</span>
        </>
      ) : null}
      {contract ? (
        <>
          <span className="text-muted">{t.contract}</span>
          <span className="break-all">{contract}</span>
        </>
      ) : null}
      {name.endsWith("lokal") ? <span className="col-span-2 font-sans text-[11.5px] text-muted">{t.localNote}</span> : null}
    </div>
  );
}

function LedgerBlock({ ledger, lang, snapshot }: { ledger: LedgerProof; lang: Lang; snapshot?: { same: string; changed: string } }) {
  const t = getDict(lang).verify.ledger;
  const f = formatters(lang);
  const ok = ledger.valid && ledger.leaf_matches;
  return (
    <div className="mt-1 flex flex-col gap-1.5 rounded-md border border-line bg-bg p-3 text-[12.5px]">
      <div className="flex flex-wrap items-center gap-2">
        <span className="label text-chain">{t.title}</span>
        <span className="font-mono text-muted">
          {t.batch(ledger.batch_id)} · {t.leaf(ledger.leaf_index, f.num(ledger.leaf_count))} · {t.created(f.dateTime(ledger.created_at))}
        </span>
      </div>
      <div className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 font-mono text-[11.5px]">
        <span className="text-muted">{t.root}</span>
        <span className="break-all" title={ledger.merkle_root}>
          {ledger.merkle_root}
        </span>
        <span className="text-muted">{t.leafHash}</span>
        <span className="break-all" title={ledger.leaf_hash}>
          {short(ledger.leaf_hash)} · {t.siblings(ledger.proof.length)}
        </span>
      </div>
      <MerkleMini siblings={ledger.proof.length} leafLabel={t.leafHash} rootLabel={t.root} valid={ok} anchored={ledger.anchor_status === "ANCHORED"} />
      {ledger.anchor_status === "ANCHORED" ? <AnchorLine ledger={ledger} lang={lang} /> : null}
      <div className="flex flex-wrap gap-1.5 pt-0.5">
        <span className={`chip ${ok ? "chip-accent" : ""}`}>{ok ? t.proofValid : ledger.leaf_matches ? t.proofInvalid : t.leafMismatch}</span>
        <span className="chip chip-chain">
          {ledger.anchor_status === "ANCHORED" && ledger.anchor_chain ? t.anchored(chainName(ledger.anchor_chain)) : t.pending}
        </span>
        <span className={`chip ${snapshot && ledger.snapshot_changed ? "text-high" : ""}`} title={ledger.snapshot_sha256 ?? undefined}>
          {ledger.snapshot_changed ? (snapshot?.changed ?? t.snapshotChanged) : (snapshot?.same ?? t.snapshotSame)}
        </span>
      </div>
    </div>
  );
}

type Search = Record<string, string | string[] | undefined>;

export async function generateMetadata({ params }: { params: Promise<{ lang: string }> }): Promise<Metadata> {
  const { lang } = await params;
  return { title: getDict(isLang(lang) ? lang : "id").verify.title };
}

/** Hasil verifikasi catatan resmi D4: isi catatan, kecocokan hash, dan posisinya di batch Merkle. */
function RecordBlock({ record, lang }: { record: VerifyRecord; lang: Lang }) {
  const t = getDict(lang);
  const r = t.verify.record;
  const f = formatters(lang);
  const ok = record.hash_matches && (record.ledger?.valid ?? false) && (record.ledger?.leaf_matches ?? false);
  return (
    <section className="card flex flex-col gap-4 p-5" style={{ borderTopColor: "var(--good)", borderTopWidth: 2 }}>
      <div className="flex items-start gap-3">
        <span className={`mt-0.5 inline-flex h-8 w-8 flex-none items-center justify-center rounded-full ${ok ? "bg-good" : "bg-high"}`} aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0f1720" strokeWidth="3">
            {ok ? <path d="M5 12l5 5L20 7" /> : <path d="M6 6l12 12M18 6L6 18" />}
          </svg>
        </span>
        <div className="flex flex-col">
          <span className="text-[16px] font-semibold">{ok ? r.found : r.mismatch}</span>
          <span className="text-[12.5px] text-muted">{r.kind}</span>
        </div>
      </div>
      <dl className="grid grid-cols-[150px_minmax(0,1fr)] gap-x-4 gap-y-2 text-[13px]">
        <dt className="text-muted">{r.incident}</dt>
        <dd>
          <Link href={L(lang, `/incidents/${record.incident_id}`)} className="no-underline">
            {incidentTitle(record.title) || record.incident_id}
          </Link>
        </dd>
        <dt className="text-muted">{r.status}</dt>
        <dd className="flex flex-wrap gap-2">
          <span className={record.status === "dibantah" ? "text-high" : "text-good"}>{t.flows.status[record.status] ?? record.status}</span>
          {record.tier ? <span className="chip">{t.flows.tiers[record.tier] ?? record.tier}</span> : null}
        </dd>
        <dt className="text-muted">{r.reason}</dt>
        <dd className="text-soft">{record.reason ?? "—"}</dd>
        <dt className="text-muted">{r.source}</dt>
        <dd className="break-all">
          {record.source_ref && /^https?:\/\//.test(record.source_ref) ? (
            <a href={record.source_ref} target="_blank" rel="noreferrer">
              {record.source_ref}
            </a>
          ) : record.source_ref?.startsWith("portal:") ? (
            r.viaPortal
          ) : (
            record.source_ref ?? "—"
          )}
        </dd>
        <dt className="text-muted">{r.recorded}</dt>
        <dd>{f.dateTime(record.recorded_at)}</dd>
        {record.supersedes !== null ? (
          <>
            <dt className="text-muted">{r.supersedes}</dt>
            <dd className="font-mono">#{record.supersedes}</dd>
          </>
        ) : null}
        <dt className="text-muted">{r.hash}</dt>
        <dd className="flex flex-col gap-0.5">
          <span className="break-all font-mono text-[11.5px]">{record.output_hash}</span>
          <span className={record.hash_matches ? "text-good" : "text-high"}>{record.hash_matches ? r.hashOk : r.hashBad}</span>
        </dd>
        <dt className="text-muted">{r.uid}</dt>
        <dd className="break-all font-mono text-[11.5px]">{record.uid}</dd>
      </dl>
      {record.ledger ? <LedgerBlock ledger={record.ledger} lang={lang} snapshot={{ same: r.chipSame, changed: r.chipChanged }} /> : null}
    </section>
  );
}

export default async function VerifyPage({ params, searchParams }: { params: Promise<{ lang: string }>; searchParams: Promise<Search> }) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  const t = getDict(lang);
  const f = formatters(lang);
  const sp = await searchParams;
  const raw = Array.isArray(sp.q) ? sp.q[0] : sp.q;
  const input = (raw ?? "").trim().slice(0, 600);
  const [result, samples, ledgerStats] = await Promise.all([input ? verify(input) : Promise.resolve(null), getSampleEvidence(), getLedgerStats()]);
  const base = L(lang, "/verify");
  const anchoredAny = result?.evidence.some((e) => e.ledger?.anchor_status === "ANCHORED") ?? false;

  return (
    <div className="flex flex-col gap-6">
      <section className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <div className="flex flex-col gap-3">
          <h1 className="text-balance text-[26px] font-semibold leading-tight">{t.verify.title}</h1>
          <p className="max-w-[70ch] text-[14.5px] leading-relaxed text-soft">{t.verify.lead}</p>
          <form method="get" action={base} className="flex w-full flex-col gap-2 sm:flex-row">
            <label htmlFor="q" className="sr-only">
              {t.verify.placeholder}
            </label>
            <SearchField
              id="q"
              name="q"
              type="text"
              defaultValue={input}
              placeholder={t.verify.placeholder}
              examples={[...samples.slice(0, 2).map((s) => s.evidence_uid), "https://"]}
              className="field flex-1 py-2.5 font-mono text-[12.5px]"
            />
            <button type="submit" className="btn btn-primary justify-center">
              {t.verify.button}
            </button>
          </form>
          {!input && samples.length ? (
            <div className="flex flex-wrap items-center gap-2 text-[12.5px] text-muted">
              <span>{t.verify.sampleLabel}:</span>
              {samples.map((s) => (
                <Link key={s.evidence_uid} href={`${base}?q=${s.evidence_uid}`} className="chip chip-accent no-underline">
                  {s.evidence_uid}
                </Link>
              ))}
            </div>
          ) : null}
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12.5px] text-muted">
            <span>{ledgerStats ? t.verify.ledger.stats(f.num(ledgerStats.batches), f.num(ledgerStats.leaves), f.num(ledgerStats.pending)) : t.verify.ledger.statsEmpty}</span>
            <Link href={`${L(lang, "/")}#process`} className="no-underline">
              {t.verify.howLink} →
            </Link>
            <a href="#lembaga" className="no-underline">
              {t.verify.attestLink} ↓
            </a>
          </p>
        </div>
        <div className="card corners grid grid-cols-[auto_minmax(0,1fr)] items-center gap-4 p-4 grid-bg">
          <HashGrid hex={result?.article?.content_sha256 ?? samples[0]?.content_sha256 ?? null} size={112} label={t.verify.fingerprintTitle} />
          <div className="flex flex-col gap-1 text-[12.5px] text-soft">
            <span className="label">{t.verify.fingerprintTitle}</span>
            <span className="leading-relaxed">{t.verify.fingerprintText}</span>
          </div>
        </div>
      </section>

      {result?.record ? (
        <RecordBlock record={result.record} lang={lang} />
      ) : result ? (
        result.article ? (
          <section className="card flex flex-col gap-4 p-5">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 inline-flex h-8 w-8 flex-none items-center justify-center rounded-full bg-good" aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0f1720" strokeWidth="3">
                  <path d="M5 12l5 5L20 7" />
                </svg>
              </span>
              <div className="flex flex-col">
                <span className="text-[16px] font-semibold">{t.verify.found}</span>
                <span className="text-[12.5px] text-muted">
                  {t.verify.matchedBy[result.kind === "hash" ? "hash" : result.kind === "url" ? "url" : "uid"]}{" "}
                  {result.article.content_fetched_at ? t.verify.fetchedAt(f.dateTime(result.article.content_fetched_at)) : t.verify.noContent}
                </span>
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-[auto_minmax(0,1fr)]">
              <HashGrid hex={result.article.content_sha256 ?? result.evidence[0]?.content_fingerprint} size={128} label={t.verify.fingerprintTitle} />
              <dl className="grid grid-cols-[130px_minmax(0,1fr)] gap-x-4 gap-y-2 text-[13px]">
                <dt className="text-muted">{t.verify.fields.article}</dt>
                <dd>
                  <a href={result.article.resolved_url ?? result.article.article_url ?? "#"} target="_blank" rel="noreferrer" className="no-underline">
                    {result.article.title ?? "—"}
                  </a>
                </dd>
                <dt className="text-muted">{t.verify.fields.published}</dt>
                <dd>{f.dateTime(result.article.published_date)}</dd>
                <dt className="text-muted">{t.verify.fields.uid}</dt>
                <dd className="break-all font-mono">{result.article.article_uid ?? "—"}</dd>
                <dt className="text-muted">{t.verify.fields.sha}</dt>
                <dd className="break-all font-mono">{result.article.content_sha256 ?? t.verify.noSha}</dd>
                {result.evidence.map((e) => (
                  <div key={e.evidence_uid} className="contents">
                    <dt className="text-muted">{t.verify.fields.evidence}</dt>
                    <dd className="flex flex-col gap-1">
                      <span className="flex flex-wrap items-center gap-2">
                        <span className="font-mono">{e.evidence_uid}</span>
                        <span className="chip">{evidenceRole(e.evidence_type, lang)}</span>
                        {!e.ledger ? <span className="chip chip-chain">{t.verify.ledger.notBatched}</span> : null}
                        <Link href={L(lang, `/incidents/${e.incident_id}`)} className="no-underline">
                          {t.verify.openIncident}
                        </Link>
                      </span>
                      {e.ledger ? <LedgerBlock ledger={e.ledger} lang={lang} /> : null}
                    </dd>
                  </div>
                ))}
                {!anchoredAny ? (
                  <>
                    <dt className="text-muted">{t.verify.fields.chain}</dt>
                    <dd>
                      <span className="chip chip-chain">{t.verify.notAnchored}</span>
                    </dd>
                  </>
                ) : null}
              </dl>
            </div>
          </section>
        ) : (
          <section className="card flex flex-col gap-2 p-5">
            <span className="text-[16px] font-semibold">{t.verify.notFound}</span>
            <p className="text-[13.5px] text-soft">{result.kind === "kosong" ? t.verify.notFoundEmpty : t.verify.notFoundText}</p>
          </section>
        )
      ) : null}

      <AttestationSection lang={lang} />
    </div>
  );
}
