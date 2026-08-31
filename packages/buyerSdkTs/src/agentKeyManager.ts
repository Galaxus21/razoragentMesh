import nacl from "tweetnacl";
import { bytesToHex, hexToBytes } from "./isomorphicCrypto.js";
import {
  didPrefix,
  keyHexLength,
  seedByteLength,
  signatureHexLength
} from "./sdkConstants.js";
import { canonicalizeJson } from "./jcsCanonicalizer.js";
import type { AgentKeyPair } from "./types.js";

const hex64Pattern = /^[0-9a-fA-F]{64}$/;
const hex128Pattern = /^[0-9a-fA-F]{128}$/;

export function formatAgentDid(publicKeyHex: string): string {
  const cleanHex = (publicKeyHex ?? "").trim().toLowerCase();
  if (!hex64Pattern.test(cleanHex)) {
    throw new Error(`Invalid public key hex: expected ${keyHexLength} hex characters, got '${cleanHex}'`);
  }
  return `${didPrefix}${cleanHex}`;
}

export function extractPublicKeyFromDid(did: string): string {
  if (typeof did !== "string" || !did.startsWith(didPrefix)) {
    throw new Error(`Invalid DID format: '${did}', expected prefix '${didPrefix}'`);
  }
  const keyHex = did.slice(didPrefix.length).trim().toLowerCase();
  if (!hex64Pattern.test(keyHex)) {
    throw new Error(`Invalid DID public key hex: expected ${keyHexLength} hex characters, got '${keyHex}'`);
  }
  return keyHex;
}

export function generateAgentKeyPair(seedHex?: string): AgentKeyPair {
  let keyPair: nacl.SignKeyPair;
  if (seedHex !== undefined) {
    const cleanSeedHex = seedHex.trim();
    if (!hex64Pattern.test(cleanSeedHex)) {
      throw new TypeError("Invalid seed: must be 64 valid hex characters (32 bytes)");
    }
    const seedBytes = hexToBytes(cleanSeedHex.toLowerCase());
    keyPair = nacl.sign.keyPair.fromSeed(new Uint8Array(seedBytes));
  } else {
    keyPair = nacl.sign.keyPair();
  }

  const publicKeyHex = bytesToHex(keyPair.publicKey);
  const secretKeyHex = bytesToHex(keyPair.secretKey);

  return {
    publicKeyHex,
    secretKeyHex,
    agentDid: formatAgentDid(publicKeyHex)
  };
}

export class AgentKeyManager {
  private readonly _keyPair: nacl.SignKeyPair;
  private readonly _publicKeyHex: string;
  private readonly _secretKeyHex: string;
  private readonly _agentDid: string;

  public constructor(seedOrSecretKeyHex?: string) {
    if (seedOrSecretKeyHex !== undefined) {
      const cleanHex = seedOrSecretKeyHex.trim();
      if (cleanHex.length === keyHexLength) {
        if (!hex64Pattern.test(cleanHex)) {
          throw new TypeError("Invalid seed: must be 64 valid hex characters (32 bytes)");
        }
        const seedBytes = hexToBytes(cleanHex.toLowerCase());
        this._keyPair = nacl.sign.keyPair.fromSeed(new Uint8Array(seedBytes));
      } else if (cleanHex.length === keyHexLength * 2) {
        if (!hex128Pattern.test(cleanHex)) {
          throw new Error(`Invalid secret key hex string: expected ${keyHexLength * 2} valid hex characters, got non-hex characters`);
        }
        const secretBytes = hexToBytes(cleanHex.toLowerCase());
        this._keyPair = nacl.sign.keyPair.fromSecretKey(new Uint8Array(secretBytes));
      } else {
        throw new Error(`Invalid key hex length: expected 64 or 128 hex characters, got ${cleanHex.length}`);
      }
    } else {
      this._keyPair = nacl.sign.keyPair();
    }

    this._publicKeyHex = bytesToHex(this._keyPair.publicKey);
    this._secretKeyHex = bytesToHex(this._keyPair.secretKey);
    this._agentDid = formatAgentDid(this._publicKeyHex);
  }

  public static generate(): AgentKeyManager {
    return new AgentKeyManager();
  }

  public static fromSeed(seedHex: string): AgentKeyManager {
    if (typeof seedHex !== "string" || !hex64Pattern.test(seedHex.trim())) {
      throw new TypeError("Invalid seed: must be 64 valid hex characters (32 bytes)");
    }
    return new AgentKeyManager(seedHex);
  }

  public static fromSecretKey(secretKeyHex: string): AgentKeyManager {
    if (typeof secretKeyHex !== "string" || !hex128Pattern.test(secretKeyHex.trim())) {
      throw new Error(`Invalid secret key hex string: expected ${keyHexLength * 2} valid hex characters`);
    }
    return new AgentKeyManager(secretKeyHex);
  }

  public getPublicKeyHex(): string {
    return this._publicKeyHex;
  }

  public getSecretKeyHex(): string {
    return this._secretKeyHex;
  }

  public getAgentDid(): string {
    return this._agentDid;
  }

  public signCanonicalBytes(canonicalBytes: Uint8Array): string {
    const signature = nacl.sign.detached(canonicalBytes, this._keyPair.secretKey);
    return bytesToHex(signature);
  }

  public signPayload(payload: unknown): string {
    const canonicalBytes = canonicalizeJson(payload);
    return this.signCanonicalBytes(canonicalBytes);
  }

  public verifySignature(canonicalBytes: Uint8Array, signatureHex: string, publicKeyHex?: string): boolean {
    try {
      if (!canonicalBytes || !(canonicalBytes instanceof Uint8Array)) {
        return false;
      }
      const targetPubKeyHex = (publicKeyHex ?? this._publicKeyHex).trim();
      const cleanSigHex = (signatureHex ?? "").trim();

      if (!hex64Pattern.test(targetPubKeyHex) || !hex128Pattern.test(cleanSigHex)) {
        return false;
      }

      const pubKeyBytes = new Uint8Array(hexToBytes(targetPubKeyHex.toLowerCase()));
      const sigBytes = new Uint8Array(hexToBytes(cleanSigHex.toLowerCase()));

      if (pubKeyBytes.length !== seedByteLength || sigBytes.length !== signatureHexLength / 2) {
        return false;
      }

      return nacl.sign.detached.verify(canonicalBytes, sigBytes, pubKeyBytes);
    } catch {
      return false;
    }
  }

  public verifyPayloadSignature(payload: unknown, signatureHex: string, publicKeyHex?: string): boolean {
    try {
      const canonicalBytes = canonicalizeJson(payload);
      return this.verifySignature(canonicalBytes, signatureHex, publicKeyHex);
    } catch {
      return false;
    }
  }
}
