import { toUserFacingError } from '../api/errors.ts';
import { Alert } from './Alert.tsx';
import { Button } from './Button.tsx';
import { Icon } from './Icon.tsx';

interface ErrorPanelProps {
  error: unknown;
  onRetry?: () => void;
  retryLabel?: string;
}

/** Renders any API/unknown error as a friendly alert, with a retry button when it may help. */
export function ErrorPanel({ error, onRetry, retryLabel = 'Try again' }: ErrorPanelProps) {
  const { title, message, retryable } = toUserFacingError(error);
  return (
    <Alert
      tone="danger"
      title={title}
      actions={
        onRetry &&
        retryable && (
          <Button size="sm" onClick={onRetry} icon={<Icon name="refresh" size={14} />}>
            {retryLabel}
          </Button>
        )
      }
    >
      {message}
    </Alert>
  );
}
