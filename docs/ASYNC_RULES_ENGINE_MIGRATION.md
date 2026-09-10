# Async rules-engine boundary

The Discord game rules now use one small asynchronous adjudication boundary.
The engine owns state, legal domains, and all rule transitions. The
storyteller model may choose only a value in a domain supplied by the engine.
There is no synchronous model callback and no fallback after an invalid model
result.

## Storyteller adapter

Configure the boundary once for a headless run:

```ts
import { setAdjudicationPolicy } from "discord-botc/dist/game/adjudication";

setAdjudicationPolicy(async (state, decision) => {
  // Project `state` to the storyteller's visible view. Return one exact
  // member of decision.legalOptions.
  return await chooseLegalValue(state, decision);
});
```

The single policy handles both legal actions and registrations. Registration
requests have `decision.type === "registration"`; they carry `role`, `player`,
`target`, and an exact `legalOptions` domain. The policy receives `null` state
for registrations because the role subject is already encoded in the request;
the bridge may close over its current authoritative state if needed.

The policy must reject or propagate errors. `InvalidAdjudicationResult` is
raised when a policy returns a value outside the supplied domain. This stops
the current transition and prevents a silent truthful/model fallback.

## Engine call sites

All ambiguous registration observations are awaited:

```ts
const isDemon = await registersAs(targetRole, "Demon", targetState);
```

Night information handlers may return either a draft or a promise. Action
handlers are awaited in the engine's fixed night-order pass. This means a
registration or misinformation request can safely call an LLM without racing
the state transition.

`legalRegistrations` remains synchronous and pure: it only describes the
finite domain. Use it when constructing information choices; use `registersAs`
when the engine needs one actual storyteller registration.

## Runtime migration

The bridge now installs one async policy with `setAdjudicationPolicy` and no
longer uses the `clocktower-ai` player/CSV compatibility layer. It still invokes
the legacy Discord-backed game loop for complete Trouble Brewing character
coverage. `engine-core/` is the new transport-free, instance-owned state-machine
foundation. It already provides serialized transitions, state-versioned
decisions, idempotency, voting and end-of-day execution, but does not yet claim
full character or night-order coverage. New rules work belongs in `engine-core`;
migrate a character only after parity tests pass, then remove the corresponding
Discord handler dependency.
