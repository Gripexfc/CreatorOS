export type ContentTraceLevel = 'info' | 'success' | 'warning' | 'error';

export type ContentTraceEvent = {
  id: string;
  at: string;
  level: ContentTraceLevel;
  event: string;
  sessionId?: string;
  details: Record<string, unknown>;
};

const STORAGE_KEY = 'creatoros:content-trace';
const MAX_EVENTS = 300;

const safeValue = (value: unknown): unknown => {
  if (value == null || typeof value === 'number' || typeof value === 'boolean') return value;
  if (typeof value === 'string') return value.slice(0, 240);
  if (Array.isArray(value)) return value.slice(0, 20).map(safeValue);
  return '[object]';
};

const safeDetails = (details: Record<string, unknown> | undefined) => Object.fromEntries(
  Object.entries(details || {}).map(([key, value]) => [key, safeValue(value)]),
);

const eventId = () => {
  try { return crypto.randomUUID(); } catch { return `${Date.now()}-${Math.random().toString(16).slice(2)}`; }
};

export const createContentTraceSession = () => eventId().slice(0, 12);

export const readContentTrace = (): ContentTraceEvent[] => {
  try {
    const value = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '[]');
    return Array.isArray(value) ? value.slice(-MAX_EVENTS) as ContentTraceEvent[] : [];
  } catch {
    return [];
  }
};

export const clearContentTrace = () => {
  try { window.localStorage.removeItem(STORAGE_KEY); } catch { /* local trace is optional */ }
};

/**
 * Write a safe, structured client-side event for the content workspace.
 * The same event goes to the browser console, local storage, and the page so
 * a Windows run can be diagnosed from DevTools or the in-page debug panel.
 */
export const traceContentStep = (
  event: string,
  details: Record<string, unknown> = {},
  level: ContentTraceLevel = 'info',
  sessionId?: string,
): ContentTraceEvent => {
  const payload: ContentTraceEvent = {
    id: eventId().slice(0, 12),
    at: new Date().toISOString(),
    level,
    event,
    ...(sessionId ? { sessionId } : {}),
    details: safeDetails(details),
  };
  const prefix = `[CreatorOS][内容工作区] ${event}`;
  const log = level === 'error' ? console.error : level === 'warning' ? console.warn : console.info;
  log(prefix, payload);
  try {
    const next = [...readContentTrace(), payload].slice(-MAX_EVENTS);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch { /* Diagnostics must never block content creation. */ }
  window.dispatchEvent(new CustomEvent<ContentTraceEvent>('creatoros:content-trace', { detail: payload }));
  return payload;
};
