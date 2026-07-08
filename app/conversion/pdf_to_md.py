"""PDF -> Markdown converter for the RAG pipeline.

Only the Python standard library is used.

- Parsing via xref / xref-stream / object streams (no regex over the whole file).
- Text from content streams (Tj / TJ / ' / ") and Form XObjects (Do).
- CID fonts: /ToUnicode CMap -> Unicode; without a CMap, hex glyph codes are
  emitted with a marker.
- Headings by font size, lists by markers, page separators.
- Images, formulas, headers/footers and footnotes are ignored.
"""

from __future__ import annotations

import re
import zlib
from pathlib import Path
from typing import Any

# ---------- PDF values ----------

PdfDict = dict[str, Any]


class PDFSyntaxError(ValueError):
    pass


def _is_white(b: int) -> bool:
    return b in (0, 9, 10, 12, 13, 32)


def _skip_ws(data: bytes, pos: int) -> int:
    n = len(data)
    while pos < n and _is_white(data[pos]):
        pos += 1
    return pos


def _read_line(data: bytes, pos: int) -> tuple[bytes, int]:
    start = pos
    n = len(data)
    while pos < n and data[pos] not in (10, 13):
        pos += 1
    while pos < n and data[pos] in (10, 13):
        pos += 1
    return data[start:pos].strip(), pos


def _parse_number(data: bytes, pos: int) -> tuple[int | float, int]:
    pos = _skip_ws(data, pos)
    start = pos
    n = len(data)
    while pos < n and data[pos] in b"+-0123456789.":
        pos += 1
    if pos == start:
        raise PDFSyntaxError(f"expected number, got {data[pos:pos+10]!r} at {pos}")
    token = data[start:pos].decode("latin-1")
    if "." in token:
        return float(token), pos
    return int(token), pos


def _parse_name(data: bytes, pos: int) -> tuple[str, int]:
    pos += 1
    start = pos
    n = len(data)
    while pos < n and not _is_white(data[pos]) and data[pos] not in b"/[]<>()":
        if data[pos] == ord("#") and pos + 2 < n:
            pos += 3
            continue
        pos += 1
    return data[start:pos].decode("latin-1", "replace"), pos


def _parse_literal_string(data: bytes, pos: int) -> tuple[bytes, int]:
    pos += 1
    out = bytearray()
    depth = 1
    n = len(data)
    while pos < n and depth:
        c = data[pos]
        if c == ord("\\"):
            pos += 1
            if pos >= n:
                break
            nxt = data[pos]
            if nxt in (
                ord("n"),
                ord("r"),
                ord("t"),
                ord("b"),
                ord("f"),
                ord("("),
                ord(")"),
                ord("\\"),
            ):
                out.append(
                    {
                        ord("n"): 10,
                        ord("r"): 13,
                        ord("t"): 9,
                        ord("b"): 8,
                        ord("f"): 12,
                        ord("("): 40,
                        ord(")"): 41,
                        ord("\\"): 92,
                    }[nxt]
                )
                pos += 1
                continue
            if ord("0") <= nxt <= ord("7"):
                oct_s = bytes([nxt])
                pos += 1
                j = 0
                while j < 2 and pos < n and ord("0") <= data[pos] <= ord("7"):
                    oct_s += bytes([data[pos]])
                    pos += 1
                    j += 1
                out.append(int(oct_s, 8) & 0xFF)
                continue
        elif c == ord("("):
            depth += 1
            out.append(c)
        elif c == ord(")"):
            depth -= 1
            if depth:
                out.append(c)
        else:
            out.append(c)
        pos += 1
    return bytes(out), pos


def _parse_hex_string(data: bytes, pos: int) -> tuple[bytes, int]:
    pos += 1
    start = pos
    n = len(data)
    while pos < n and data[pos] != ord(">"):
        pos += 1
    hex_part = re.sub(rb"\s+", b"", data[start:pos])
    pos += 1
    if len(hex_part) % 2:
        hex_part += b"0"
    try:
        return bytes.fromhex(hex_part.decode("ascii")), pos
    except ValueError:
        return b"", pos


def _parse_array(data: bytes, pos: int) -> tuple[list[Any], int]:
    pos += 1
    items: list[Any] = []
    while True:
        pos = _skip_ws(data, pos)
        if pos >= len(data) or data[pos] == ord("]"):
            return items, pos + 1
        val, pos = _parse_value(data, pos)
        items.append(val)


def _parse_dict(data: bytes, pos: int) -> tuple[PdfDict, int]:
    pos += 2
    d: PdfDict = {}
    while True:
        pos = _skip_ws(data, pos)
        if pos + 1 < len(data) and data[pos : pos + 2] == b">>":
            return d, pos + 2
        if pos >= len(data):
            raise PDFSyntaxError("unterminated dictionary")
        if data[pos] != ord("/"):
            raise PDFSyntaxError(f"expected key name, pos={pos}")
        key, pos = _parse_name(data, pos)
        val, pos = _parse_value(data, pos)
        d[key] = val


def _parse_value(data: bytes, pos: int) -> tuple[Any, int]:
    pos = _skip_ws(data, pos)
    if pos >= len(data):
        raise PDFSyntaxError("unexpected end of data")
    c = data[pos]
    if c == ord("<"):
        if pos + 1 < len(data) and data[pos + 1] == ord("<"):
            return _parse_dict(data, pos)
        return _parse_hex_string(data, pos)
    if c == ord("["):
        return _parse_array(data, pos)
    if c == ord("("):
        return _parse_literal_string(data, pos)
    if c == ord("/"):
        return _parse_name(data, pos)
    if c in b"0123456789+-.":
        num1, pos2 = _parse_number(data, pos)
        pos3 = _skip_ws(data, pos2)
        if pos3 < len(data) and data[pos3] in b"0123456789":
            num2, pos4 = _parse_number(data, pos3)
            pos5 = _skip_ws(data, pos4)
            if pos5 < len(data) and data[pos5] == ord("R"):
                return (int(num1), int(num2)), pos5 + 1
        return num1, pos2
    if data[pos : pos + 4] == b"true":
        return True, pos + 4
    if data[pos : pos + 5] == b"false":
        return False, pos + 5
    if data[pos : pos + 4] == b"null":
        return None, pos + 4
    raise PDFSyntaxError(f"unknown token near pos={pos}: {data[pos:pos+20]!r}")


def _rdict(reader: Any, val: Any) -> PdfDict:
    """Resolve an indirect reference, return a dict or {}."""
    if isinstance(val, tuple) and len(val) == 2:
        try:
            val = reader.resolve(val)
        except Exception:
            return {}
    return val if isinstance(val, dict) else {}


def _rlist(reader: Any, val: Any) -> list:
    """Resolve an indirect reference, return a list or []."""
    if isinstance(val, tuple) and len(val) == 2:
        try:
            val = reader.resolve(val)
        except Exception:
            return []
    return val if isinstance(val, list) else ([] if val is None else [val])


def _merge_dicts(base: PdfDict, override: PdfDict) -> PdfDict:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _merge_dicts(out[k], v)
        else:
            out[k] = v
    return out


# ---------- stream filters ----------

def _ascii85_decode(data: bytes) -> bytes:
    if data.endswith(b"~>"):
        data = data[:-2]
    data = (
        data.replace(b"\n", b"")
        .replace(b"\r", b"")
        .replace(b" ", b"")
        .replace(b"\t", b"")
    )
    out = bytearray()
    buf = 0
    cnt = 0
    for ch in data:
        if ch == ord("z") and cnt == 0:
            out.extend(b"\x00\x00\x00\x00")
            continue
        if not (33 <= ch <= 117):
            continue
        buf = buf * 85 + (ch - 33)
        cnt += 1
        if cnt == 5:
            out.extend(buf.to_bytes(4, "big"))
            buf = 0
            cnt = 0
    if cnt:
        buf = buf * (85 ** (5 - cnt))
        out.extend(buf.to_bytes(4, "big")[: cnt - 1])
    return bytes(out)


def _ascii_hex_decode(data: bytes) -> bytes:
    cleaned = re.sub(rb"\s+", b"", data)
    if cleaned.endswith(b">"):
        cleaned = cleaned[:-1]
    if len(cleaned) % 2:
        cleaned += b"0"
    return bytes.fromhex(cleaned.decode("ascii", "ignore"))


def _flate_decode(data: bytes) -> bytes:
    """FlateDecode with fallback across wbits and partial decompression."""
    for wbits in (15, -15, 47):
        try:
            return zlib.decompress(data, wbits)
        except zlib.error:
            continue
    for wbits in (15, -15):
        try:
            d = zlib.decompressobj(wbits=wbits)
            return d.decompress(data)
        except zlib.error:
            continue
    return b""


def _decode_stream(payload: bytes, filters: list[str]) -> bytes:
    data = payload
    for flt in filters:
        if flt == "FlateDecode":
            data = _flate_decode(data)
        elif flt == "ASCII85Decode":
            data = _ascii85_decode(data)
        elif flt == "ASCIIHexDecode":
            data = _ascii_hex_decode(data)
        elif flt == "LZWDecode":
            return b""
    return data


def _normalize_filters(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw.lstrip("/")]
    if isinstance(raw, list):
        return [x.lstrip("/") if isinstance(x, str) else str(x) for x in raw]
    return []


# ---------- xref / objects ----------

class PDFReader:
    """Minimal PDF reader: xref, object streams, reference resolution."""

    def __init__(self, data: bytes) -> None:
        if not data.startswith(b"%PDF-"):
            raise ValueError("Not a PDF: missing %PDF- header")
        self.data = data
        self.trailer: PdfDict = {}
        self.xref: dict[int, tuple[int, int, int]] = {}
        self._cache: dict[int, Any] = {}
        self._stream_cache: dict[int, bytes] = {}
        try:
            self._parse_xref_chain()
        except Exception:
            pass
        if not self.xref:
            self._brute_scan()
        if not self.trailer.get("Root"):
            self._find_root_bruteforce()

    def _find_startxref(self) -> int:
        idx = self.data.rfind(b"startxref")
        if idx == -1:
            raise PDFSyntaxError("startxref not found")
        pos = _skip_ws(self.data, idx + 9)
        num, _ = _parse_number(self.data, pos)
        return int(num)

    def _parse_xref_chain(self) -> None:
        offsets_seen: set[int] = set()
        offset = self._find_startxref()
        latest_trailer: PdfDict = {}
        while offset and offset not in offsets_seen:
            offsets_seen.add(offset)
            if self.data[offset : offset + 4] == b"xref":
                trailer = self._parse_traditional_xref(offset)
            else:
                trailer = self._parse_xref_stream_obj(offset)
            if not latest_trailer:
                latest_trailer = trailer
            xstm = trailer.get("XRefStm")
            if xstm is not None and int(xstm) not in offsets_seen:
                try:
                    self._parse_xref_stream_obj(int(xstm))
                    offsets_seen.add(int(xstm))
                except Exception:
                    pass
            prev = trailer.get("Prev")
            offset = int(prev) if prev is not None else 0
        self.trailer = latest_trailer

    def _parse_traditional_xref(self, offset: int) -> PdfDict:
        pos = offset + 4
        while True:
            pos = _skip_ws(self.data, pos)
            if self.data[pos : pos + 7] == b"trailer":
                pos += 7
                pos = _skip_ws(self.data, pos)
                trailer, pos = _parse_value(self.data, pos)
                return trailer
            line, pos = _read_line(self.data, pos)
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                start = int(parts[0].decode("latin-1"))
                count = int(parts[1].decode("latin-1"))
            except (ValueError, AttributeError):
                continue
            for i in range(count):
                entry, pos = _read_line(self.data, pos)
                if len(entry) < 17:
                    continue
                try:
                    off = int(entry[:10].decode("latin-1").strip())
                    gen = int(entry[11:16].decode("latin-1").strip())
                except (ValueError, UnicodeDecodeError):
                    continue
                typ = entry[17:18]
                num = start + i
                if typ == b"f":
                    continue
                if num not in self.xref:
                    self.xref[num] = (1, off, gen)

    def _parse_xref_stream_obj(self, offset: int) -> PdfDict:
        obj = self._read_object_at(offset)
        if not isinstance(obj, dict) or obj.get("Type") != "XRef":
            raise PDFSyntaxError("expected XRef stream")
        payload = self._stream_payload(obj, offset)
        w = obj.get("W", [1, 2, 1])
        if not isinstance(w, list) or len(w) != 3:
            w = [1, 2, 1]
        w = [int(x) for x in w]
        size = int(obj.get("Size", 0))
        index = obj.get("Index", [0, size])
        if not isinstance(index, list):
            index = [0, size]
        rec_len = sum(w)
        pos = 0
        for idx in range(0, len(index) - 1, 2):
            start = int(index[idx])
            count = int(index[idx + 1])
            for i in range(count):
                entry = payload[pos : pos + rec_len]
                pos += rec_len
                if len(entry) < rec_len:
                    break
                typ = entry[0] if w[0] else 1
                f2 = int.from_bytes(entry[w[0] : w[0] + w[1]], "big") if w[1] else 0
                f3 = (
                    int.from_bytes(entry[w[0] + w[1] : w[0] + w[1] + w[2]], "big")
                    if w[2]
                    else 0
                )
                num = start + i
                if typ == 0:
                    continue
                if num not in self.xref:
                    self.xref[num] = (typ, f2, f3)
        return obj

    def _brute_scan(self) -> None:
        """Fallback: find all 'N G obj' via regex over the file."""
        for m in re.finditer(rb"(\d+)\s+(\d+)\s+obj\b", self.data):
            num = int(m.group(1))
            self.xref[num] = (1, m.start(), int(m.group(2)))

    def _find_root_bruteforce(self) -> None:
        m = re.search(rb"/Type\s*/Catalog", self.data)
        if not m:
            return
        back = self.data.rfind(b"obj", 0, m.start())
        if back == -1:
            return
        num_m = re.search(rb"(\d+)\s+\d+\s+obj\s*$", self.data[max(0, back - 30) : back + 3])
        if num_m:
            self.trailer["Root"] = (int(num_m.group(1)), 0)

    def _read_object_at(self, offset: int) -> Any:
        pos = _skip_ws(self.data, offset)
        obj_num, pos = _parse_number(self.data, pos)
        gen, pos = _parse_number(self.data, pos)
        pos = _skip_ws(self.data, pos)
        if self.data[pos : pos + 3] != b"obj":
            raise PDFSyntaxError(f"expected obj near {offset}")
        pos = _skip_ws(self.data, pos + 3)
        val, pos = _parse_value(self.data, pos)
        if isinstance(val, dict) and self._peek_stream(pos).startswith(b"stream"):
            stream_start = self._locate_stream(pos)
            length_val = val.get("Length")
            if isinstance(length_val, tuple):
                try:
                    length_val = self.get_object(length_val[0])
                except Exception:
                    length_val = None
            if isinstance(length_val, (int, float)) and int(length_val) > 0:
                raw = self.data[stream_start : stream_start + int(length_val)]
                tail = self.data[
                    stream_start + int(length_val) : stream_start + int(length_val) + 20
                ]
                if b"endstream" not in tail:
                    raw = self._raw_until_endstream(stream_start)
            else:
                raw = self._raw_until_endstream(stream_start)
            val["_stream_raw"] = raw
            val["_stream_offset"] = offset
        self._cache[int(obj_num)] = val
        return val

    def _raw_until_endstream(self, stream_start: int) -> bytes:
        endstream = self.data.find(b"endstream", stream_start)
        if endstream == -1:
            raise PDFSyntaxError("endstream not found")
        raw = self.data[stream_start:endstream]
        if raw.endswith(b"\r\n"):
            raw = raw[:-2]
        elif raw.endswith(b"\n") or raw.endswith(b"\r"):
            raw = raw[:-1]
        return raw

    def _peek_stream(self, pos: int) -> bytes:
        pos = _skip_ws(self.data, pos)
        return self.data[pos : pos + 10]

    def _locate_stream(self, pos: int) -> int:
        pos = _skip_ws(self.data, pos)
        if not self.data[pos : pos + 6].startswith(b"stream"):
            raise PDFSyntaxError("stream not found")
        pos += 6
        if self.data[pos : pos + 2] == b"\r\n":
            return pos + 2
        if pos < len(self.data) and self.data[pos] in (10, 13):
            return pos + 1
        return pos

    def resolve(self, ref: Any) -> Any:
        if not isinstance(ref, tuple) or len(ref) != 2:
            return ref
        obj_num, _gen = ref
        return self.get_object(int(obj_num))

    def get_object(self, obj_num: int) -> Any:
        if obj_num in self._cache:
            return self._cache[obj_num]
        entry = self.xref.get(obj_num)
        if not entry:
            raise PDFSyntaxError(f"object {obj_num} not found in xref")
        typ, f2, f3 = entry
        if typ == 1:
            return self._read_object_at(f2)
        if typ == 2:
            stm_num, idx = f2, f3
            stm_obj = self.get_object(stm_num)
            return self._extract_from_objstm(stm_obj, idx)
        raise PDFSyntaxError(f"unknown xref type for {obj_num}: {typ}")

    def _extract_from_objstm(self, stm_obj: Any, index: int) -> Any:
        payload = self._stream_payload(stm_obj)
        first = int(stm_obj.get("First", 0))
        header = payload[:first].decode("latin-1", "replace")
        nums = [int(x) for x in header.split()]
        pairs: list[tuple[int, int]] = []
        for i in range(0, len(nums) - 1, 2):
            pairs.append((nums[i], nums[i + 1]))
        if index >= len(pairs):
            raise PDFSyntaxError(f"index {index} out of ObjStm")
        obj_num, rel_off = pairs[index]
        start = first + rel_off
        end = first + pairs[index + 1][1] if index + 1 < len(pairs) else len(payload)
        chunk = payload[start:end]
        val, _ = _parse_value(chunk, 0)
        self._cache[obj_num] = val
        return val

    def _stream_payload(self, obj: PdfDict, offset: int | None = None) -> bytes:
        cache_key = id(obj)
        if cache_key in self._stream_cache:
            return self._stream_cache[cache_key]
        raw = obj.get("_stream_raw")
        if raw is None:
            if offset is not None:
                self._read_object_at(offset)
                raw = obj.get("_stream_raw", b"")
            else:
                raw = b""
        filters = _normalize_filters(obj.get("Filter"))
        data = _decode_stream(raw, filters) if filters else raw
        dp = obj.get("DecodeParms") or obj.get("DP")
        if isinstance(dp, list):
            dp = dp[0] if dp else None
        if isinstance(dp, dict) and int(dp.get("Predictor", 1)) >= 10:
            columns = int(dp.get("Columns", 1))
            data = self._unpredict_png(data, columns)
        self._stream_cache[cache_key] = data
        return data

    def _unpredict_png(self, data: bytes, columns: int) -> bytes:
        out = bytearray()
        prev = bytearray([0] * columns)
        i = 0
        n = len(data)
        stride = columns + 1
        while i + stride <= n:
            filt = data[i]
            row = bytearray(data[i + 1 : i + stride])
            i += stride
            if filt == 2:  # Up
                for j in range(columns):
                    row[j] = (row[j] + prev[j]) & 0xFF
            elif filt == 1:  # Sub
                for j in range(1, columns):
                    row[j] = (row[j] + row[j - 1]) & 0xFF
            out.extend(row)
            prev = row
        return bytes(out)

    def root(self) -> PdfDict:
        root = self.resolve(self.trailer.get("Root"))
        if not isinstance(root, dict):
            raise PDFSyntaxError("/Root not found or not a dict")
        return root

    def pages_tree(self) -> list[tuple[PdfDict, PdfDict]]:
        """[(page_dict, merged_resources), ...] in traversal order."""
        root = self.root()
        pages = self.resolve(root.get("Pages"))
        result = self._walk_pages(pages, {}, set())
        if result:
            return result
        out: list[tuple[PdfDict, PdfDict]] = []
        for num in sorted(self.xref):
            try:
                obj = self.get_object(num)
            except Exception:
                continue
            if isinstance(obj, dict) and obj.get("Type") == "Page":
                res = _rdict(self, obj.get("Resources"))
                out.append((obj, res))
        return out

    def _walk_pages(
        self, node: Any, inherited: PdfDict, seen: set
    ) -> list[tuple[PdfDict, PdfDict]]:
        if not isinstance(node, dict):
            return []
        res = _merge_dicts(inherited, _rdict(self, node.get("Resources")))
        if node.get("Type") == "Page":
            return [(node, res)]
        out: list[tuple[PdfDict, PdfDict]] = []
        for kid_ref in _rlist(self, node.get("Kids")):
            key = kid_ref if isinstance(kid_ref, tuple) else id(kid_ref)
            if key in seen:
                continue
            seen.add(key)
            kid = self.resolve(kid_ref)
            out.extend(self._walk_pages(kid, res, seen))
        return out


# ---------- CMap ----------

_CMAP_BFCHAR_RE = re.compile(rb"<([0-9A-Fa-f]+)>\s+<([0-9A-Fa-f]+)>")


def _parse_cmap(cmap_bytes: bytes) -> dict[int, str]:
    table: dict[int, str] = {}
    text = cmap_bytes.decode("latin-1", "replace")
    for m in re.finditer(r"beginbfchar(.*?)endbfchar", text, re.DOTALL):
        for src, dst in _CMAP_BFCHAR_RE.findall(m.group(1).encode()):
            try:
                code = int(src, 16)
                u = bytes.fromhex(dst.replace(b" ", b"").decode()).decode(
                    "utf-16-be", "replace"
                )
                if u:
                    table[code] = u
            except Exception:
                continue
    for m in re.finditer(r"beginbfrange(.*?)endbfrange", text, re.DOTALL):
        for src_lo, src_hi, dst0 in re.findall(
            r"<([0-9A-Fa-f]+)>\s+<([0-9A-Fa-f]+)>\s+<([0-9A-Fa-f]+)>", m.group(1)
        ):
            try:
                lo, hi = int(src_lo, 16), int(src_hi, 16)
                dst_bytes = bytes.fromhex(dst0)
                base_chars = dst_bytes.decode("utf-16-be", "replace")
                if len(base_chars) == 1:
                    d0 = ord(base_chars)
                    for off in range(hi - lo + 1):
                        table[lo + off] = chr(d0 + off)
                else:
                    for off, ch in enumerate(base_chars):
                        if lo + off <= hi:
                            table[lo + off] = ch
            except Exception:
                continue
    return table


def _font_cmap(reader: PDFReader, font_obj: Any) -> dict[int, str] | None:
    if not isinstance(font_obj, dict):
        return None
    tu = font_obj.get("ToUnicode")
    if tu:
        cmap_obj = reader.resolve(tu)
        if isinstance(cmap_obj, dict):
            return _parse_cmap(reader._stream_payload(cmap_obj))
    if font_obj.get("Subtype") == "Type0":
        desc = _rlist(reader, font_obj.get("DescendantFonts"))
        if desc:
            cid = reader.resolve(desc[0])
            if isinstance(cid, dict):
                tu2 = cid.get("ToUnicode")
                if tu2:
                    cmap_obj = reader.resolve(tu2)
                    if isinstance(cmap_obj, dict):
                        return _parse_cmap(reader._stream_payload(cmap_obj))
    return None


# ---------- text extraction ----------

_BT_RE = re.compile(rb"\bBT\b(.*?)\bET\b", re.DOTALL)
_DO_RE = re.compile(rb"/([A-Za-z][A-Za-z0-9_.+-]*)\s+Do\b")
_GARBAGE_RE = re.compile(r"(/Type\s|/Subtype\s|endobj|\d+\s+\d+\s+obj|/Length\s|/Filter\s)")


def _hex_to_bytes(hexstr: bytes) -> bytes:
    cleaned = re.sub(rb"\s+", b"", hexstr)
    if len(cleaned) % 2:
        cleaned += b"0"
    try:
        return bytes.fromhex(cleaned.decode("ascii"))
    except Exception:
        return b""


def _decode_bytes_to_text(raw: bytes, cmap: dict[int, str] | None, codespace: int) -> str:
    if not raw:
        return ""
    if cmap:
        out: list[str] = []
        for i in range(0, len(raw), codespace):
            chunk = raw[i : i + codespace]
            if len(chunk) < codespace:
                break
            code = int.from_bytes(chunk, "big")
            out.append(cmap.get(code, ""))
        return "".join(out)
    if codespace == 1:
        return raw.decode("latin-1", "replace")
    codes = " ".join(f"0x{raw[i]:02X}{raw[i+1]:02X}" for i in range(0, len(raw) - 1, 2))
    if len(raw) % 2:
        codes += f" 0x{raw[-1]:02X}"
    return f"[?{codes}]"


def _looks_like_pdf_garbage(text: str) -> bool:
    if not text or len(text) < 4:
        return False
    if _GARBAGE_RE.search(text):
        return True
    if text.count("/") >= 3 and any(k in text for k in ("Font", "Length", "Filter", "obj")):
        return True
    return False


def _tokenize_content(data: bytes):
    """Content-stream tokenizer, yields ('num'|'name'|'str'|'arr'|'op', value)."""
    pos = 0
    n = len(data)
    while pos < n:
        pos = _skip_ws(data, pos)
        if pos >= n:
            break
        c = data[pos]
        if c == ord("%"):
            while pos < n and data[pos] not in (10, 13):
                pos += 1
            continue
        if c == ord("/"):
            name, pos = _parse_name(data, pos)
            yield ("name", name)
            continue
        if c == ord("("):
            s, pos = _parse_literal_string(data, pos)
            yield ("str", s)
            continue
        if c == ord("<"):
            if pos + 1 < n and data[pos + 1] == ord("<"):
                try:
                    _d, pos = _parse_dict(data, pos)
                except PDFSyntaxError:
                    pos += 2
                continue
            s, pos = _parse_hex_string(data, pos)
            yield ("str", s)
            continue
        if c == ord("["):
            try:
                arr, pos = _parse_array(data, pos)
                yield ("arr", arr)
            except PDFSyntaxError:
                pos += 1
            continue
        if c in b"]>)}":
            pos += 1
            continue
        if c in b"+-.0123456789":
            try:
                num, pos = _parse_number(data, pos)
                yield ("num", num)
            except PDFSyntaxError:
                pos += 1
            continue
        start = pos
        while pos < n and not _is_white(data[pos]) and data[pos] not in b"/[]<>(){}%":
            pos += 1
        op = data[start:pos]
        if not op:
            pos += 1
            continue
        if op == b"BI":
            id_pos = data.find(b"ID", pos)
            ei_pos = data.find(b"EI", id_pos + 2) if id_pos != -1 else -1
            pos = ei_pos + 2 if ei_pos != -1 else n
            continue
        yield ("op", op)


class PageTextExtractor:
    def __init__(self, reader: PDFReader, resources: PdfDict) -> None:
        self.reader = reader
        self.resources = resources
        self.font_cmaps: dict[str, dict[int, str] | None] = {}

    def _font_cmap(self, font_name: str) -> tuple[dict[int, str] | None, int]:
        if font_name in self.font_cmaps:
            cmap = self.font_cmaps[font_name]
            return cmap, (2 if cmap else 1)
        fonts = _rdict(self.reader, self.resources.get("Font"))
        ref = fonts.get(font_name)
        cmap = None
        if ref is not None:
            font_obj = self.reader.resolve(ref)
            cmap = _font_cmap(self.reader, font_obj)
        self.font_cmaps[font_name] = cmap
        return cmap, (2 if cmap else 1)

    def extract_from_stream(
        self, stream: bytes, depth: int = 0
    ) -> list[tuple[float, float, float, str]]:
        out: list[tuple[float, float, float, str]] = []
        if depth > 8:
            return out
        xobjs = _rdict(self.reader, self.resources.get("XObject"))

        stack: list[Any] = []
        cur_size = 0.0
        cur_cmap: dict[int, str] | None = None
        cur_codespace = 1
        line_x = line_y = 0.0
        cur_x = cur_y = 0.0

        def emit(text: str) -> None:
            t = text.strip()
            if t and not _looks_like_pdf_garbage(t):
                out.append((cur_size, cur_x, cur_y, t))

        def _num(v: Any) -> float:
            return float(v) if isinstance(v, (int, float)) else 0.0

        for typ, val in _tokenize_content(stream):
            if typ != "op":
                stack.append(val)
                continue

            if val == b"Tf":
                if len(stack) >= 2:
                    name = stack[-2]
                    cur_size = _num(stack[-1])
                    if isinstance(name, str):
                        cur_cmap, cur_codespace = self._font_cmap(name)
            elif val == b"BT":
                line_x = line_y = cur_x = cur_y = 0.0
            elif val in (b"Td", b"TD"):
                if len(stack) >= 2:
                    line_x += _num(stack[-2])
                    line_y += _num(stack[-1])
                    cur_x, cur_y = line_x, line_y
            elif val == b"Tm":
                if len(stack) >= 6:
                    line_x = _num(stack[-2])
                    line_y = _num(stack[-1])
                    cur_x, cur_y = line_x, line_y
            elif val == b"T*":
                cur_x, cur_y = line_x, line_y
            elif val in (b"Tj", b"'"):
                if val == b"'":
                    cur_x, cur_y = line_x, line_y
                if stack and isinstance(stack[-1], (bytes, bytearray)):
                    emit(_decode_bytes_to_text(bytes(stack[-1]), cur_cmap, cur_codespace))
            elif val == b'"':
                if stack and isinstance(stack[-1], (bytes, bytearray)):
                    emit(_decode_bytes_to_text(bytes(stack[-1]), cur_cmap, cur_codespace))
            elif val == b"TJ":
                if stack and isinstance(stack[-1], list):
                    parts: list[str] = []
                    for el in stack[-1]:
                        if isinstance(el, (bytes, bytearray)):
                            parts.append(
                                _decode_bytes_to_text(bytes(el), cur_cmap, cur_codespace)
                            )
                    emit("".join(parts))
            elif val == b"Do":
                if stack and isinstance(stack[-1], str):
                    ref = xobjs.get(stack[-1])
                    if ref is not None:
                        xobj = self.reader.resolve(ref)
                        if isinstance(xobj, dict) and xobj.get("Subtype") == "Form":
                            form_res = _merge_dicts(
                                self.resources, _rdict(self.reader, xobj.get("Resources"))
                            )
                            nested = PageTextExtractor(self.reader, form_res)
                            payload = self.reader._stream_payload(xobj)
                            out.extend(nested.extract_from_stream(payload, depth + 1))

            stack.clear()
        return out

    def extract_page(self, page: PdfDict) -> list[tuple[float, float, float, str]]:
        contents = page.get("Contents")
        if contents is None:
            return []
        refs = contents if isinstance(contents, list) else [contents]
        out: list[tuple[float, float, float, str]] = []
        for ref in refs:
            obj = self.reader.resolve(ref)
            if isinstance(obj, dict):
                data = self.reader._stream_payload(obj)
            elif isinstance(obj, (bytes, bytearray)):
                data = bytes(obj)
            else:
                continue
            out.extend(self.extract_from_stream(data))
        return out


# ---------- Markdown ----------

_LIST_RE = re.compile(r"^([\u2022\u00b7\u25cf\u25cb\u25e6\u25aa\u25ab\-\u2014\u2013]|\d+[.)])\s+")


def _group_into_lines(
    items: list[tuple[float, float, float, str]]
) -> list[tuple[float, str]]:
    if not items:
        return []
    items.sort(key=lambda r: (-r[2], r[1]))
    lines: list[tuple[float, str]] = []
    cur_y: float | None = None
    cur_size = 0.0
    cur_text: list[str] = []
    for size, _x, y, t in items:
        if cur_y is None or abs(cur_y - y) > max(2.0, size * 0.5):
            if cur_text:
                lines.append((cur_size, " ".join(cur_text).strip()))
            cur_y, cur_size, cur_text = y, size, [t]
        else:
            cur_text.append(t)
            cur_size = max(cur_size, size)
    if cur_text:
        lines.append((cur_size, " ".join(cur_text).strip()))
    return lines


def _looks_like_heading(text: str, size: float, base_size: float) -> int | None:
    if not text or len(text) > 120:
        return None
    if text.endswith((".", ":", ";")):
        return None
    if size <= base_size * 1.05:
        return None
    if size >= base_size * 1.6:
        return 1
    if size >= base_size * 1.3:
        return 2
    return 3


def _norm_key(text: str) -> str:
    """Normalized key with digits collapsed, so page-varying header/footer
    lines (``Стр. 5`` / ``Стр. 6``) map to a single key."""
    t = re.sub(r"\s+", " ", text).strip().lower()
    return re.sub(r"\d+", "#", t)


# Page numbers / footers: bare numbers, "- 5 -", "стр. 5", "страница 5 из 10",
# "page 5", "5 из 10", "5/10", roman-ish "5 of 12".
_PAGE_NUMBER_RE = re.compile(
    r"^\s*(?:"
    r"[-\u2013\u2014]?\s*\d{1,4}\s*[-\u2013\u2014]?"
    r"|(?:стр(?:аница)?\.?|лист|page|pg\.?)\s*\.?\s*\d{1,4}"
    r"(?:\s*(?:из|of|/)\s*\d{1,4})?"
    r"|\d{1,4}\s*(?:из|of|/)\s*\d{1,4}"
    r")\s*$",
    re.IGNORECASE,
)

# Service / boilerplate lines (copyright, rights notices).
_SERVICE_RE = re.compile(
    r"^\s*(?:\u00a9|\(c\)|(?:copyright|все права защищены|all rights reserved)\b)",
    re.IGNORECASE,
)

# Project-specific stale/service strings can be added here (matched with search).
EXTRA_DROP_PATTERNS: list[re.Pattern[str]] = []


def _is_droppable_line(text: str) -> bool:
    """True for page numbers, footers and boilerplate service lines."""
    stripped = text.strip()
    if not stripped:
        return False
    if len(stripped) <= 30 and _PAGE_NUMBER_RE.match(stripped):
        return True
    if len(stripped) <= 80 and _SERVICE_RE.match(stripped):
        return True
    return any(pat.search(stripped) for pat in EXTRA_DROP_PATTERNS)


def _detect_running_lines(pages_lines: list[list[tuple[float, str]]]) -> set[str]:
    """Header/footer lines: same text (ignoring page numbers) on many pages."""
    from collections import Counter

    counter: Counter[str] = Counter()
    for lines in pages_lines:
        seen_on_page: set[str] = set()
        for _size, text in lines:
            key = _norm_key(text)
            if key and len(key) <= 90 and key not in seen_on_page:
                seen_on_page.add(key)
                counter[key] += 1
    if len(pages_lines) < 3:
        return set()
    threshold = max(3, int(len(pages_lines) * 0.4))
    return {key for key, cnt in counter.items() if cnt >= threshold}


def _dedupe_consecutive(md_lines: list[str]) -> list[str]:
    """Drop content lines identical to the previous emitted content line
    (common at page boundaries where a title/line repeats)."""
    out: list[str] = []
    last_key: str | None = None
    for line in md_lines:
        if line.strip():
            key = _norm_key(line)
            if key and key == last_key:
                continue
            last_key = key
        out.append(line)
    return out


def _page_to_md(
    lines: list[tuple[float, str]],
    _page_idx: int,
    repeated: set[str],
) -> str:
    if not lines:
        return ""
    sizes = [s for s, _ in lines if s > 0]
    base = sorted(sizes)[len(sizes) // 2] if sizes else 10.0
    if base <= 0:
        base = 10.0

    out: list[str] = []
    for size, text in lines:
        text = re.sub(r"[ \t]+", " ", text).strip()
        if not text or _looks_like_pdf_garbage(text):
            continue
        if _norm_key(text) in repeated:  # header/footer repeated across pages
            continue
        if _is_droppable_line(text):  # page number / footer / service line
            continue
        lvl = _looks_like_heading(text, size, base)
        if lvl is not None:
            out.extend(["", f"{'#' * lvl} {text}", ""])
            continue
        if _LIST_RE.match(text):
            out.append(f"- {text}")
            continue
        out.append(text)
    return "\n".join(out)


def convert(pdf_path: Path) -> str:
    data = pdf_path.read_bytes()
    reader = PDFReader(data)
    pages = reader.pages_tree()

    pages_lines: list[list[tuple[float, str]]] = []
    for page, resources in pages:
        extractor = PageTextExtractor(reader, resources)
        try:
            items = extractor.extract_page(page)
        except Exception:
            items = []
        pages_lines.append(_group_into_lines(items))

    repeated = _detect_running_lines(pages_lines)

    chunks: list[str] = []
    for idx, lines in enumerate(pages_lines):
        md = _page_to_md(lines, idx, repeated)
        if md.strip():
            chunks.append(md)

    md = "\n".join(chunks)
    md = "\n".join(_dedupe_consecutive(md.split("\n")))
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    if "[?0x" in md:
        md = (
            "<!-- WARNING: some text was not decoded (no /ToUnicode CMap). "
            "Hex glyph codes are shown in square brackets. -->\n\n" + md
        )
    if not md:
        raise ValueError("No text extracted - the PDF may be a scan or encrypted")
    return md + "\n"


def diagnose(pdf_path: Path) -> None:
    """Print parsing diagnostics to understand where extraction breaks."""
    data = pdf_path.read_bytes()
    print(f"file: {pdf_path.name}")
    print(f"size: {len(data)} bytes")
    print(f"header: {data[:12]!r}")
    enc = re.search(rb"/Encrypt\b", data)
    print(f"/Encrypt present: {'YES (encrypted)' if enc else 'no'}")

    reader = PDFReader(data)
    print(f"objects in xref: {len(reader.xref)}")
    print(f"trailer Root: {reader.trailer.get('Root')}")

    try:
        pages = reader.pages_tree()
    except Exception as exc:
        print(f"pages_tree failed: {exc}")
        pages = []
    print(f"pages found: {len(pages)}")

    total_items = 0
    for idx, (page, resources) in enumerate(pages[:3]):
        contents = page.get("Contents")
        refs = contents if isinstance(contents, list) else [contents]
        print(f"\n--- page {idx+1} ---")
        print(f"  Contents refs: {refs}")
        print(f"  Resources keys: {list(resources.keys())}")
        extractor = PageTextExtractor(reader, resources)
        try:
            items = extractor.extract_page(page)
        except Exception as exc:
            print(f"  extract_page failed: {exc}")
            items = []
        total_items += len(items)
        print(f"  text fragments: {len(items)}")
        if items:
            print(f"  samples: {[t for *_, t in items[:5]]}")
    print(f"\nTOTAL fragments on first pages: {total_items}")
