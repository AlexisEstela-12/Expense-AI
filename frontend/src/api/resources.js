import { postJson } from "./client.js";

export const createMovement = (payload) => postJson("movements", payload);
export const createExchange = (payload) => postJson("exchanges", payload);
export const createBudget = (payload) => postJson("budgets", payload);
