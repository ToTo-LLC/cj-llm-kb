// Build the ``obsidian://open?vault=&file=`` URI used by the
// Browse meta-strip's "Open in Obsidian" button. Plan 07 Task 18.
//
// Both params are URL-encoded so whitespace + slashes survive
// handoff to ``open --url`` (macOS) and ``start`` (Windows).
// ``encodeURIComponent`` — not ``encodeURI`` — because we want
// ``/`` in the relative path to become ``%2F``; Obsidian's
// URL handler accepts both encoded and raw paths, but we keep
// the encoded form so edge characters round-trip reliably across
// shells.

/** Build the ``obsidian://open?vault=…&file=…`` URI. */
export function buildObsidianUri(
  vaultName: string,
  relativePath: string,
): string {
  const vault = encodeURIComponent(vaultName);
  const file = encodeURIComponent(relativePath);
  return `obsidian://open?vault=${vault}&file=${file}`;
}
