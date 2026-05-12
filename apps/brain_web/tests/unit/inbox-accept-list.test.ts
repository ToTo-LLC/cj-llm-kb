import { describe, expect, test } from "vitest";

/**
 * Inbox drop-zone accept list (Plan 24 T5).
 *
 * The frontend advertises the supported upload formats through
 * ``INGEST_ACCEPT`` — a Readonly MIME → extensions map — and a
 * helper ``ingestAcceptAttribute()`` that serializes the map into
 * the comma-separated string a native ``<input type="file" accept=...>``
 * expects. Plan 24 added Office Open XML formats (.docx + .pptx) and
 * these tests pin the canonical MIME types so a future refactor that
 * accidentally drops or mis-spells either entry fails RED.
 *
 * The MIME types below are the IANA-registered Office Open XML
 * identifiers; browsers report ``.docx`` as the wordprocessingml MIME
 * and ``.pptx`` as the presentationml MIME (verified across Safari /
 * Chrome / Edge on Mac + Windows during Plan 24 T5).
 */

import {
  INGEST_ACCEPT,
  ingestAcceptAttribute,
} from "@/lib/state/inbox-store";

const DOCX_MIME =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
const PPTX_MIME =
  "application/vnd.openxmlformats-officedocument.presentationml.presentation";

describe("INGEST_ACCEPT (Plan 24 T5)", () => {
  test("includes the canonical .docx MIME type with the .docx extension", () => {
    expect(INGEST_ACCEPT[DOCX_MIME]).toEqual([".docx"]);
  });

  test("includes the canonical .pptx MIME type with the .pptx extension", () => {
    expect(INGEST_ACCEPT[PPTX_MIME]).toEqual([".pptx"]);
  });

  test("preserves the existing text + pdf + email entries (no regression)", () => {
    // Regression guard: Plan 24 T5 only adds entries — the existing
    // text-ish, PDF, and email entries the inbox depended on before
    // Plan 24 must survive untouched.
    expect(INGEST_ACCEPT["text/plain"]).toContain(".txt");
    expect(INGEST_ACCEPT["text/markdown"]).toContain(".md");
    expect(INGEST_ACCEPT["application/pdf"]).toContain(".pdf");
    expect(INGEST_ACCEPT["message/rfc822"]).toContain(".eml");
  });
});

describe("ingestAcceptAttribute() (Plan 24 T5)", () => {
  test("serializes to a comma-separated string containing both MIMEs + extensions", () => {
    const attr = ingestAcceptAttribute();
    // MIME forms — what content-aware browsers consume.
    expect(attr).toContain(DOCX_MIME);
    expect(attr).toContain(PPTX_MIME);
    // Extension forms — Safari historically needs these for Office
    // Open XML files to even appear in the picker on macOS.
    expect(attr).toContain(".docx");
    expect(attr).toContain(".pptx");
    // Sanity: it's a non-empty comma-separated list.
    expect(attr.split(",").length).toBeGreaterThan(4);
  });
});
