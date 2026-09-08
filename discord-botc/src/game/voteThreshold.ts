/** Standard executions require at least half of currently alive players. */
export function executionThreshold(alive: number): number {
  if (!Number.isInteger(alive) || alive < 1) throw new Error("Invalid alive count");
  return Math.ceil(alive / 2);
}
