import hashlib
import re
from dataclasses import dataclass


PARSER_VERSION = "txt-md-parser/0.1.0"
CHUNKER_VERSION = "line-heading-chunker/0.1.0"
SUPPORTED_TEXT_MIME_TYPES = {"text/plain", "text/markdown", "text/x-markdown"}


@dataclass(frozen=True)
class ParsedChunk:
    chunk_id: str
    chunk_index: int
    content: str
    content_hash: str
    chunk_hash: str
    token_count: int
    line_start: int
    line_end: int
    section_path: tuple[str, ...]
    citation_locator: str
    parser_version: str
    chunker_version: str


def parse_txt_md_document(
    *,
    document_id: str,
    document_version: str,
    title: str,
    mime_type: str,
    source_text: str,
    chunk_size: int = 900,
) -> list[ParsedChunk]:
    if mime_type not in SUPPORTED_TEXT_MIME_TYPES:
        raise ValueError(f"Unsupported text parser MIME type: {mime_type}")

    normalized_text = source_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized_text.split("\n")
    is_markdown = mime_type in {"text/markdown", "text/x-markdown"}
    chunks: list[ParsedChunk] = []
    heading_path: list[str] = []
    block_lines: list[str] = []
    block_start = 0
    block_heading_path: tuple[str, ...] = ()

    def flush_block(end_line: int) -> None:
        nonlocal block_lines, block_start, block_heading_path
        content = "\n".join(line.strip() for line in block_lines).strip()
        if not content:
            block_lines = []
            block_start = 0
            block_heading_path = ()
            return

        for segment in _split_oversized_content(content, chunk_size):
            chunk_index = len(chunks)
            chunks.append(
                _build_chunk(
                    document_id=document_id,
                    document_version=document_version,
                    title=title,
                    chunk_index=chunk_index,
                    content=segment,
                    line_start=block_start,
                    line_end=end_line,
                    section_path=block_heading_path,
                )
            )

        block_lines = []
        block_start = 0
        block_heading_path = ()

    for line_number, raw_line in enumerate(lines, start=1):
        heading = _parse_markdown_heading(raw_line) if is_markdown else None
        if heading is not None:
            flush_block(line_number - 1)
            level, text = heading
            heading_path = heading_path[: level - 1] + [text]
            continue

        if not raw_line.strip():
            flush_block(line_number - 1)
            continue

        if not block_lines:
            block_start = line_number
            block_heading_path = tuple(heading_path)
        block_lines.append(raw_line)

    flush_block(len(lines))
    return chunks


def _build_chunk(
    *,
    document_id: str,
    document_version: str,
    title: str,
    chunk_index: int,
    content: str,
    line_start: int,
    line_end: int,
    section_path: tuple[str, ...],
) -> ParsedChunk:
    content_hash = _sha256(content)
    locator = _citation_locator(title, section_path, line_start, line_end)
    locator_hash = hashlib.sha256(locator.encode("utf-8")).hexdigest()[:8]
    chunk_hash = _sha256(f"{content_hash}:{locator}")
    chunk_id = (
        f"{document_id}:{document_version}:l{line_start}-{line_end}:"
        f"c{chunk_index:03d}:{locator_hash}"
    )
    return ParsedChunk(
        chunk_id=chunk_id,
        chunk_index=chunk_index,
        content=content,
        content_hash=content_hash,
        chunk_hash=chunk_hash,
        token_count=len(content.split()),
        line_start=line_start,
        line_end=line_end,
        section_path=section_path,
        citation_locator=locator,
        parser_version=PARSER_VERSION,
        chunker_version=CHUNKER_VERSION,
    )


def _citation_locator(
    title: str,
    section_path: tuple[str, ...],
    line_start: int,
    line_end: int,
) -> str:
    section = " > ".join(section_path) if section_path else "body"
    return f"{title} / {section} / lines {line_start}-{line_end}"


def _parse_markdown_heading(line: str) -> tuple[int, str] | None:
    match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
    if match is None:
        return None
    return len(match.group(1)), match.group(2).strip()


def _sha256(value: str) -> str:
    return "sha256-" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _split_oversized_content(content: str, chunk_size: int) -> list[str]:
    if len(content) <= chunk_size:
        return [content]

    segments: list[str] = []
    remaining = content
    while len(remaining) > chunk_size:
        split_at = remaining.rfind(" ", 0, chunk_size)
        if split_at < max(chunk_size // 2, 1):
            split_at = chunk_size
        segments.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()

    if remaining:
        segments.append(remaining)
    return segments
