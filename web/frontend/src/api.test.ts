import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { discoverModels } from './api';

describe('API request cancellation', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('window', {
      setTimeout: globalThis.setTimeout,
      clearTimeout: globalThis.clearTimeout,
    });
    vi.stubGlobal('fetch', vi.fn((_input: RequestInfo | URL, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      const signal = init?.signal;
      const abort = () => reject(new DOMException('Aborted', 'AbortError'));
      if (!signal || signal.aborted) abort();
      else signal.addEventListener('abort', abort, { once: true });
    })));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('applies the internal timeout when discovery also has a caller signal', async () => {
    const caller = new AbortController();
    const pending = discoverModels({ slot: 'custom', baseUrl: 'https://example.test/v1', key: 'key' }, caller.signal);
    const outcome = pending.then(
      () => ({ ok: true, error: null }),
      (error: unknown) => ({ ok: false, error }),
    );

    // Discovery retries transient timeout responses twice. Advance virtual
    // time through all three attempts without waiting in real time.
    await vi.advanceTimersByTimeAsync(25_250);
    await vi.advanceTimersByTimeAsync(25_250);
    await vi.advanceTimersByTimeAsync(25_250);

    const result = await outcome;
    expect(result.ok).toBe(false);
    expect(result.error).toMatchObject({ status: 408 });
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(3);
  });
});
