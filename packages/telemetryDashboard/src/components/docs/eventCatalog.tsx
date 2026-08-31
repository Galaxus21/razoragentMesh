// <EventCatalog /> -- every telemetry event type the mesh can emit, derived from source.
//
// The prose around this table used to enumerate the events by hand and open with "The 12
// Canonical Event Schema Specifications". That count is a claim the document cannot keep: add a
// thirteenth event type and the sentence is simply wrong, with nothing to catch it.
//
// The rows below come from defaultEventStyleMap, which TypeScript types as
// Record<TelemetryEventType, EventMetaStyle> -- a total map. A new member of the union will not
// compile until that map gains a matching entry, so this table cannot fall behind the union.
// The emitting layer comes from protocolLayerMap, so an event no layer claims shows as such
// rather than being quietly attributed.

import React from "react";
import { defaultEventStyleMap } from "@/constants/dashboardConstants";
import { protocolLayerNodes } from "@/constants/protocolLayerMap";
import type { TelemetryEventType } from "@/types/telemetryEventTypes";

const unclaimedLayerLabel = "not claimed by any layer";

function findEmittingLayers(eventType: TelemetryEventType): readonly string[] {
  return protocolLayerNodes
    .filter((layer) => layer.eventsEmitted.includes(eventType))
    .map((layer) => layer.title);
}

export function EventCatalog(): React.JSX.Element {
  const eventTypes = Object.keys(defaultEventStyleMap) as TelemetryEventType[];

  return (
    <div className="doc-widget overflow-x-auto custom-scrollbar">
      <table>
        <thead>
          <tr>
            <th>Event type</th>
            <th>Badge</th>
            <th>Emitted by</th>
          </tr>
        </thead>
        <tbody>
          {eventTypes.map((eventType) => {
            const layers = findEmittingLayers(eventType);
            return (
              <tr key={eventType}>
                <td>
                  <code>{eventType}</code>
                </td>
                <td>{defaultEventStyleMap[eventType].label}</td>
                <td className={layers.length === 0 ? "text-textMuted" : undefined}>
                  {layers.length === 0 ? unclaimedLayerLabel : layers.join(", ")}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-2 text-[11px] text-textMuted">
        {eventTypes.length} event types, read from{" "}
        <code className="font-mono">TelemetryEventType</code> at build time.
      </p>
    </div>
  );
}
