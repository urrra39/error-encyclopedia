import type { JSX } from "react";

/**
 * Home page (server component). Presents the product hero and a
 * non-interactive search box placeholder. The interactive search experience
 * lands in Phase 4.
 */
export default function HomePage(): JSX.Element {
  return (
    <section className="flex flex-col items-center text-center">
      <span className="mb-4 inline-flex items-center rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700 dark:bg-brand-700/20 dark:text-brand-100">
        The developer&apos;s error reference
      </span>

      <h1 className="max-w-3xl text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl dark:text-slate-50">
        Error Encyclopedia
      </h1>

      <p className="mt-4 max-w-2xl text-lg text-slate-600 dark:text-slate-300">
        Paste an error, understand it in plain English, and apply a verified
        before/after fix — without the rabbit hole of stale forum threads.
      </p>

      <div className="mt-10 w-full max-w-2xl">
        <div
          className="flex items-center gap-3 rounded-xl border border-slate-300 bg-white px-4 py-3 text-left shadow-sm dark:border-slate-700 dark:bg-slate-900"
          aria-hidden
        >
          <svg
            className="h-5 w-5 shrink-0 text-slate-400"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              fillRule="evenodd"
              d="M9 3.5a5.5 5.5 0 1 0 3.4 9.82l3.64 3.64a.75.75 0 1 0 1.06-1.06l-3.64-3.64A5.5 5.5 0 0 0 9 3.5ZM5 9a4 4 0 1 1 8 0 4 4 0 0 1-8 0Z"
              clipRule="evenodd"
            />
          </svg>
          <span className="text-slate-400">
            Search for an error message or code…
          </span>
        </div>
        <p className="mt-3 text-sm text-slate-400 dark:text-slate-500">
          Interactive search is coming soon.
        </p>
      </div>

      <dl className="mt-14 grid w-full max-w-3xl grid-cols-1 gap-6 sm:grid-cols-3">
        <Feature
          title="Plain English"
          body="Every error explained the way a senior engineer would explain it to you."
        />
        <Feature
          title="Root causes"
          body="The actual reasons an error fires — not just the symptom on your screen."
        />
        <Feature
          title="Verified fixes"
          body="Before/after code you can trust, with an explanation of why it works."
        />
      </dl>
    </section>
  );
}

function Feature({
  title,
  body,
}: {
  title: string;
  body: string;
}): JSX.Element {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 text-left dark:border-slate-800 dark:bg-slate-900">
      <dt className="text-base font-semibold text-slate-900 dark:text-slate-100">
        {title}
      </dt>
      <dd className="mt-1 text-sm text-slate-600 dark:text-slate-400">
        {body}
      </dd>
    </div>
  );
}
