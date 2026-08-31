// The shape of the generated reference artifacts under generated/.
//
// One shape covers both SDKs on purpose. The drift checker asks the same questions of a
// TypeScript class and a Python class -- does this name exist, does this member exist, does this
// keyword argument exist -- so a single surface type lets one checker serve both languages
// instead of two that fall out of step.

export type ExportedSymbolKind =
  | "class"
  | "interface"
  | "function"
  | "variable"
  | "type"
  | "enum";

export interface SymbolMember {
  readonly name: string;
  // Rendered by the language's own tooling: the TypeScript checker for TS, inspect.signature for
  // Python. Displayed in error messages so a failure names the real signature, not just "unknown".
  readonly signature: string;
}

export interface ExportedSymbol {
  readonly name: string;
  readonly kind: ExportedSymbolKind;
  readonly signature: string;
  // Methods of a class, properties of an interface, fields of a dataclass. The checker resolves
  // `client.someMethod` and `SomeConfig({ someKey })` against this list.
  readonly members: readonly SymbolMember[];
  // Names accepted by the constructor: TypeScript config-object properties, Python keyword
  // arguments. Empty for anything that is not constructible.
  readonly constructorParameters: readonly string[];
}

export interface PackageSurface {
  // The name a reader would install and import -- the string the guides must match.
  readonly packageName: string;
  readonly entryPoint: string;
  readonly exports: readonly ExportedSymbol[];
}

export interface HttpOperation {
  readonly method: string;
  readonly path: string;
}

export interface HttpServiceSurface {
  readonly serviceId: string;
  readonly title: string;
  readonly operations: readonly HttpOperation[];
}

export interface HttpApiReference {
  readonly services: readonly HttpServiceSurface[];
  // Event type strings the Python side can emit, so the dashboard union can be checked against
  // them rather than assumed to agree.
  readonly telemetryEventTypes: readonly string[];
}

// Named for the schema pair (InventoryLock -> InventoryLockRequest / InventoryLockResponse)
// rather than for the JSON-RPC tool, because the schema module is where these come from and
// inventing a mapping to the wire tool names would be a third source of truth to keep in step.
export interface McpToolSchema {
  readonly schemaName: string;
  readonly requestFields: readonly string[];
  readonly responseFields: readonly string[];
}

export interface McpToolReference {
  readonly entryPoint: string;
  readonly schemas: readonly McpToolSchema[];
}
