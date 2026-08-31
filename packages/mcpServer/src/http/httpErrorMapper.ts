import { ZodError } from "zod";
import {
  InsufficientStockException,
  InvalidPincodeException,
  SkuNotFoundException
} from "../types/mcpToolTypes.js";
import {
  statusConflict,
  statusNotFound,
  statusServerError,
  statusUnprocessable
} from "../constants/httpAdapterConstants.js";

export interface MappedHttpError {
  readonly statusCode: number;
  readonly errorName: string;
  readonly detail: string;
  readonly issues?: unknown;
}

const genericErrorName = "InternalError";
const validationErrorName = "ValidationError";
const unknownErrorDetail = "An unexpected error occurred while handling the request.";

// Maps a thrown tool-layer error onto an HTTP status. The buyer SDK branches on status codes
// (see `ClientRequestError` handling in buyerSdkTs/src/razorAgentClient.ts), so an unmapped
// error surfacing as 500 would be indistinguishable from a crash -- map the known ones.
export function mapErrorToHttpResponse(error: unknown): MappedHttpError {
  if (error instanceof ZodError) {
    return {
      statusCode: statusUnprocessable,
      errorName: validationErrorName,
      detail: "Request failed schema validation.",
      issues: error.issues
    };
  }
  if (error instanceof SkuNotFoundException) {
    return { statusCode: statusNotFound, errorName: error.name, detail: error.message };
  }
  if (error instanceof InsufficientStockException) {
    return { statusCode: statusConflict, errorName: error.name, detail: error.message };
  }
  if (error instanceof InvalidPincodeException) {
    return { statusCode: statusUnprocessable, errorName: error.name, detail: error.message };
  }
  if (error instanceof Error) {
    return { statusCode: statusServerError, errorName: error.name || genericErrorName, detail: error.message };
  }
  return { statusCode: statusServerError, errorName: genericErrorName, detail: unknownErrorDetail };
}
