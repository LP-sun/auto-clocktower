/** Standard executions require a strict majority of currently alive players. */
export function executionThreshold(alive: number): number {
  if (!Number.isInteger(alive) || alive < 1) throw new Error("Invalid alive count");
  return Math.floor(alive / 2) + 1;
}
