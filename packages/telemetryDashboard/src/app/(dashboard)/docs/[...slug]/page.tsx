// One route for every guide. Replaces six near-identical page.tsx files that differed only by
// a slug constant, each of which had to be created by hand alongside two loader maps.
//
// A server component: MDXRemote from next-mdx-remote/rsc compiles on the server, so no MDX
// runtime reaches the client bundle. generateStaticParams prerenders each guide at build time.

import React from "react";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { MDXRemote } from "next-mdx-remote/rsc";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeSlug from "rehype-slug";
import rehypeAutolinkHeadings from "rehype-autolink-headings";
import rehypeKatex from "rehype-katex";
// The tax and telemetry specs carry real LaTeX -- the GST equal-half division, the floor
// operations that keep paise arithmetic exact, the settlement metric formulas. The previous
// markdown viewer printed those as raw `$$\text{...}$$` source. KaTeX renders them, and it also
// keeps MDX from reading `{` as the start of a JS expression and failing to compile.
import "katex/dist/katex.min.css";
import { DocEditLink } from "@/components/docs/docEditLink";
import { DocPagination } from "@/components/docs/docPagination";
import { DocSearch } from "@/components/docs/docSearch";
import { DocTableOfContents } from "@/components/docs/docTableOfContents";
import { mdxComponents } from "@/components/docs/mdxComponents";
import { loadAllDocPages, loadDocPage, toNavEntry } from "@/lib/docsLoader";
import type { DocNavEntry } from "@/types/docsTypes";

interface DocsRouteParams {
  readonly slug: string[];
}

interface DocsPageProps {
  readonly params: Promise<DocsRouteParams>;
}

const mdxOptions = {
  mdxOptions: {
    remarkPlugins: [remarkGfm, remarkMath],
    // rehypeSlug must run before autolink: the anchor plugin links to the ids slug creates.
    // These ids are the same ones docsLoader precomputes for the table of contents.
    rehypePlugins: [
      rehypeSlug,
      // "wrap" turns the heading text itself into the anchor. No className here: the plugin
      // does not apply `properties` in wrap mode, so it would be config that silently does
      // nothing -- the anchor is styled by the `.markdown-content h2 > a` rule instead.
      [rehypeAutolinkHeadings, { behavior: "wrap" }],
      // strict:false so one malformed formula renders as a warning rather than failing the
      // whole page build.
      [rehypeKatex, { strict: false }],
    ] as never,
  },
};

export function generateStaticParams(): DocsRouteParams[] {
  return loadAllDocPages().map((page) => ({ slug: page.slugSegments as string[] }));
}

export async function generateMetadata({ params }: DocsPageProps): Promise<Metadata> {
  const { slug } = await params;
  const page = loadDocPage(slug);
  if (!page) {
    return { title: "Documentation" };
  }
  return { title: page.frontmatter.title, description: page.frontmatter.description };
}

function findNeighbours(slug: string): {
  previous: DocNavEntry | null;
  next: DocNavEntry | null;
} {
  const pages = loadAllDocPages();
  const index = pages.findIndex((page) => page.slug === slug);
  return {
    previous: index > 0 ? toNavEntry(pages[index - 1]) : null,
    next: index >= 0 && index < pages.length - 1 ? toNavEntry(pages[index + 1]) : null,
  };
}

export default async function DocsPage({ params }: DocsPageProps): Promise<React.JSX.Element> {
  const { slug } = await params;
  const page = loadDocPage(slug);

  // A missing guide is a real 404 now. The old loader returned a body that said "Page Not
  // Found" with HTTP 200, which is indistinguishable from a real page to anything but a reader.
  if (!page) {
    notFound();
  }

  const { previous, next } = findNeighbours(page.slug);

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 pb-12 lg:flex-row">
      <article className="min-w-0 flex-1">
        <header className="mb-6 border-b border-borderSubtle pb-4">
          <p className="text-[11px] uppercase tracking-wide text-textMuted">
            {page.frontmatter.audience}
          </p>
          <h1 className="mt-1 text-headline-sm text-textPrimary">{page.frontmatter.title}</h1>
          <p className="mt-1.5 text-body-sm leading-relaxed text-textSecondary">
            {page.frontmatter.description}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
            <p className="text-[11px] text-textMuted">
              Source: <code className="font-mono">{page.sourcePath}</code>
            </p>
            <DocEditLink sourcePath={page.sourcePath} />
          </div>
        </header>

        <div className="markdown-content">
          <MDXRemote source={page.body} components={mdxComponents} options={mdxOptions} />
        </div>

        <DocPagination previous={previous} next={next} />
      </article>

      <aside className="order-first w-full shrink-0 lg:order-last lg:w-56">
        <div className="sticky top-4">
          <DocSearch />
          <DocTableOfContents headings={page.headings} />
        </div>
      </aside>
    </div>
  );
}
