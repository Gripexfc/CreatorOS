const CREATE_ENTRY_ORIGIN_KEY = 'creatoros:content-entry-origin';
const CREATE_HANDOFF_KEYS = [
  'creatoros:selected-hotspot',
  'creatoros:editing-draft',
  'creatoros:compose-form',
] as const;

export type CreateEntryOrigin = 'hotspot' | 'direct';

/**
 * Mark the next content-workspace mount as a direct creation entry.
 * Clearing the hand-off envelopes here prevents a previous hotspot or draft
 * from leaking into a new blank composition.
 */
export const beginDirectCreate = () => {
  try {
    window.localStorage.setItem(CREATE_ENTRY_ORIGIN_KEY, 'direct');
    CREATE_HANDOFF_KEYS.forEach(key => window.localStorage.removeItem(key));
  } catch {
    // The editor can still open blank when browser storage is unavailable.
  }
  // If the editor is already mounted, reset it immediately instead of
  // leaving the one-shot marker for a later, unrelated hand-off.
  window.dispatchEvent(new CustomEvent('creatoros:new-content'));
};

/** Mark the next content-workspace mount as a hotspot hand-off. */
export const beginHotspotCreate = () => {
  try {
    window.localStorage.setItem(CREATE_ENTRY_ORIGIN_KEY, 'hotspot');
  } catch {
    // The selected hotspot remains usable when storage is available.
  }
};

/** Consume the one-shot origin marker used by navigation hand-offs. */
export const consumeCreateEntryOrigin = (): CreateEntryOrigin | '' => {
  try {
    const value = window.localStorage.getItem(CREATE_ENTRY_ORIGIN_KEY);
    window.localStorage.removeItem(CREATE_ENTRY_ORIGIN_KEY);
    return value === 'hotspot' || value === 'direct' ? value : '';
  } catch {
    return '';
  }
};

/** Remove a marker left behind when a page is reset without remounting. */
export const clearCreateEntryOrigin = () => {
  try { window.localStorage.removeItem(CREATE_ENTRY_ORIGIN_KEY); } catch { /* optional browser storage */ }
};
