// <ApiEndpoint service=".." path=".." method=".." /> -- one HTTP endpoint, with its host details
// resolved from the service registry rather than retyped into prose.
//
// Ports in these guides had been written out by hand in cURL blocks, which is how a document
// comes to name a port the compose file no longer binds. The port, the health path and the
// implementing package all come from meshServiceRegistry here, so the only thing the author
// supplies is the route itself.
//
// An unknown service id throws rather than rendering a blank: documentation pages are
// statically generated, so the throw fails `next build` and the typo cannot ship.

import React from "react";
import { meshServicesById } from "@/constants/meshServiceRegistry";

const defaultHttpMethod = "GET";
const localHostOrigin = "http://localhost";

export interface ApiEndpointProps {
  readonly service: string;
  readonly path: string;
  readonly method?: string;
  readonly children?: React.ReactNode;
}

export function ApiEndpoint({
  service,
  path,
  method,
  children,
}: ApiEndpointProps): React.JSX.Element {
  const descriptor = meshServicesById[service];
  if (!descriptor) {
    throw new Error(
      `<ApiEndpoint service="${service}"> names no service in meshServiceRegistry. ` +
        `Known ids: ${Object.keys(meshServicesById).join(", ")}`
    );
  }

  const httpMethod = (method ?? defaultHttpMethod).toUpperCase();

  return (
    <div className="doc-widget my-4 rounded-lg border border-borderSubtle bg-bgSurface p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded bg-accentSubtle px-1.5 py-0.5 font-mono text-[11px] font-semibold uppercase text-accentPrimary">
          {httpMethod}
        </span>
        <code className="font-mono text-body-sm text-textPrimary">{path}</code>
      </div>

      {children ? (
        <div className="mt-2 text-body-sm leading-relaxed text-textSecondary">{children}</div>
      ) : null}

      <dl className="mt-2.5 grid grid-cols-1 gap-x-6 gap-y-1 text-[11px] sm:grid-cols-3">
        <div>
          <dt className="text-textMuted">Service</dt>
          <dd className="text-textSecondary">{descriptor.displayName}</dd>
        </div>
        <div>
          <dt className="text-textMuted">Local URL</dt>
          <dd className="font-mono text-textSecondary">
            {localHostOrigin}:{descriptor.composePort}
            {path}
          </dd>
        </div>
        <div>
          <dt className="text-textMuted">Implemented in</dt>
          <dd className="font-mono text-textSecondary">{descriptor.packagePath}</dd>
        </div>
      </dl>
    </div>
  );
}
