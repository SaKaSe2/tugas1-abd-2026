"""Konversi dump Wikipedia Indonesia (stub-meta-history, gzip XML) menjadi Parquet.

Dataset : idwiki-20260901-stub-meta-history.xml.gz (metadata revisi, tanpa teks artikel)
Output  : data/processed/idwiki_revisions.parquet (flat, satu file, kompresi zstd)

Pakai:
    python src/convert_idwiki_to_parquet.py
    python src/convert_idwiki_to_parquet.py --limit-pages 2000   # uji coba cepat
"""

from __future__ import annotations

import argparse
import gzip
import time
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

MEDIAWIKI_NS = "{http://www.mediawiki.org/xml/export-0.11/}"
PAGE_TAG = MEDIAWIKI_NS + "page"

SCHEMA = pa.schema(
    [
        ("page_id", pa.int64()),
        ("page_title", pa.string()),
        ("page_namespace", pa.int16()),
        ("is_redirect", pa.bool_()),
        ("rev_id", pa.int64()),
        ("parent_rev_id", pa.int64()),
        ("rev_timestamp", pa.timestamp("us")),  # UTC (dari format Z)
        ("contributor_name", pa.string()),
        ("contributor_id", pa.int64()),
        ("is_anonymous", pa.bool_()),
        ("is_minor", pa.bool_()),
        ("comment", pa.string()),
        ("text_bytes", pa.int64()),
        ("text_sha1", pa.string()),
        ("rev_sha1", pa.string()),
    ]
)


def _localname(el) -> str:
    tag = el.tag
    return tag.rsplit("}", 1)[-1]


def _child(el, name):
    for c in el:
        if _localname(c) == name:
            return c
    return None


def _text(el) -> str | None:
    if el is None or el.text is None:
        return None
    return el.text or None


def _as_int(value: str | None):
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _as_ts(value: str | None):
    if not value:
        return None
    try:
        # "2003-11-07T00:43:23Z" -> datetime aware UTC -> buang tz (naive UTC)
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _make_iterparse():
    """Pakai lxml bila tersedia, kalau tidak pakai stdlib xml.etree."""
    try:
        from lxml import etree as LET

        def iterparse(handle, **kw):
            return LET.iterparse(handle, huge_tree=True, **kw)

        return iterparse, "lxml"
    except ImportError:
        import xml.etree.ElementTree as ET

        def iterparse(handle, **kw):
            return ET.iterparse(handle, **kw)

        return iterparse, "xml.etree (stdlib)"


def convert(input_path: Path, output_path: Path, batch_rows: int, limit_pages: int | None):
    iterparse, parser_name = _make_iterparse()
    print(f"parser     : {parser_name}", flush=True)
    print(f"input      : {input_path} ({input_path.stat().st_size / 1e9:.2f} GB)", flush=True)
    print(f"output     : {output_path}", flush=True)
    print(f"batch rows : {batch_rows:,}", flush=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_name(output_path.name + ".part")
    if tmp_path.exists():
        tmp_path.unlink()

    cols: dict[str, list] = {name: [] for name in SCHEMA.names}
    writer = pq.ParquetWriter(tmp_path, SCHEMA, compression="zstd")
    rows = pages = 0
    partial = False
    t0 = time.perf_counter()
    next_report = 500_000

    def flush():
        nonlocal rows, next_report
        if not cols["rev_id"]:
            return
        arrays = [pa.array(cols[name], type=SCHEMA.field(name).type) for name in SCHEMA.names]
        writer.write_table(pa.Table.from_arrays(arrays, schema=SCHEMA))
        for name in SCHEMA.names:
            cols[name].clear()

    def handle_page(page):
        nonlocal rows, pages, next_report
        page_id = _as_int(_text(_child(page, "id")))
        title = _text(_child(page, "title"))
        ns = _as_int(_text(_child(page, "ns"))) or 0
        is_redirect = _child(page, "redirect") is not None
        pages += 1

        for rev in page:
            if _localname(rev) != "revision":
                continue
            contributor = _child(rev, "contributor")
            username = ip = None
            contributor_id = None
            if contributor is not None:
                username = _text(_child(contributor, "username"))
                ip = _text(_child(contributor, "ip"))
                contributor_id = _as_int(_text(_child(contributor, "id")))
            text_el = _child(rev, "text")

            cols["page_id"].append(page_id)
            cols["page_title"].append(title)
            cols["page_namespace"].append(ns)
            cols["is_redirect"].append(is_redirect)
            cols["rev_id"].append(_as_int(_text(_child(rev, "id"))))
            cols["parent_rev_id"].append(_as_int(_text(_child(rev, "parentid"))))
            cols["rev_timestamp"].append(_as_ts(_text(_child(rev, "timestamp"))))
            cols["contributor_name"].append(username if username is not None else ip)
            cols["contributor_id"].append(contributor_id)
            cols["is_anonymous"].append(ip is not None)
            cols["is_minor"].append(_child(rev, "minor") is not None)
            cols["comment"].append(_text(_child(rev, "comment")))
            cols["text_bytes"].append(_as_int(text_el.get("bytes") if text_el is not None else None))
            cols["text_sha1"].append(text_el.get("sha1") if text_el is not None else None)
            cols["rev_sha1"].append(_text(_child(rev, "sha1")))
            rows += 1

        if rows >= next_report:
            elapsed = time.perf_counter() - t0
            print(
                f"[{elapsed:7.1f}s] rows={rows:,} pages={pages:,} "
                f"rate={rows / max(elapsed, 1e-9):,.0f} rev/s",
                flush=True,
            )
            next_report += 500_000
        if len(cols["rev_id"]) >= batch_rows:
            flush()

    with gzip.open(input_path, "rb") as handle:
        context = iterparse(handle, events=("start", "end"))
        try:
            _event, root = next(context)
        except StopIteration:
            root = None
            context = None

        if context is not None:
            try:
                for event, el in context:
                    if event == "end" and el.tag == PAGE_TAG:
                        handle_page(el)
                        if limit_pages is not None and pages >= limit_pages:
                            partial = True
                            print(f"--limit-pages {limit_pages} tercapai, berhenti.", flush=True)
                            break
                        el.clear()
                        if parser_name == "lxml":
                            parent = el.getparent()
                            if parent is not None:
                                while el.getprevious() is not None:
                                    del parent[0]
                        elif root is not None:
                            root.clear()
            except (SyntaxError, OSError, EOFError) as exc:
                partial = True
                print(f"PERINGATAN: stream terputus/tidak valid di akhir -> {exc!r}", flush=True)
                print("Baris yang sudah terbaca tetap disimpan (data parsial).", flush=True)

    flush()
    writer.close()
    tmp_path.replace(output_path)

    elapsed = time.perf_counter() - t0
    size = output_path.stat().st_size
    print("-" * 60, flush=True)
    print(f"status     : {'PARTIAL' if partial else 'LENGKAP'}", flush=True)
    print(f"halaman    : {pages:,}", flush=True)
    print(f"revisi     : {rows:,}", flush=True)
    print(f"waktu      : {elapsed / 60:.1f} menit ({rows / max(elapsed, 1e-9):,.0f} rev/s)", flush=True)
    print(f"file       : {output_path} ({size / 1e6:,.1f} MB)", flush=True)
    return partial


def main() -> int:
    ap = argparse.ArgumentParser(description="Konversi idwiki stub-meta-history XML.gz -> Parquet")
    ap.add_argument(
        "--input",
        default="data/raw/idwiki-20260901-stub-meta-history1.xml.gz",
    )
    ap.add_argument("--output", default="data/processed/idwiki_revisions.parquet")
    ap.add_argument("--batch-rows", type=int, default=200_000)
    ap.add_argument("--limit-pages", type=int, default=None, help="berhenti setelah N halaman (uji coba)")
    args = ap.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: input tidak ditemukan: {input_path}", flush=True)
        return 1

    partial = convert(input_path, Path(args.output), args.batch_rows, args.limit_pages)
    return 0 if not partial else 2


if __name__ == "__main__":
    raise SystemExit(main())
