import { describe, expect, test, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
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
});
