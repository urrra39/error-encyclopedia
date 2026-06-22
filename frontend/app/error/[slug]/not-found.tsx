import Link from "next/link";
import type { JSX } from "react";

/**
 * Rendered when `getErrorBySlug` returns null and the page calls `notFound()`.
 * A small, friendly dead-end with a path back to search.
 */
export default function ErrorNotFound(): JSX.Element {
  return (
    <section className="mx-auto flex max-w-xl flex-col items-center text-center">
      <span className="mb-4 inline-flex items-center rounded-full bg-rose-50 px-3 py-1 text-xs font-medium text-rose-700 dark:bg-rose-900/30 dark:text-rose-300">
        404 · Not found
      </span>

      <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl dark:text-slate-50">
        Error not found
      </h1>

      <p className="mt-4 text-base text-slate-600 dark:text-slate-300">
        We couldn&apos;t find an entry for that error. It may have been removed,
        or the link might be incorrect.
      </p>

      <Link
        href="/"
        className="mt-8 inline-flex items-center gap-2 rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
      >
        Back to search
      </Link>
    </section>
  );
}
