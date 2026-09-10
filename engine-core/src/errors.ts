export class EngineError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "EngineError";
  }
}

export class StaleDecisionError extends EngineError {
  constructor(
    public readonly requestId: string,
    public readonly expectedVersion: number,
    public readonly actualVersion: number,
    public readonly expectedPhaseToken: string,
    public readonly actualPhaseToken: string,
  ) {
    super(`Decision ${requestId} is stale: expected state ${expectedVersion}/${expectedPhaseToken}, current state ${actualVersion}/${actualPhaseToken}`);
    this.name = "StaleDecisionError";
  }
}

export class IllegalDecisionError extends EngineError {
  constructor(public readonly value: unknown, public readonly legalOptions: readonly unknown[]) {
    super(`Illegal decision value: ${String(value)}`);
    this.name = "IllegalDecisionError";
  }
}

export class InvalidTransitionError extends EngineError {
  constructor(from: string, to: string) {
    super(`Invalid phase transition: ${from} -> ${to}`);
    this.name = "InvalidTransitionError";
  }
}
