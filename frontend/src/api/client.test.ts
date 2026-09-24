import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiRequest, buildUrl } from './client.ts';
import { toUserFacingError } from './errors.ts';
import { createReview, listReviews } from './reviews.ts';

function mockFetch(response: Response | Error) {
  const fetchMock = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>(() =>
    response instanceof Error ? Promise.reject(response) : Promise.resolve(response),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  });

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('buildUrl', () => {
  it('drops empty query values', () => {
    expect(
      buildUrl('/api/reviews', { owner: 'o', repo: '', pull_number: undefined, limit: 20 }),
    ).toBe('/api/reviews?owner=o&limit=20');
  });
});

describe('API functions', () => {
  it('createReview posts the PR and only sends force when requested', async () => {
    const fetchMock = mockFetch(json(200, { id: 'x' }));

    await createReview({ owner: 'octo', repo: 'app', pullNumber: 7 }, { force: true });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/reviews/github?force=true');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(init?.body as string)).toEqual({
      owner: 'octo',
      repo: 'app',
      pull_number: 7,
    });
  });

  it('listReviews maps filters and pagination to query parameters', async () => {
    const fetchMock = mockFetch(json(200, { items: [], total: 0, limit: 20, offset: 40 }));

    await listReviews({ owner: 'octo', pullNumber: 3, limit: 20, offset: 40 });

    expect(fetchMock.mock.calls[0][0]).toBe(
      '/api/reviews?owner=octo&pull_number=3&limit=20&offset=40',
    );
  });
});

describe('error handling', () => {
  it('uses the backend detail message and Retry-After', async () => {
    mockFetch(json(503, { detail: 'Review storage is unavailable.' }, { 'Retry-After': '30' }));

    const error = await apiRequest('/api/reviews').catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 503,
      detail: 'Review storage is unavailable.',
      retryAfterSeconds: 30,
    });
  });

  it('discards non-JSON and markup error bodies', async () => {
    mockFetch(new Response('<html><body>Bad gateway</body></html>', { status: 502 }));

    const error = (await apiRequest('/x').catch((e: unknown) => e)) as ApiError;

    expect(error.detail).toBeNull();
    expect(toUserFacingError(error).message).not.toContain('<');
  });

  it('treats a proxy error without an API detail as an unreachable API', async () => {
    mockFetch(
      new Response('Bad Gateway', { status: 502, headers: { 'Content-Type': 'text/plain' } }),
    );

    const error = await apiRequest('/x').catch((e: unknown) => e);

    expect(toUserFacingError(error).title).toBe('Cannot reach the RepoPilot API');
  });

  it('ignores FastAPI validation arrays', async () => {
    mockFetch(json(422, { detail: [{ loc: ['body', 'owner'], msg: 'bad', input: 'secret' }] }));

    const error = (await apiRequest('/x').catch((e: unknown) => e)) as ApiError;

    expect(error.detail).toBeNull();
    expect(toUserFacingError(error).title).toBe('Invalid request');
  });

  it('reports network failures as status 0', async () => {
    mockFetch(new TypeError('Failed to fetch'));

    const error = (await apiRequest('/x').catch((e: unknown) => e)) as ApiError;

    expect(error.status).toBe(0);
    expect(toUserFacingError(error).title).toBe('Cannot reach the RepoPilot API');
  });

  it.each([
    [404, 'Repository or pull request not found on GitHub.', 'Not found', false],
    [429, 'GitHub API rate limit exceeded.', 'GitHub rate limit reached', true],
    [503, 'AI review is not configured on this server.', 'Service unavailable', true],
    [502, 'The AI provider is unavailable.', 'Upstream service error', true],
    [504, 'The AI provider did not respond in time.', 'Review timed out', true],
  ])('maps %i to a friendly message', (status, detail, title, retryable) => {
    const friendly = toUserFacingError(new ApiError(status, detail));

    expect(friendly).toEqual({ title, message: detail, retryable });
  });

  it('never exposes unknown thrown values', () => {
    expect(toUserFacingError(new Error('stack trace at foo.ts:1')).message).not.toContain('stack');
  });
});
