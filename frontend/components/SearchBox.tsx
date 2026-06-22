"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type JSX,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";

import { ApiError, searchErrors } from "@/lib/api";
import type { SearchResultItem } from "@/lib/types";

/** Props accepted by {@link SearchBox}. */
export interface SearchBoxProps {
  /** Placeholder text shown in the empty input. */
  placeholder?: string;
  /** Whether the input should grab focus on mount. */
  autoFocus?: boolean;
}

/** Minimum trimmed query length before a search request is issued. */
const MIN_QUERY_LENGTH = 2;
/** Debounce window applied to keystrokes before searching, in milliseconds. */
const DEBOUNCE_MS = 250;
/** Maximum number of hits requested from the API. */
const RESULT_LIMIT = 8;
/** Delay before closing the dropdown on blur so option clicks register. */
const BLUR_CLOSE_DELAY_MS = 150;

/**
 * Debounce an arbitrary value, returning the latest value only after it has
 * stopped changing for `delayMs`. Implemented with a single timeout that is
 * cleared on every change (no external dependency).
 */
function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState<T>(value);

  useEffect(() => {
    const timeout = setTimeout(() => {
      setDebounced(value);
    }, delayMs);
    return () => {
      clearTimeout(timeout);
    };
  }, [value, delayMs]);

  return debounced;
}

/** The mutually-exclusive states the dropdown can be in. */
type DropdownStatus = "idle" | "loading" | "results" | "empty" | "error";

/** Truncate text to a sensible length for a one-line suggestion summary. */
function truncate(text: string, max = 120): string {
  const trimmed = text.trim();
  if (trimmed.length <= max) {
    return trimmed;
  }
  return `${trimmed.slice(0, max - 1).trimEnd()}…`;
}

/**
 * A debounced, keyboard-navigable search box with a results dropdown.
 *
 * Behaviour:
 *  - Debounces input by {@link DEBOUNCE_MS} and only searches when the trimmed
 *    query is at least {@link MIN_QUERY_LENGTH} characters.
 *  - Cancels stale in-flight requests via an `AbortController` and guards
 *    against out-of-order responses with a monotonically increasing token.
 *  - Surfaces loading, empty, and error states inside the dropdown.
 *  - Implements ARIA combobox semantics with Arrow/Enter/Escape navigation.
 */
export default function SearchBox({
  placeholder = "Search for an error message or code…",
  autoFocus = false,
}: SearchBoxProps): JSX.Element {
  const router = useRouter();

  const [query, setQuery] = useState<string>("");
  const [hits, setHits] = useState<SearchResultItem[]>([]);
  const [status, setStatus] = useState<DropdownStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [activeIndex, setActiveIndex] = useState<number>(-1);
  /** The query string the current `hits`/state reflect (for empty-state copy). */
  const [resultQuery, setResultQuery] = useState<string>("");

  const debouncedQuery = useDebouncedValue(query, DEBOUNCE_MS);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const blurTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** Monotonic token guarding against out-of-order responses. */
  const requestTokenRef = useRef<number>(0);

  const listboxId = useId();
  const optionId = useCallback(
    (index: number): string => `${listboxId}-option-${index}`,
    [listboxId],
  );

  // Run the (debounced) search whenever the debounced query changes.
  useEffect(() => {
    const trimmed = debouncedQuery.trim();

    if (trimmed.length < MIN_QUERY_LENGTH) {
      // Short/empty query: reset to a closed, idle dropdown and issue no request.
      requestTokenRef.current += 1;
      setHits([]);
      setStatus("idle");
      setErrorMessage("");
      setActiveIndex(-1);
      setResultQuery("");
      return;
    }

    const token = ++requestTokenRef.current;
    const controller = new AbortController();

    setStatus("loading");
    setIsOpen(true);
    setActiveIndex(-1);

    searchErrors(trimmed, RESULT_LIMIT, { signal: controller.signal })
      .then((response) => {
        // Discard if a newer request has superseded this one.
        if (token !== requestTokenRef.current) {
          return;
        }
        setHits(response.hits);
        setResultQuery(trimmed);
        setStatus(response.hits.length > 0 ? "results" : "empty");
        setErrorMessage("");
      })
      .catch((error: unknown) => {
        if (token !== requestTokenRef.current) {
          return;
        }
        // An aborted request is expected churn, not a user-facing error.
        if (controller.signal.aborted) {
          return;
        }
        const message =
          error instanceof ApiError
            ? "Search is temporarily unavailable. Please try again."
            : "Something went wrong while searching.";
        setHits([]);
        setResultQuery(trimmed);
        setStatus("error");
        setErrorMessage(message);
      });

    return () => {
      controller.abort();
    };
  }, [debouncedQuery]);

  // Close the dropdown when clicking outside the component.
  useEffect(() => {
    function handlePointerDown(event: MouseEvent): void {
      const node = containerRef.current;
      if (node && event.target instanceof Node && !node.contains(event.target)) {
        setIsOpen(false);
        setActiveIndex(-1);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, []);

  // Clear any pending blur timeout on unmount.
  useEffect(() => {
    return () => {
      if (blurTimeoutRef.current !== null) {
        clearTimeout(blurTimeoutRef.current);
      }
    };
  }, []);

  const hrefForHit = useCallback(
    (hit: SearchResultItem): string => `/error/${encodeURIComponent(hit.slug)}`,
    [],
  );

  const navigateTo = useCallback(
    (hit: SearchResultItem): void => {
      setIsOpen(false);
      setActiveIndex(-1);
      router.push(hrefForHit(hit));
    },
    [router, hrefForHit],
  );

  const clearQuery = useCallback((): void => {
    requestTokenRef.current += 1;
    setQuery("");
    setHits([]);
    setStatus("idle");
    setErrorMessage("");
    setResultQuery("");
    setActiveIndex(-1);
    setIsOpen(false);
    inputRef.current?.focus();
  }, []);

  const handleKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLInputElement>): void => {
      const hasOptions = status === "results" && hits.length > 0;

      switch (event.key) {
        case "ArrowDown": {
          if (!hasOptions) {
            return;
          }
          event.preventDefault();
          setIsOpen(true);
          setActiveIndex((prev) => (prev + 1) % hits.length);
          break;
        }
        case "ArrowUp": {
          if (!hasOptions) {
            return;
          }
          event.preventDefault();
          setIsOpen(true);
          setActiveIndex((prev) => (prev <= 0 ? hits.length - 1 : prev - 1));
          break;
        }
        case "Enter": {
          if (hasOptions && activeIndex >= 0 && activeIndex < hits.length) {
            event.preventDefault();
            navigateTo(hits[activeIndex]);
          }
          break;
        }
        case "Escape": {
          if (isOpen) {
            event.preventDefault();
            setIsOpen(false);
            setActiveIndex(-1);
          }
          break;
        }
        default:
          break;
      }
    },
    [status, hits, activeIndex, isOpen, navigateTo],
  );

  const handleFocus = useCallback((): void => {
    if (blurTimeoutRef.current !== null) {
      clearTimeout(blurTimeoutRef.current);
      blurTimeoutRef.current = null;
    }
    if (query.trim().length >= MIN_QUERY_LENGTH) {
      setIsOpen(true);
    }
  }, [query]);

  const handleBlur = useCallback((): void => {
    // Delay closing so a click on an option is registered before unmount.
    blurTimeoutRef.current = setTimeout(() => {
      setIsOpen(false);
      setActiveIndex(-1);
    }, BLUR_CLOSE_DELAY_MS);
  }, []);

  const activeOptionId =
    isOpen && status === "results" && activeIndex >= 0
      ? optionId(activeIndex)
      : undefined;

  const showDropdown = isOpen && status !== "idle";

  return (
    <div ref={containerRef} className="relative w-full">
      <div
        className="flex items-center gap-3 rounded-xl border border-slate-300 bg-white px-4 py-3 shadow-sm transition-shadow focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-500/40 dark:border-slate-700 dark:bg-slate-900"
      >
        <svg
          className="h-5 w-5 shrink-0 text-slate-400"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden
        >
          <path
            fillRule="evenodd"
            d="M9 3.5a5.5 5.5 0 1 0 3.4 9.82l3.64 3.64a.75.75 0 1 0 1.06-1.06l-3.64-3.64A5.5 5.5 0 0 0 9 3.5ZM5 9a4 4 0 1 1 8 0 4 4 0 0 1-8 0Z"
            clipRule="evenodd"
          />
        </svg>

        <input
          ref={inputRef}
          type="text"
          // eslint-disable-next-line jsx-a11y/no-autofocus -- opt-in via prop for the hero search.
          autoFocus={autoFocus}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={handleFocus}
          onBlur={handleBlur}
          placeholder={placeholder}
          autoComplete="off"
          spellCheck={false}
          className="w-full bg-transparent text-base text-slate-900 placeholder:text-slate-400 focus:outline-none dark:text-slate-100"
          role="combobox"
          aria-expanded={showDropdown}
          aria-controls={listboxId}
          aria-autocomplete="list"
          aria-activedescendant={activeOptionId}
          aria-label="Search the error encyclopedia"
        />

        {status === "loading" ? (
          <Spinner className="h-4 w-4 shrink-0 text-brand-500" />
        ) : null}

        {query.length > 0 ? (
          <button
            type="button"
            onClick={clearQuery}
            aria-label="Clear search"
            className="shrink-0 rounded-md p-1 text-slate-400 transition-colors hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 dark:hover:text-slate-200"
          >
            <svg
              className="h-4 w-4"
              viewBox="0 0 20 20"
              fill="currentColor"
              aria-hidden
            >
              <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
            </svg>
          </button>
        ) : null}
      </div>

      {showDropdown ? (
        <div
          className="absolute z-20 mt-2 w-full overflow-hidden rounded-xl border border-slate-200 bg-white text-left shadow-lg dark:border-slate-700 dark:bg-slate-900"
        >
          {status === "loading" ? (
            <ul className="divide-y divide-slate-100 dark:divide-slate-800" aria-hidden>
              {[0, 1, 2].map((key) => (
                <li key={key} className="flex flex-col gap-2 px-4 py-3">
                  <span className="h-4 w-1/3 animate-pulse rounded bg-slate-200 dark:bg-slate-700" />
                  <span className="h-3 w-3/4 animate-pulse rounded bg-slate-100 dark:bg-slate-800" />
                </li>
              ))}
            </ul>
          ) : null}

          {status === "error" ? (
            <div
              role="alert"
              className="flex items-start gap-2 px-4 py-4 text-sm text-rose-600 dark:text-rose-400"
            >
              <svg
                className="mt-0.5 h-4 w-4 shrink-0"
                viewBox="0 0 20 20"
                fill="currentColor"
                aria-hidden
              >
                <path
                  fillRule="evenodd"
                  d="M10 1.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17ZM10 5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 9.5a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
                  clipRule="evenodd"
                />
              </svg>
              <span>{errorMessage}</span>
            </div>
          ) : null}

          {status === "empty" ? (
            <div className="px-4 py-4 text-sm text-slate-500 dark:text-slate-400">
              No matching errors found for{" "}
              <span className="font-medium text-slate-700 dark:text-slate-200">
                &ldquo;{resultQuery}&rdquo;
              </span>
              .
            </div>
          ) : null}

          {status === "results" ? (
            <ul
              id={listboxId}
              role="listbox"
              aria-label="Search results"
              className="max-h-96 divide-y divide-slate-100 overflow-y-auto dark:divide-slate-800"
            >
              {hits.map((hit, index) => {
                const isActive = index === activeIndex;
                return (
                  <li key={hit.slug} role="presentation">
                    <Link
                      id={optionId(index)}
                      role="option"
                      aria-selected={isActive}
                      href={hrefForHit(hit)}
                      onMouseEnter={() => setActiveIndex(index)}
                      onClick={() => {
                        setIsOpen(false);
                        setActiveIndex(-1);
                      }}
                      className={`flex flex-col gap-1 px-4 py-3 transition-colors focus:outline-none ${
                        isActive
                          ? "bg-brand-50 dark:bg-brand-700/20"
                          : "hover:bg-slate-50 dark:hover:bg-slate-800/60"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
                          {hit.title}
                        </span>
                        <span className="flex shrink-0 items-center gap-1.5">
                          <Badge
                            label={`${hit.fix_count} ${
                              hit.fix_count === 1 ? "fix" : "fixes"
                            }`}
                            tone="green"
                          />
                          <Badge
                            label={`${hit.root_cause_count} ${
                              hit.root_cause_count === 1 ? "cause" : "causes"
                            }`}
                            tone="indigo"
                          />
                        </span>
                      </div>
                      <span className="line-clamp-2 text-xs text-slate-500 dark:text-slate-400">
                        {truncate(hit.plain_english_explanation)}
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/** A small inline animated spinner. */
function Spinner({ className }: { className?: string }): JSX.Element {
  return (
    <svg
      className={`animate-spin ${className ?? ""}`}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-90"
        fill="currentColor"
        d="M4 12a8 8 0 0 1 8-8v4a4 4 0 0 0-4 4H4Z"
      />
    </svg>
  );
}

/** A tiny rounded count badge in one of two tones. */
function Badge({
  label,
  tone,
}: {
  label: string;
  tone: "green" | "indigo";
}): JSX.Element {
  const toneClasses =
    tone === "green"
      ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300"
      : "bg-brand-50 text-brand-700 dark:bg-brand-700/20 dark:text-brand-100";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ${toneClasses}`}
    >
      {label}
    </span>
  );
}
