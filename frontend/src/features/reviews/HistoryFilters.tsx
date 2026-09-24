import { useState, type FormEvent } from 'react';
import { Button } from '../../components/Button.tsx';
import { TextField } from '../../components/Field.tsx';
import {
  validateHistoryFilters,
  type HistoryFilterErrors,
  type HistoryFilterValues,
} from './pullRequestInput.ts';
import styles from './HistoryFilters.module.css';

interface HistoryFiltersProps {
  initial: HistoryFilterValues;
  onApply: (filters: HistoryFilterValues) => void;
  onClear: () => void;
}

export function HistoryFilters({ initial, onApply, onClear }: HistoryFiltersProps) {
  const [draft, setDraft] = useState(initial);
  const [errors, setErrors] = useState<HistoryFilterErrors>({});
  const active = Boolean(initial.owner || initial.repo || initial.pr);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = { owner: draft.owner.trim(), repo: draft.repo.trim(), pr: draft.pr.trim() };
    const invalid = validateHistoryFilters(trimmed);
    setErrors(invalid ?? {});
    if (!invalid) onApply(trimmed);
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit} aria-label="Filter reviews" noValidate>
      <TextField
        label="Owner"
        mono
        placeholder="any"
        value={draft.owner}
        error={errors.owner}
        onChange={(e) => setDraft({ ...draft, owner: e.target.value })}
      />
      <TextField
        label="Repository"
        mono
        placeholder="any"
        value={draft.repo}
        error={errors.repo}
        onChange={(e) => setDraft({ ...draft, repo: e.target.value })}
      />
      <TextField
        label="PR number"
        mono
        inputMode="numeric"
        placeholder="any"
        value={draft.pr}
        error={errors.pr}
        onChange={(e) => setDraft({ ...draft, pr: e.target.value })}
      />
      <div className={styles.actions}>
        <Button type="submit">Apply filters</Button>
        {active && (
          <Button variant="ghost" onClick={onClear}>
            Clear
          </Button>
        )}
      </div>
    </form>
  );
}
