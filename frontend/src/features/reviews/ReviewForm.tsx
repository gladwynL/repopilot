import { useState, type ChangeEvent, type FormEvent } from 'react';
import { Button } from '../../components/Button.tsx';
import { TextField } from '../../components/Field.tsx';
import type { PullRequestRef } from '../../types/api.ts';
import {
  parsePullRequestUrl,
  validatePullRequestForm,
  type PullRequestFormErrors,
  type PullRequestFormValues,
} from './pullRequestInput.ts';
import styles from './ReviewForm.module.css';

interface ReviewFormProps {
  onSubmit: (pr: PullRequestRef) => void;
  pending: boolean;
}

const EMPTY: PullRequestFormValues = { owner: '', repo: '', pullNumber: '' };

export function ReviewForm({ onSubmit, pending }: ReviewFormProps) {
  const [url, setUrl] = useState('');
  const [urlError, setUrlError] = useState<string>();
  const [values, setValues] = useState(EMPTY);
  const [errors, setErrors] = useState<PullRequestFormErrors>({});

  function applyUrl(raw: string) {
    if (!raw.trim()) {
      setUrlError(undefined);
      return;
    }
    const parsed = parsePullRequestUrl(raw);
    if (!parsed) {
      setUrlError('Expected a pull request URL like https://github.com/owner/repo/pull/123.');
      return;
    }
    setUrlError(undefined);
    setErrors({});
    setValues({ owner: parsed.owner, repo: parsed.repo, pullNumber: String(parsed.pullNumber) });
  }

  function updateField(field: keyof PullRequestFormValues) {
    return (event: ChangeEvent<HTMLInputElement>) => {
      setValues((current) => ({ ...current, [field]: event.target.value }));
      setErrors((current) => ({ ...current, [field]: undefined }));
    };
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = validatePullRequestForm(values);
    if (!result.ok) {
      setErrors(result.errors);
      return;
    }
    onSubmit(result.value);
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate aria-label="Start a review">
      <fieldset className={styles.fieldset} disabled={pending}>
        <TextField
          label="Pull request URL"
          name="url"
          type="url"
          inputMode="url"
          mono
          placeholder="https://github.com/owner/repo/pull/123"
          hint="Paste a GitHub PR link to fill in the fields below."
          error={urlError}
          value={url}
          onChange={(event) => {
            setUrl(event.target.value);
            applyUrl(event.target.value);
          }}
          autoComplete="off"
          spellCheck={false}
        />

        <div className={styles.divider} aria-hidden="true">
          <span>or enter the details</span>
        </div>

        <div className={styles.row}>
          <TextField
            label="Owner"
            name="owner"
            mono
            placeholder="e.g. octocat"
            value={values.owner}
            error={errors.owner}
            onChange={updateField('owner')}
            autoComplete="off"
            spellCheck={false}
          />
          <span className={styles.slash} aria-hidden="true">
            /
          </span>
          <TextField
            label="Repository"
            name="repo"
            mono
            placeholder="e.g. Hello-World"
            value={values.repo}
            error={errors.repo}
            onChange={updateField('repo')}
            autoComplete="off"
            spellCheck={false}
          />
          <TextField
            label="PR number"
            name="pullNumber"
            mono
            inputMode="numeric"
            placeholder="e.g. 42"
            value={values.pullNumber}
            error={errors.pullNumber}
            onChange={updateField('pullNumber')}
            autoComplete="off"
            className={styles.number}
          />
        </div>
      </fieldset>

      <div className={styles.footer}>
        <p className={styles.note}>
          Stored reviews of the same commit are reused; otherwise this runs a new AI review.
        </p>
        <Button type="submit" variant="primary" loading={pending}>
          {pending ? 'Reviewing…' : 'Review pull request'}
        </Button>
      </div>
    </form>
  );
}
