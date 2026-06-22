import type { Metadata } from "next";
import type { ReactNode } from "react";

import "@/app/globals.css";

const SITE_NAME = "Error Encyclopedia";
const SITE_DESCRIPTION =
  "A searchable reference of programming errors with plain-English explanations, root causes, and verified before/after fixes.";

export const metadata: Metadata = {
  metadataBase: new URL("https://error-encyclopedia.dev"),
  title: {
    default: SITE_NAME,
    template: `%s · ${SITE_NAME}`,
  },
  description: SITE_DESCRIPTION,
  applicationName: SITE_NAME,
  openGraph: {
    type: "website",
    siteName: SITE_NAME,
    title: SITE_NAME,
    description: SITE_DESCRIPTION,
    url: "/",
  },
};

export default function RootLayout({
  children,
}: {
  children: ReactNode;
}): JSX.Element {
  return (
    <html lang="en">
      <body className="flex min-h-screen flex-col">
        <header className="border-b border-slate-200 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-900/80">
          <div className="mx-auto flex max-w-content items-center justify-between px-6 py-4">
            <a
              href="/"
              className="flex items-center gap-2 text-lg font-semibold text-slate-900 hover:text-brand-600 dark:text-slate-100 dark:hover:text-brand-500"
            >
              <span aria-hidden className="text-brand-600 dark:text-brand-500">
                {"</>"}
              </span>
              {SITE_NAME}
            </a>
            <nav className="text-sm text-slate-500 dark:text-slate-400">
              <span>Search · Diagnose · Fix</span>
            </nav>
          </div>
        </header>

        <main className="mx-auto w-full max-w-content flex-1 px-6 py-12">
          {children}
        </main>

        <footer className="border-t border-slate-200 bg-white/60 dark:border-slate-800 dark:bg-slate-900/60">
          <div className="mx-auto max-w-content px-6 py-6 text-sm text-slate-500 dark:text-slate-400">
            {`© ${new Date().getFullYear()} ${SITE_NAME}. Built for developers who would rather fix than guess.`}
          </div>
        </footer>
      </body>
    </html>
  );
}
