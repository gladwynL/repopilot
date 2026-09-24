import { describe, expect, it } from 'vitest';
import { parsePullRequestUrl, validatePullRequestForm } from './pullRequestInput.ts';

describe('parsePullRequestUrl', () => {
  it.each([
    'https://github.com/octo-org/widgets/pull/42',
    'github.com/octo-org/widgets/pull/42',
    'https://www.github.com/octo-org/widgets/pull/42/files',
    'https://github.com/octo-org/widgets/pull/42?diff=split#discussion',
    '  https://github.com/octo-org/widgets/pull/42  ',
  ])('parses %s', (url) => {
    expect(parsePullRequestUrl(url)).toEqual({
      owner: 'octo-org',
      repo: 'widgets',
      pullNumber: 42,
    });
  });

  it.each([
    'https://gitlab.com/octo-org/widgets/pull/42',
    'https://github.com/octo-org/widgets/issues/42',
    'https://github.com/octo-org/widgets/pull/abc',
    'https://github.com/octo-org/widgets/pull/0',
    'https://github.com/-bad-/widgets/pull/1',
    'not a url',
  ])('rejects %s', (url) => {
    expect(parsePullRequestUrl(url)).toBeNull();
  });
});

describe('validatePullRequestForm', () => {
  it('trims and converts valid input', () => {
    expect(
      validatePullRequestForm({ owner: ' octo ', repo: 'app.js ', pullNumber: ' 7 ' }),
    ).toEqual({
      ok: true,
      value: { owner: 'octo', repo: 'app.js', pullNumber: 7 },
    });
  });

  it('reports every blank field', () => {
    const result = validatePullRequestForm({ owner: '', repo: ' ', pullNumber: '' });

    expect(result.ok).toBe(false);
    if (!result.ok) expect(Object.values(result.errors).filter(Boolean)).toHaveLength(3);
  });

  it.each(['0', '-1', '1.5', '4e2', 'abc'])('rejects PR number %s', (pullNumber) => {
    const result = validatePullRequestForm({ owner: 'o', repo: 'r', pullNumber });

    expect(result.ok).toBe(false);
  });

  it('rejects owners and repos the backend would reject', () => {
    const result = validatePullRequestForm({ owner: 'octo_org', repo: '..', pullNumber: '1' });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors.owner).toBeDefined();
      expect(result.errors.repo).toBeDefined();
    }
  });
});
