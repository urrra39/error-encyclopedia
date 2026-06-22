import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache } from "react";
import type { JSX } from "react";

import SearchBox from "@/components/SearchBox";
import { getErrorBySlug } from "@/lib/api";
import type {
  ErrorDetail,
  RootCauseRead,
  VerifiedFixRead,
} from "@/lib/types";

/** Params shape for the dynamic `/error/[slug]` route (Next 14.2). */
interface ErrorPageProps {
  params: { slug: string };
}

/**
 * Request-cached fetch so that `generateMetadata` and the page body share a
 * single network call per render. React's `cache` dedupes by argument.
 */
const loadError = cache(
  async (slug: string): Promise<ErrorDetail | null> => getErrorBySlug(slug),
);

/** Truncate plain text to a meta-description-friendly length. */
function truncateDescription(text: string, max = 155): string {
  const collapsed = text.replace(/\s+/g, " ").trim();
  if (collapsed.length <= max) {
    return collapsed;
  }
  return `${collapsed.slice(0, max - 1).trimEnd()}…`;
}

/** Format an ISO datetime string as a human-readable date (UTC, stable SSR). */
function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    timeZone: "UTC",
  });
}

export async function generateMetadata({
  params,
}: ErrorPageProps): Promise<Metadata> {
  const error = await loadError(params.slug);

  if (!error) {
    return {
      title: "Error not found",
      description: "The requested error could not be found in the encyclopedia.",
    };
  }

  const title = `${error.title} — Error Encyclopedia`;
  const description = truncateDescription(error.plain_english_explanation);

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      type: "article",
      url: `/error/${encodeURIComponent(error.slug)}`,
    },
  };
}

export default async function Page({
  params,
}: ErrorPageProps): Promise<JSX.Element> {
  const error = await loadError(params.slug);

  if (!error) {
    notFound();
  }

  return (
    <article className="mx-auto w-full max-w-3xl">
      <nav className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:text-brand-700 dark:text-brand-500 dark:hover:text-brand-100"
        >
          <svg
            className="h-4 w-4"
            viewBox="0 0 20 20"
            fill="currentColor"
            aria-hidden
          >
            <path
              fillRule="evenodd"
              d="M12.78 4.22a.75.75 0 0 1 0 1.06L8.06 10l4.72 4.72a.75.75 0 1 1-1.06 1.06l-5.25-5.25a.75.75 0 0 1 0-1.06l5.25-5.25a.75.75 0 0 1 1.06 0Z"
              clipRule="evenodd"
            />
          </svg>
          Back to home
        </Link>
      </nav>

      <div className="mb-8">
        <SearchBox placeholder="Search for another error…" />
      </div>

      <header className="border-b border-slate-200 pb-6 dark:border-slate-800">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl dark:text-slate-50">
          {error.title}
        </h1>
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-500 dark:text-slate-400">
          <code className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">
            {error.slug}
          </code>
          <span aria-hidden>·</span>
          <span>
            Documented{" "}
            <time dateTime={error.created_at}>
              {formatDate(error.created_at)}
            </time>
          </span>
        </div>
      </header>

      <Section title="Plain-English Explanation">
        <p className="text-base leading-relaxed text-slate-700 dark:text-slate-300">
          {error.plain_english_explanation}
        </p>
      </Section>

      <Section title="Common Root Causes">
        {error.root_causes.length > 0 ? (
          <ul className="list-disc space-y-2 pl-5 text-base leading-relaxed text-slate-700 marker:text-brand-500 dark:text-slate-300">
            {error.root_causes.map((cause: RootCauseRead) => (
              <li key={cause.id}>{cause.description}</li>
            ))}
          </ul>
        ) : (
          <EmptyNote>No root causes documented yet.</EmptyNote>
        )}
      </Section>

      <Section title="Verified Fixes">
        {error.verified_fixes.length > 0 ? (
          <div className="space-y-8">
            {error.verified_fixes.map((fix: VerifiedFixRead) => (
              <FixCard key={fix.id} fix={fix} />
            ))}
          </div>
        ) : (
          <EmptyNote>No verified fixes documented yet.</EmptyNote>
        )}
      </Section>

      {error.related.length > 0 ? (
        <Section title="Related Errors">
          <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {error.related.map((related) => (
              <li key={related.slug}>
                <Link
                  href={`/error/${encodeURIComponent(related.slug)}`}
                  className="flex h-full flex-col gap-1 rounded-lg border border-slate-200 bg-white p-4 transition-colors hover:border-brand-400 hover:bg-brand-50/40 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-brand-500 dark:hover:bg-brand-700/10"
                >
                  <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                    {related.title}
                  </span>
                  <span className="line-clamp-2 text-xs text-slate-500 dark:text-slate-400">
                    {truncateDescription(related.plain_english_explanation, 120)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}
    </article>
  );
}

/** A titled content section with consistent vertical rhythm. */
function Section({
  title,
  children,
}: {
  title: string;
  children: JSX.Element | JSX.Element[];
}): JSX.Element {
  return (
    <section className="mt-8">
      <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
        {title}
      </h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

/** A muted note used for empty-state messaging. */
function EmptyNote({ children }: { children: string }): JSX.Element {
  return (
    <p className="rounded-lg border border-dashed border-slate-300 px-4 py-3 text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
      {children}
    </p>
  );
}

/** A single verified-fix card: explanation plus before/after code blocks. */
function FixCard({ fix }: { fix: VerifiedFixRead }): JSX.Element {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
      <p className="text-base leading-relaxed text-slate-700 dark:text-slate-300">
        {fix.explanation}
      </p>
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <CodeBlock
          label="Before"
          variant="before"
          code={fix.before_code_snippet}
        />
        <CodeBlock
          label="After"
          variant="after"
          code={fix.after_code_snippet}
        />
      </div>
    </div>
  );
}

/** A labeled, scrollable, whitespace-preserving code block. */
function CodeBlock({
  label,
  variant,
  code,
}: {
  label: string;
  variant: "before" | "after";
  code: string;
}): JSX.Element {
  const isBefore = variant === "before";
  const containerClasses = isBefore
    ? "border-rose-300 dark:border-rose-800/70"
    : "border-emerald-300 dark:border-emerald-800/70";
  const headerClasses = isBefore
    ? "bg-rose-50 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300"
    : "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300";

  return (
    <figure
      className={`overflow-hidden rounded-lg border ${containerClasses}`}
    >
      <figcaption
        className={`flex items-center gap-2 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide ${headerClasses}`}
      >
        <span
          aria-hidden
          className={`inline-block h-2 w-2 rounded-full ${
            isBefore ? "bg-rose-500" : "bg-emerald-500"
          }`}
        />
        {label}
      </figcaption>
      <pre className="overflow-x-auto bg-slate-950 p-4 text-sm leading-relaxed text-slate-100">
        <code className="whitespace-pre font-mono">{code}</code>
      </pre>
    </figure>
  );
}
