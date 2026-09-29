"""Bandingkan keluaran alur D1 - D4 dari tabel flow_outputs untuk laporan.

Setiap alur dibaca pada snapshot terakhirnya sampai waktu ``--as-of``
(default sekarang), sehingga angka laporan bisa diulang persis dengan waktu
yang sama walaupun D1 terus berubah. D4 (keputusan resmi lembaga) menjadi
acuan untuk incident yang sudah sampai ke sana.

Ukuran yang dihitung:
  cakupan      jumlah incident per alur dan porsinya terhadap D1
  kecepatan    median jam dari artikel pertama sampai keluaran pertama alur;
               hanya incident yang pertama terlihat setelah flow_outputs mulai
               diisi (snapshot D1 awal adalah pengisian riwayat, bukan kecepatan)
  ketepatan    D1 terhadap D4 per kolom: precision, recall, F1; hanya D4
               berstatus dikonfirmasi dan kolom D4 yang terisi; nilai dianggap
               sama bila sama setelah huruf kecil dan spasi dirapikan, kecuali
               jenis serangan: daftar jenis D1 cukup memuat jenis dari D4
  penilaian    ketepatan penilaian D2 (sesuai / tidak sesuai) dan D3
               (dikonfirmasi / dibantah) terhadap D4 per kolom
  kesepakatan  D2 dengan D3 per kolom: persentase setuju dan Cohen's kappa
  hoaks        incident yang dibantah D4: berapa yang dinilai tinggi/sedang
               oleh mesin dan berapa yang dinilai sesuai oleh publik
  preventif    rata-rata Jaccard kunci langkah D1 dengan D4, dan porsi D4
               yang menambah langkah di luar D1
  bias         sebaran tingkat trust D1 seluruh incident dibanding incident
               yang sampai ke D4 (D4 cenderung kasus besar dan jelas)

Pemakaian:
  python eval/compare_flows.py [--db PATH] [--as-of ISO] [--out DIR]
Hasil: DIR/report.md dan DIR/metrics.csv (default eval/flows/), dan
laporan Markdown dicetak ke layar.
"""

import argparse
import csv
import json
import os
import sqlite3
import statistics
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from csais.config import DATABASE_FILE  # noqa: E402
from csais.flows import FLOWS, PENDING, REMOVED, attack_types  # noqa: E402

JUDGED_FIELDS = ("attack_type", "target", "threat_actor", "attack_date", "location")
D2_JUDGMENT = {"sesuai": True, "tidak_sesuai": False}
D3_JUDGMENT = {"dikonfirmasi": True, "dibantah": False}
TRUST_LEVELS = ("tinggi", "sedang", "rendah", "tanpa_skor")


# --- Pembacaan ---
def parse_time(value):
    """ISO 8601 -> datetime UTC; None bila kosong atau tidak terbaca."""
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _json(value):
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def load_latest(conn, as_of):
    """Snapshot terakhir tiap (alur, incident) sampai as_of: {flow: {incident: row}}."""
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM flow_outputs ORDER BY output_id"
    ).fetchall()
    latest = {flow: {} for flow in FLOWS}
    first = {flow: {} for flow in FLOWS}
    for row in rows:
        moment = parse_time(row["recorded_at"])
        if moment is None or moment > as_of:
            continue
        record = dict(row)
        latest[row["flow"]][row["incident_id"]] = record
        first[row["flow"]].setdefault(row["incident_id"], moment)
    for flow in FLOWS:
        # dihapus: incident sudah tidak ada; belum: jawaban belum cukup untuk memutuskan
        latest[flow] = {k: v for k, v in latest[flow].items() if v["status"] not in (REMOVED, PENDING)}
    return latest, first


def first_seen(conn):
    """Waktu artikel paling awal per incident."""
    cursor = conn.execute("""
        SELECT d.incident_id, MIN(a.published_date)
        FROM v05_incident_documents d JOIN articles a ON a.article_id = d.article_id
        GROUP BY d.incident_id
        """)
    return {incident_id: parse_time(value) for incident_id, value in cursor.fetchall()}


# --- Ukuran ---
def norm(value):
    return " ".join(str(value).lower().split()) if value else None


def same_value(field, guess, truth):
    """Nilai mesin cocok dengan acuan; jenis serangan D1 berupa daftar, cukup memuat acuan."""
    if guess is None or truth is None:
        return False
    if field == "attack_type":
        return set(attack_types(truth)) <= set(attack_types(guess))
    return norm(guess) == norm(truth)


def prf(tp, fp, fn):
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else None
    return precision, recall, f1


def cohen_kappa(pairs):
    """Kappa dua penilai biner; None bila tidak terdefinisi."""
    n = len(pairs)
    if not n:
        return None
    observed = sum(a == b for a, b in pairs) / n
    a_true = sum(a for a, _ in pairs) / n
    b_true = sum(b for _, b in pairs) / n
    expected = a_true * b_true + (1 - a_true) * (1 - b_true)
    return None if expected >= 1 else (observed - expected) / (1 - expected)


def compare(latest, first, seen):
    """Hitung semua ukuran; kembalikan daftar baris metrik."""
    metrics = []

    def add(metric, flow, field, value, n, note=""):
        metrics.append({"metric": metric, "flow": flow, "field": field, "value": value, "n": n, "note": note})

    d1, d2, d3, d4 = (latest[f] for f in FLOWS)
    total = len(d1)

    # Cakupan
    for flow in FLOWS:
        count = len(latest[flow])
        add("cakupan", flow, "", count, total, "porsi terhadap D1" if flow != "D1" else "")
        if flow != "D1":
            add("cakupan_porsi", flow, "", count / total if total else None, total)

    # Kecepatan
    started = min(first["D1"].values(), default=None)
    for flow in FLOWS:
        hours = []
        for incident_id, moment in first[flow].items():
            begin = seen.get(incident_id)
            if begin is None or started is None or begin < started:
                continue
            hours.append(max(0.0, (moment - begin).total_seconds() / 3600))
        add("kecepatan_median_jam", flow, "", statistics.median(hours) if hours else None, len(hours))

    confirmed = {k: v for k, v in d4.items() if v["status"] == "dikonfirmasi"}

    # Ketepatan D1 terhadap D4
    for field in JUDGED_FIELDS:
        tp = fp = fn = 0
        for incident_id, official in confirmed.items():
            truth = norm(official.get(field))
            machine = d1.get(incident_id)
            if truth is None or machine is None:
                continue
            guess = norm(machine.get(field))
            if same_value(field, guess, truth):
                tp += 1
            else:
                fn += 1
                if guess is not None:
                    fp += 1
        precision, recall, f1 = prf(tp, fp, fn)
        n = tp + fn
        add("ketepatan_precision", "D1", field, precision, n)
        add("ketepatan_recall", "D1", field, recall, n)
        add("ketepatan_f1", "D1", field, f1, n)

    # Penilaian D2 dan D3 terhadap D4
    for flow, source, mapping in (("D2", d2, D2_JUDGMENT), ("D3", d3, D3_JUDGMENT)):
        for field in JUDGED_FIELDS:
            correct = n = 0
            for incident_id, official in confirmed.items():
                row = source.get(incident_id)
                truth = norm(official.get(field))
                if row is None or truth is None:
                    continue
                judged = mapping.get(_json(row.get("field_status")).get(field))
                if judged is None:
                    continue
                n += 1
                correct += judged == same_value(field, row.get(field), truth)
            add("penilaian_tepat", flow, field, correct / n if n else None, n)

    # Kesepakatan D2 dengan D3
    for field in JUDGED_FIELDS:
        pairs = []
        for incident_id, public in d2.items():
            official = d3.get(incident_id)
            if official is None:
                continue
            a = D2_JUDGMENT.get(_json(public.get("field_status")).get(field))
            b = D3_JUDGMENT.get(_json(official.get("field_status")).get(field))
            if a is not None and b is not None:
                pairs.append((a, b))
        agree = sum(a == b for a, b in pairs) / len(pairs) if pairs else None
        add("kesepakatan_d2_d3", "D2-D3", field, agree, len(pairs))
        add("kappa_d2_d3", "D2-D3", field, cohen_kappa(pairs), len(pairs))

    # Hoaks yang lolos
    refuted = [k for k, v in d4.items() if v["status"] == "dibantah"]
    add("hoaks_dibantah_d4", "D4", "", len(refuted), len(d4))
    add("hoaks_lolos_mesin", "D1", "", sum(1 for k in refuted if d1.get(k, {}).get("status") in ("tinggi", "sedang")), len(refuted), "trust tinggi atau sedang")
    add("hoaks_lolos_publik", "D2", "", sum(1 for k in refuted if d2.get(k, {}).get("status") == "sesuai"), len(refuted), "survei menyatakan sesuai")

    # Langkah preventif D1 dengan D4
    scores, added = [], 0
    for incident_id, official in d4.items():
        machine = d1.get(incident_id)
        official_steps = set(_json(official.get("prevention")).get("steps") or [])
        if machine is None or not official_steps:
            continue
        machine_steps = set(_json(machine.get("prevention")).get("steps") or [])
        union = machine_steps | official_steps
        scores.append(len(machine_steps & official_steps) / len(union))
        added += bool(official_steps - machine_steps)
    add("preventif_jaccard_d1_d4", "D1-D4", "", statistics.mean(scores) if scores else None, len(scores))
    add("preventif_d4_menambah", "D4", "", added / len(scores) if scores else None, len(scores))

    # Bias pilihan
    reached = [k for k in d4 if k in d1]
    for level in TRUST_LEVELS:
        overall = sum(1 for v in d1.values() if v["status"] == level)
        subset = sum(1 for k in reached if d1[k]["status"] == level)
        add("bias_trust_semua", "D1", level, overall / total if total else None, total)
        add("bias_trust_sampai_d4", "D1", level, subset / len(reached) if reached else None, len(reached))

    return metrics


# --- Keluaran ---
def fmt(value):
    if value is None:
        return "–"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def render(metrics, as_of):
    lines = [
        "# Perbandingan alur D1 - D4",
        "",
        f"Snapshot sampai {as_of.isoformat(timespec='seconds')}. Tanda – berarti belum ada data.",
        "",
        "| Ukuran | Alur | Kolom | Nilai | n | Catatan |",
        "|---|---|---|---|---|---|",
    ]
    for m in metrics:
        lines.append(f"| {m['metric']} | {m['flow']} | {m['field']} | {fmt(m['value'])} | {m['n']} | {m['note']} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Bandingkan keluaran alur D1 - D4")
    parser.add_argument("--db", default=DATABASE_FILE)
    parser.add_argument("--as-of", help="waktu snapshot ISO 8601 (default sekarang)")
    parser.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "flows"))
    args = parser.parse_args()

    as_of = parse_time(args.as_of) if args.as_of else datetime.now(timezone.utc)
    if as_of is None:
        parser.error(f"--as-of tidak terbaca: {args.as_of}")
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    try:
        latest, first = load_latest(conn, as_of)
        conn.row_factory = None
        metrics = compare(latest, first, first_seen(conn))
    finally:
        conn.close()

    os.makedirs(args.out, exist_ok=True)
    report = render(metrics, as_of)
    with open(os.path.join(args.out, "report.md"), "w", encoding="utf-8") as fh:
        fh.write(report)
    with open(os.path.join(args.out, "metrics.csv"), "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["metric", "flow", "field", "value", "n", "note"])
        writer.writeheader()
        writer.writerows(metrics)
    print(report)


if __name__ == "__main__":
    main()
