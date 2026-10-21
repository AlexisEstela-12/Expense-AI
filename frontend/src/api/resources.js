import { get, postJson, postWithoutBody } from "./client.js";

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
export const createReimbursementRequest = (payload) =>
  postJson("reimbursements", payload);
export const completeReimbursementRequest = (id, payload) =>
  postJson(`reimbursements/${id}/complete`, payload);
export const createRecurringPaymentRequest = (payload) =>
  postJson("recurring-payments", payload);
export const payRecurringPaymentRequest = (id, payload) =>
  postJson(`recurring-payments/${id}/pay`, payload);
export const createSavingsGoalRequest = (payload) =>
  postJson("savings-goals", payload);
export const addSavingsContributionRequest = (id, payload) =>
  postJson(`savings-goals/${id}/contributions`, payload);
export const cancelSavingsGoalRequest = (id) =>
  postWithoutBody(`savings-goals/${id}/cancel`);
export const useSavingsGoalRequest = (id) =>
  postWithoutBody(`savings-goals/${id}/use`);
export const createCategoryRequest = (payload) =>
  postJson("categories", payload);
