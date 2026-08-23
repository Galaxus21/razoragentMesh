import { initialCatalogFixtures } from "./catalogFixtures.js";
import {
  meshCatalogUpdatesChannel,
  catalogEventAdded,
  catalogEventUpdated,
  catalogEventRemoved
} from "../constants/protocolConstants.js";
import {
  CatalogSkuItem,
  SkuFilterCriteria,
  SkuNotFoundException,
  catalogSkuItemSchema,
  RedisChannelSubscriber
} from "../types/mcpToolTypes.js";

export class CatalogStore {
  private readonly itemsMap = new Map<string, CatalogSkuItem>();
  private readonly stockMap = new Map<string, number>();

  constructor(initialItems: readonly CatalogSkuItem[] = initialCatalogFixtures) {
    this.seedCatalog(initialItems);
  }

  public seedCatalog(items: readonly CatalogSkuItem[]): void {
    this.itemsMap.clear();
    this.stockMap.clear();

    for (const rawItem of items) {
      const validatedItem = catalogSkuItemSchema.parse(rawItem);
      this.itemsMap.set(validatedItem.skuId, validatedItem);
      this.stockMap.set(validatedItem.skuId, validatedItem.availableStock);
    }
  }

  public addSku(item: CatalogSkuItem): void {
    const validated = catalogSkuItemSchema.parse(item);
    this.itemsMap.set(validated.skuId, validated);
    this.stockMap.set(validated.skuId, validated.availableStock);
  }

  public removeSku(skuId: string): boolean {
    this.stockMap.delete(skuId);
    return this.itemsMap.delete(skuId);
  }

  public subscribeToCatalogChannel(redisSubscriber: RedisChannelSubscriber): void {
    redisSubscriber.subscribe(meshCatalogUpdatesChannel);
    redisSubscriber.on("message", (channel: unknown, rawMessage: unknown) => {
      if (typeof channel !== "string" || channel !== meshCatalogUpdatesChannel) {
        return;
      }
      if (typeof rawMessage !== "string") {
        return;
      }
      try {
        const parsed = JSON.parse(rawMessage) as {
          action?: string;
          event?: string;
          type?: string;
          item?: unknown;
          payload?: unknown;
          skuId?: string;
          sku_id?: string;
        };
        const actionType = parsed.action ?? parsed.event ?? parsed.type;
        if (
          actionType === catalogEventAdded ||
          actionType === catalogEventUpdated ||
          actionType === "CATALOG_ITEM_ADDED" ||
          actionType === "CATALOG_ITEM_UPDATED"
        ) {
          const itemData = (parsed.item ?? parsed.payload ?? parsed) as CatalogSkuItem;
          this.addSku(itemData);
        } else if (
          actionType === catalogEventRemoved ||
          actionType === "CATALOG_ITEM_REMOVED"
        ) {
          const skuId =
            parsed.skuId ??
            parsed.sku_id ??
            (parsed.payload as { skuId?: string; sku_id?: string })?.skuId ??
            (parsed.payload as { skuId?: string; sku_id?: string })?.sku_id;
          if (skuId) {
            this.removeSku(skuId);
          }
        }
      } catch {
        // Ignore malformed message payloads gracefully
      }
    });
  }

  public getSku(skuId: string): CatalogSkuItem | undefined {
    const item = this.itemsMap.get(skuId);
    if (!item) {
      return undefined;
    }

    const currentStock = this.stockMap.get(skuId) ?? item.availableStock;
    return {
      ...item,
      availableStock: currentStock
    };
  }

  public getRequiredSku(skuId: string): CatalogSkuItem {
    const sku = this.getSku(skuId);
    if (!sku) {
      throw new SkuNotFoundException(skuId);
    }
    return sku;
  }

  public getAllSkus(): CatalogSkuItem[] {
    const results: CatalogSkuItem[] = [];
    for (const skuId of this.itemsMap.keys()) {
      const sku = this.getSku(skuId);
      if (sku) {
        results.push(sku);
      }
    }
    return results;
  }

  public getStock(skuId: string): number {
    return this.stockMap.get(skuId) ?? 0;
  }

  public updateStock(skuId: string, quantityDelta: number): number {
    const currentStock = this.getStock(skuId);
    const newStock = Math.max(0, currentStock + quantityDelta);
    this.stockMap.set(skuId, newStock);
    return newStock;
  }

  public resetCatalog(): void {
    this.seedCatalog(initialCatalogFixtures);
  }

  public filterSkus(criteria: SkuFilterCriteria): CatalogSkuItem[] {
    return this.getAllSkus().filter((sku) => {
      if (criteria.category && sku.category.toLowerCase() !== criteria.category.toLowerCase()) {
        return false;
      }
      if (criteria.hsnCode && sku.hsnCode !== criteria.hsnCode) {
        return false;
      }
      if (criteria.minStock !== undefined && sku.availableStock < criteria.minStock) {
        return false;
      }
      if (criteria.brand && sku.brand?.toLowerCase() !== criteria.brand.toLowerCase()) {
        return false;
      }
      return true;
    });
  }
}

export const defaultCatalogStore = new CatalogStore();
