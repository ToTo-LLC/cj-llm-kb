import { describe, expect, test, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

/**
 * DropZone (Plan 07 Task 17) — big idle/drag-over target with a
 * "Browse files" + "Paste a URL" action row. Drag-enter adds a
 * highlight class; drop forwards the first file to ``uploadFile``;
 * clicking Browse triggers the hidden file input.
 *
 * Tests mock ``@/lib/ingest/upload`` so the drop handler exercises the
 * wiring without hitting the network. The ``uploadFile`` mock resolves
 * to a fake ``patch_id`` so the drop handler can finish its toast /
 * store-update chain in the implementation.
 */

const { uploadFileMock } = vi.hoisted(() => ({
  uploadFileMock: vi.fn(),
}));

vi.mock("@/lib/ingest/upload", () => ({
  uploadFile: uploadFileMock,
}));

import { DropZone } from "@/components/inbox/drop-zone";
import { useInboxStore } from "@/lib/state/inbox-store";

describe("DropZone", () => {
  beforeEach(() => {
    uploadFileMock.mockReset();
    uploadFileMock.mockResolvedValue({ patch_id: "p-1" });
  });

  test("drag-enter adds a drag-over highlight class", () => {
    render(<DropZone />);
    const root = screen.getByTestId("drop-zone");
    expect(root.className).not.toMatch(/drag-over/);

    fireEvent.dragEnter(root, {
      dataTransfer: { types: ["Files"] },
    });
    expect(root.className).toMatch(/drag-over/);

    fireEvent.dragLeave(root);
    expect(root.className).not.toMatch(/drag-over/);
  });

  test("drop forwards the dropped file to uploadFile()", () => {
    render(<DropZone />);
    const root = screen.getByTestId("drop-zone");
    const file = new File(["# hello\n"], "note.md", { type: "text/markdown" });

    fireEvent.drop(root, {
      dataTransfer: {
        files: [file],
        types: ["Files"],
      },
    });

    expect(uploadFileMock).toHaveBeenCalledTimes(1);
    const arg = uploadFileMock.mock.calls[0][0] as File;
    expect(arg.name).toBe("note.md");
    expect(arg.type).toBe("text/markdown");
  });

  test("upload success does NOT write res.domain into the inbox row (Plan 19 T2)", async () => {
    // Reset the inbox store to a known empty state so we can read the
    // row we drop in for this test only.
    useInboxStore.setState({ sources: [], activeTab: "progress" });

    // The backend's ``UploadResponse`` only emits ``{patch_id: str}`` —
    // ``domain`` is NEVER present. Plan 18 T1-class regression: the
    // drop-zone caller used to write ``res.domain`` (always undefined)
    // into the inbox row's ``domain`` field, silently clobbering it.
    // Post-fix, the row's ``domain`` should remain at its optimistic
    // placeholder (``null``) until ``inbox-store``'s ``recentIngests``
    // poll fills the actual classified domain.
    uploadFileMock.mockResolvedValueOnce({ patch_id: "p-narrow" });

    render(<DropZone />);
    const root = screen.getByTestId("drop-zone");
    const file = new File(["# note\n"], "note.md", { type: "text/markdown" });

    fireEvent.drop(root, {
      dataTransfer: { files: [file], types: ["Files"] },
    });

    // Wait for the optimistic row + the post-upload status flip.
    await waitFor(() => {
      const sources = useInboxStore.getState().sources;
      expect(sources).toHaveLength(1);
      expect(sources[0].status).toBe("done");
    });

    const row = useInboxStore.getState().sources[0];
    // The fix: ``domain`` stays at the optimistic placeholder (``null``)
    // — NOT ``undefined`` (the pre-fix bug shape).
    expect(row.domain).toBeNull();
    expect(row.progress).toBe(100);
  });

  test("Browse files button opens the hidden file picker", () => {
    const { container } = render(<DropZone />);
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement | null;
    expect(input).not.toBeNull();
    const clickSpy = vi.spyOn(input as HTMLInputElement, "click");

    fireEvent.click(screen.getByRole("button", { name: /browse files/i }));
    expect(clickSpy).toHaveBeenCalled();
  });

  // Plan 24 T5: the hidden ``<input type="file">`` carries an
  // ``accept`` attribute that filters the native picker to the
  // supported formats. The docx + pptx Office Open XML MIME types
  // and their extensions are the Plan 24 additions — assert both
  // are present so a regression that drops the helper or rewires
  // the input forgetting ``accept`` fails RED.
  test("hidden file input advertises .docx + .pptx in its accept attribute", () => {
    const { container } = render(<DropZone />);
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement | null;
    expect(input).not.toBeNull();
    const accept = input!.getAttribute("accept") ?? "";
    // Office Open XML MIMEs.
    expect(accept).toContain(
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    );
    expect(accept).toContain(
      "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    );
    // Extensions — needed by Safari + some Windows picker variants.
    expect(accept).toContain(".docx");
    expect(accept).toContain(".pptx");
  });

  // Plan 24 T5.5: the optimistic inbox row inserted on drop must carry
  // the right ``IngestType`` based on the filename's extension. Pre-T5.5
  // every drop hardcoded ``type: "file"`` so docx / pptx uploads
  // briefly rendered the generic ``FileIcon`` for the upload-window
  // duration (between drop and backend completion) even though Plan 24
  // T5 wired dedicated FileText / Presentation icons.
  test("handleFile infers `docx` type from .docx extension (Plan 24 T5.5)", () => {
    useInboxStore.setState({ sources: [], activeTab: "progress" });
    render(<DropZone />);
    const root = screen.getByTestId("drop-zone");
    const file = new File(["fake docx bytes"], "strategy.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });

    fireEvent.drop(root, {
      dataTransfer: { files: [file], types: ["Files"] },
    });

    const sources = useInboxStore.getState().sources;
    expect(sources).toHaveLength(1);
    // The optimistic row's type matches the extension-sniff result —
    // NOT the pre-T5.5 hardcoded "file".
    expect(sources[0].type).toBe("docx");
  });

  test("handleFile infers `pptx` type from .pptx extension (Plan 24 T5.5)", () => {
    useInboxStore.setState({ sources: [], activeTab: "progress" });
    render(<DropZone />);
    const root = screen.getByTestId("drop-zone");
    const file = new File(["fake pptx bytes"], "deck.pptx", {
      type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    });

    fireEvent.drop(root, {
      dataTransfer: { files: [file], types: ["Files"] },
    });

    const sources = useInboxStore.getState().sources;
    expect(sources).toHaveLength(1);
    expect(sources[0].type).toBe("pptx");
  });

  test("handleFile falls back to `file` for unknown extension (Plan 24 T5.5)", () => {
    // The fallback branch — unknown extensions still produce a typed
    // optimistic row rather than throwing, matching the pre-T5.5
    // default behavior for the surface area not covered by the
    // extension-sniff helper.
    useInboxStore.setState({ sources: [], activeTab: "progress" });
    render(<DropZone />);
    const root = screen.getByTestId("drop-zone");
    const file = new File(["binary bytes"], "data.xyz", {
      type: "application/octet-stream",
    });

    fireEvent.drop(root, {
      dataTransfer: { files: [file], types: ["Files"] },
    });

    const sources = useInboxStore.getState().sources;
    expect(sources).toHaveLength(1);
    expect(sources[0].type).toBe("file");
  });

  test("drop forwards a .docx file to uploadFile() (Plan 24 T5)", () => {
    // End-to-end wiring smoke: a .docx file with the canonical
    // wordprocessingml MIME type lands at ``uploadFile`` unchanged.
    // The drag-drop path is deliberately permissive (the input's
    // accept attribute only governs the native picker), so the
    // backend remains the validation gate; this test pins the
    // handler-doesn't-filter-out behaviour.
    render(<DropZone />);
    const root = screen.getByTestId("drop-zone");
    const file = new File(["fake docx bytes"], "strategy.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });

    fireEvent.drop(root, {
      dataTransfer: { files: [file], types: ["Files"] },
    });

    expect(uploadFileMock).toHaveBeenCalledTimes(1);
    const arg = uploadFileMock.mock.calls[0][0] as File;
    expect(arg.name).toBe("strategy.docx");
    expect(arg.type).toBe(
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    );
  });
});
