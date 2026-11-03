#!/usr/bin/env python3
"""
Mengolah log daya HWiNFO untuk satu pengukuran "beban" (ukur_pc.py).

Pasangan masukan:
    berkas CSV HWiNFO yang direkam selama pengukuran
    berkas cap waktu beban_*.json dari ukur_pc.py

Langkah:
  1. Cuplikan HWiNFO dibagi menurut fase: diam (sebelum), beban, diam (sesudah).
     Beberapa detik di awal dan akhir tiap fase dibuang (BATAS_DETIK) supaya
     transisi tidak ikut terhitung.
  2. Daya diam = rata-rata kedua fase diam (sebelum dan sesudah), sehingga
     pergeseran pelan selama pengukuran (misalnya suhu) ikut terimbangi.
  3. Daya inferensi = daya beban - daya diam (metode selisih).
  4. Energi per citra:
       tambahan = (P_beban - P_diam) / citra per detik
       total    =  P_beban            / citra per detik

Tiga tingkat daya CPU dari HWiNFO (AMD Ryzen):
  Core K Power         inti fisik yang dikunci (ukur_pc.py --inti K)
  CPU Package Power    seluruh paket CPU
  GPU Power            kontrol: harus tidak berubah, karena model hanya di CPU

Jalankan:
    python 5_PC/olah_daya_pc.py 5_PC/hasil/hwinfo.CSV
        semua pengukuran (beban_*.json di folder yang sama) yang tercakup log
        diolah, lalu dirangkum per model: rata-rata ± simpangan antarulangan
    python 5_PC/olah_daya_pc.py 5_PC/hasil/hwinfo.CSV 5_PC/hasil/beban_....json
        satu pengukuran saja, dengan rincian per fase
"""
import csv
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

BATAS_DETIK = 5.0        # dibuang di awal dan akhir tiap fase


def baca_hwinfo(berkas):
    """Kembalikan (judul kolom, nama sensor per kolom, daftar (waktu, baris))."""
    baris = list(csv.reader(open(berkas, encoding="latin-1")))
    judul = baris[0]
    # HWiNFO menulis nama perangkat tiap kolom di baris terakhir
    sensor = baris[-1] if not baris[-1][0] else [""] * len(judul)
    data = []
    for b in baris[1:]:
        if len(b) < 2 or not b[0] or not b[1]:
            continue
        try:
            t = datetime.strptime(f"{b[0]} {b[1]}", "%d.%m.%Y %H:%M:%S.%f")
        except ValueError:
            continue
        data.append((t, b))
    return judul, sensor, data


def kolom(judul, sensor, nama, perangkat=None):
    """Indeks kolom berjudul `nama`, bila perlu dipilih menurut nama perangkat."""
    cocok = [i for i, j in enumerate(judul) if j.strip() == nama]
    if perangkat:
        cocok = [i for i in cocok if perangkat.lower() in sensor[i].lower()] or cocok
    return cocok[0] if cocok else None


def angka(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def rerata_fase(data, i_kolom, mulai, selesai):
    """Rata-rata kolom dalam satu fase, hanya dari cuplikan SEGAR.

    HWiNFO menulis satu baris tiap interval, tetapi bila pembacaan sensor
    tertahan (misalnya inti yang dibaca sedang penuh dipakai), baris berikutnya
    hanya MENGULANG nilai lama. Baris ulangan seperti itu dibuang: sebuah
    cuplikan dipakai hanya bila nilainya berbeda dari baris sebelumnya.
    Tanpa ini, nilai diam yang basi dapat terbawa ke awal fase beban.
    """
    nilai = [angka(b[i_kolom]) for k, (t, b) in enumerate(data)
             if k > 0 and b[i_kolom] != data[k - 1][1][i_kolom]
             and (t - mulai).total_seconds() >= BATAS_DETIK
             and (selesai - t).total_seconds() >= BATAS_DETIK]
    nilai = [v for v in nilai if v is not None]
    if not nilai:
        return None, None, 0
    return statistics.mean(nilai), (statistics.stdev(nilai) if len(nilai) > 1 else 0.0), len(nilai)


def cakup(data, fase):
    t = [datetime.fromisoformat(f["waktu"]) for f in fase["fase"]]
    return bool(data) and data[0][0] <= t[0] and t[-1] <= data[-1][0]


def olah_satu(judul, sensor, data, fase):
    """Daya per fase untuk satu pengukuran. Mengembalikan ringkasan (dict)."""
    t = {f["fase"]: datetime.fromisoformat(f["waktu"]) for f in fase["fase"]}
    inti = (fase.get("kunci_inti") or {}).get("inti_fisik")
    besaran = []
    if inti is not None:
        besaran.append((f"Core {inti} Power [W]", "Inti yang dikunci"))
    besaran += [("CPU Package Power [W]", "Paket CPU"),
                ("Core+SoC+SR Power (SVI3 TFN) [W]", "Inti + SoC (regulator)"),
                ("GPU Power [W]", "GPU (kontrol)")]

    laju = fase["citra_per_detik"]
    ringkas = {"model": fase["model"], "inti": inti, "mulai": fase["fase"][0]["waktu"],
               "citra_per_detik": laju, "pemakaian_cpu_persen": fase.get("pemakaian_cpu_persen"),
               "besaran": {}}
    for nama_kolom, label in besaran:
        i = kolom(judul, sensor, nama_kolom, "NVIDIA" if label.startswith("GPU") else None)
        if i is None:
            continue
        d1, s1, n1 = rerata_fase(data, i, t["diam_mulai"], t["beban_mulai"])
        bb, sb, nb = rerata_fase(data, i, t["beban_mulai"], t["beban_selesai"])
        d2, s2, n2 = rerata_fase(data, i, t["beban_selesai"], t["diam_selesai"])
        if None in (d1, bb, d2):
            continue
        selisih = bb - (d1 + d2) / 2
        ringkas["besaran"][label] = {
            "kolom": nama_kolom, "perangkat": sensor[i] if i < len(sensor) else "",
            "diam_sebelum_w": d1, "beban_w": bb, "diam_sesudah_w": d2,
            "simpangan_w": [s1, sb, s2], "n_cuplikan": [n1, nb, n2],
            "selisih_w": selisih,
            "energi_tambahan_uj_per_citra": selisih / laju * 1e6,
            "energi_total_uj_per_citra": bb / laju * 1e6}
    if inti is not None:
        i0 = kolom(judul, sensor, f"Core {inti} T0 Usage [%]")
        if i0 is not None:
            ringkas["pemakaian_core_t0_hwinfo_persen"] = rerata_fase(
                data, i0, t["beban_mulai"], t["beban_selesai"])[0]
    return ringkas


def cetak_satu(r):
    print(f"Model {r['model'].upper()}" + (f", inti fisik {r['inti']}" if r["inti"] is not None else "")
          + f" | {r['citra_per_detik']:,.0f} citra/detik | CPU proses {r['pemakaian_cpu_persen'] or 0:.1f} %")
    print(f"{'Besaran':24} {'Diam sebelum':>14} {'Beban':>14} {'Diam sesudah':>14}"
          f" {'Selisih':>9} {'E tambahan':>11} {'E total':>9}")
    print(f"{'':24} {'(W)':>14} {'(W)':>14} {'(W)':>14} {'(W)':>9} {'(µJ/citra)':>11} {'(µJ/citra)':>9}")
    for label, b in r["besaran"].items():
        s1, sb, s2 = b["simpangan_w"]
        print(f"{label:24} {b['diam_sebelum_w']:7.3f} ±{s1:5.3f} {b['beban_w']:7.3f} ±{sb:5.3f}"
              f" {b['diam_sesudah_w']:7.3f} ±{s2:5.3f} {b['selisih_w']:9.3f}"
              f" {b['energi_tambahan_uj_per_citra']:11.2f} {b['energi_total_uj_per_citra']:9.2f}")


def rs(nilai):
    """'rata ± simpangan' antarulangan."""
    return (statistics.mean(nilai), statistics.stdev(nilai) if len(nilai) > 1 else 0.0)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    berkas_csv = Path(sys.argv[1])
    judul, sensor, data = baca_hwinfo(berkas_csv)
    interval = statistics.median((b[0] - a[0]).total_seconds() for a, b in zip(data, data[1:]))

    # ---- satu pengukuran ----
    if len(sys.argv) == 3:
        berkas_fase = Path(sys.argv[2])
        fase = json.loads(berkas_fase.read_text(encoding="utf-8"))
        if not cakup(data, fase):
            sys.exit("Log HWiNFO tidak mencakup seluruh fase pengukuran. "
                     "Mulai logging SEBELUM skrip dijalankan dan hentikan SETELAH diam_selesai.")
        print(f"Interval cuplikan HWiNFO: {interval:.2f} detik; "
              f"{BATAS_DETIK:.0f} detik di tepi tiap fase dibuang\n")
        r = olah_satu(judul, sensor, data, fase)
        cetak_satu(r)
        keluaran = berkas_fase.with_name(berkas_fase.stem + "_daya.json")
        keluaran.write_text(json.dumps(r, indent=2), encoding="utf-8")
        print(f"\nringkasan: {keluaran}")
        return

    # ---- semua pengukuran yang tercakup log ----
    hasil = []
    for j in sorted(berkas_csv.parent.glob("beban_*.json")):
        if j.stem.endswith("_daya"):
            continue
        fase = json.loads(j.read_text(encoding="utf-8"))
        if cakup(data, fase):
            hasil.append(olah_satu(judul, sensor, data, fase))
    if not hasil:
        sys.exit("Tidak ada pengukuran beban_*.json yang tercakup log ini.")

    print(f"Log {berkas_csv.name}: {len(data)} cuplikan, interval {interval:.2f} detik, "
          f"{len(hasil)} pengukuran tercakup; {BATAS_DETIK:.0f} detik di tepi tiap fase dibuang\n")
    print("Per pengukuran (selisih daya beban - diam, W):")
    print(f"  {'Mulai':23} {'Model':5} {'citra/s':>8} {'Inti':>7} {'Paket':>7} {'GPU':>7}")
    for r in hasil:
        b = r["besaran"]
        print(f"  {r['mulai']:23} {r['model']:5} {r['citra_per_detik']:8.0f}"
              f" {b.get('Inti yang dikunci', {}).get('selisih_w', float('nan')):7.3f}"
              f" {b.get('Paket CPU', {}).get('selisih_w', float('nan')):7.3f}"
              f" {b.get('GPU (kontrol)', {}).get('selisih_w', float('nan')):7.3f}")

    rangkum = {"log": berkas_csv.name, "interval_detik": interval, "per_pengukuran": hasil,
               "per_model": {}}
    print("\nRangkuman per model (rata-rata ± simpangan antarulangan):")
    for model in sorted({r["model"] for r in hasil}):
        rr = [r for r in hasil if r["model"] == model]
        laju = rs([r["citra_per_detik"] for r in rr])
        print(f"\n  {model.upper()}: {len(rr)} ulangan, {laju[0]:,.0f} ± {laju[1]:,.0f} citra/detik")
        print(f"    {'Besaran':24} {'Diam (W)':>14} {'Beban (W)':>14} {'Selisih (W)':>14}"
              f" {'E tambahan (µJ)':>17} {'E total (µJ)':>15}")
        m = {"ulangan": len(rr), "citra_per_detik": laju, "besaran": {}}
        for label in rr[0]["besaran"]:
            bs = [r["besaran"][label] for r in rr if label in r["besaran"]]
            diam = rs([(b["diam_sebelum_w"] + b["diam_sesudah_w"]) / 2 for b in bs])
            beban = rs([b["beban_w"] for b in bs])
            selisih = rs([b["selisih_w"] for b in bs])
            et = rs([b["energi_tambahan_uj_per_citra"] for b in bs])
            eo = rs([b["energi_total_uj_per_citra"] for b in bs])
            print(f"    {label:24} {diam[0]:7.2f} ±{diam[1]:5.2f} {beban[0]:7.2f} ±{beban[1]:5.2f}"
                  f" {selisih[0]:7.2f} ±{selisih[1]:5.2f} {et[0]:9.1f} ±{et[1]:6.1f}"
                  f" {eo[0]:8.1f} ±{eo[1]:5.1f}")
            m["besaran"][label] = {"diam_w": diam, "beban_w": beban, "selisih_w": selisih,
                                   "energi_tambahan_uj_per_citra": et,
                                   "energi_total_uj_per_citra": eo}
        rangkum["per_model"][model] = m

    keluaran = berkas_csv.with_name(berkas_csv.stem + "_rangkuman.json")
    keluaran.write_text(json.dumps(rangkum, indent=2), encoding="utf-8")
    print(f"\nrangkuman: {keluaran}")


if __name__ == "__main__":
    main()
