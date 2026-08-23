import { CatalogSkuItem } from "../types/mcpToolTypes.js";
import { catalogFixturesOne } from "./catalogFixturesOne.js";
import { catalogFixturesTwo } from "./catalogFixturesTwo.js";

export const initialCatalogFixtures: readonly CatalogSkuItem[] = [
  ...catalogFixturesOne,
  ...catalogFixturesTwo
];
