import test from "node:test";
import assert from "node:assert/strict";
import { getDistribution } from "./distribution";

test("Trouble Brewing base distributions cover 5–15 players", () => {
  const expected: Record<number, [number, number, number, number]> = {
    5: [3, 0, 1, 1], 6: [3, 1, 1, 1], 7: [5, 0, 1, 1],
    8: [5, 1, 1, 1], 9: [5, 2, 1, 1], 10: [7, 0, 2, 1],
    11: [7, 1, 2, 1], 12: [7, 2, 2, 1], 13: [9, 0, 3, 1],
    14: [9, 1, 3, 1], 15: [9, 2, 3, 1],
  };
  for (const [count, values] of Object.entries(expected)) {
    const distribution = getDistribution(Number(count));
    assert.deepEqual(
      [distribution.townsfolk, distribution.outsiders, distribution.minions, distribution.demon],
      values,
    );
    assert.equal(values.reduce((a, b) => a + b, 0), Number(count));
  }
});

test("distribution rejects unsupported player counts", () => {
  assert.throws(() => getDistribution(4), RangeError);
  assert.throws(() => getDistribution(16), RangeError);
});
