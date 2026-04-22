// Build the grouped-tree data structure used by the Browse file
// tree. Plan 07 Task 18.
//
// Input: a flat array of note descriptors (domain, folder, path,
// title). Output: a nested ``domain → folder → note[]`` shape that
// preserves input order for stable rendering, and exposes a
// convenience ``domains`` list for render iteration.

export interface TreeNote {
  path: string;
  title: string;
  domain: string;
  folder: string;
}

export interface TreeFolder {
  folder: string;
  notes: TreeNote[];
}

export interface TreeDomain {
  domain: string;
  folders: TreeFolder[];
}

export interface VaultTree {
  domains: TreeDomain[];
}

/**
 * Group notes into a ``{domain: {folder: [notes]}}`` structure.
 *
 * Order of appearance is preserved — the first time a domain or
 * folder is seen, it becomes the next entry in the output. Further
 * encounters append to the same group. This keeps the file tree
 * render stable across re-fetches (no shuffling on network hits).
 */
export function buildTree(notes: TreeNote[]): VaultTree {
  const domainMap = new Map<string, Map<string, TreeNote[]>>();
  for (const note of notes) {
    let folderMap = domainMap.get(note.domain);
    if (!folderMap) {
      folderMap = new Map();
      domainMap.set(note.domain, folderMap);
    }
    let bucket = folderMap.get(note.folder);
    if (!bucket) {
      bucket = [];
      folderMap.set(note.folder, bucket);
    }
    bucket.push(note);
  }

  const domains: TreeDomain[] = [];
  for (const [domain, folderMap] of domainMap) {
    const folders: TreeFolder[] = [];
    for (const [folder, bucket] of folderMap) {
      folders.push({ folder, notes: bucket });
    }
    domains.push({ domain, folders });
  }
  return { domains };
}
