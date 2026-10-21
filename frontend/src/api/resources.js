import { get, postJson } from "./client.js";

export const getSummary = () => get("summary");
export const getMovements = () => get("movements");
export const getBudgets = () => get("budgets");
export const getCategories = () => get("categories");
export const getReimbursements = () => get("reimbursements");
export const getRecurringPayments = () => get("recurring-payments");
export const getSavingsGoals = () => get("savings-goals");
export const getNotifications = () => get("notifications");

export const createMovement = (payload) => postJson("movements", payload);
export const createExchange = (payload) => postJson("exchanges", payload);
export const createBudget = (payload) => postJson("budgets", payload);
