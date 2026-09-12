import { AlertTriangle } from "lucide-react";
import { Link, useRouteError } from "react-router-dom";

export function RouteErrorPage() {
  const error = useRouteError();

  return (
    <main className="centered-state">
      <AlertTriangle size={32} aria-hidden="true" />
      <h1>We could not open this page</h1>
      <p>The prototype is safe. Try returning to the CivicLens home page.</p>
      {import.meta.env.DEV && error instanceof Error ? (
        <pre className="developer-error">{error.message}</pre>
      ) : null}
      <Link className="button button-primary" to="/">
        Return home
      </Link>
    </main>
  );
}

