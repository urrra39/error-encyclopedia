import type { JSX } from "react";

import SearchBox from "@/components/SearchBox";

/**
 * Home page (server component). Presents the product hero with the embedded
 * interactive {@link SearchBox} client component and a feature trio below.
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

      <p className="mt-4 max-w-2xl text-base text-slate-600 sm:text-lg dark:text-slate-300">
        Stop guessing. Search any error message, understand what it actually
        means in plain English, and apply a verified before/after fix — no more
        wading through stale forum threads.
      </p>

      <div className="mt-10 w-full max-w-2xl">
        <SearchBox autoFocus placeholder="Search for an error message or code…" />
        <p className="mt-3 text-sm text-slate-400 dark:text-slate-500">
          Try a snippet of the error text — results appear as you type.
        </p>
      </div>

      <dl className="mt-14 grid w-full max-w-3xl grid-cols-1 gap-6 sm:grid-cols-3">
        <Feature
          title="Plain-English explanations"
          body="Every error explained the way a senior engineer would explain it to you — no jargon, no hand-waving."
        />
        <Feature
          title="Verified fixes"
          body="Real before/after code you can trust, paired with a clear explanation of why the change works."
        />
        <Feature
          title="Related errors"
          body="Discover the errors that tend to travel together, so you can fix the root problem, not just the symptom."
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
