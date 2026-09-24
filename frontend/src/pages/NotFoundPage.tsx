import { Link } from 'react-router';
import { buttonClassName } from '../components/buttonClassName.ts';
import { EmptyState } from '../components/EmptyState.tsx';

export default function NotFoundPage() {
  return (
    <>
      <title>Page not found — RepoPilot</title>
      <EmptyState
        icon="search"
        titleAs="h1"
        title="Page not found"
        action={
          <Link to="/" className={buttonClassName('primary')}>
            Go to the dashboard
          </Link>
        }
      >
        There is nothing at this address.
      </EmptyState>
    </>
  );
}
