(() => {
  "use strict";

  const PROTECTED_METHODS = Object.freeze([
    ["app.queuePrompt", (host) => host.app?.queuePrompt],
    ["app.graphToPrompt", (host) => host.app?.graphToPrompt],
    ["nodePrototype.onNodeCreated", (host) => host.nodePrototype?.onNodeCreated],
    ["graphPrototype.configure", (host) => host.graphPrototype?.configure],
  ]);

  function canonicalUnsignedDecimal(value, maximum) {
    if (typeof value !== "string" || typeof maximum !== "string") {
      throw new TypeError("seed and maximum must be decimal strings");
    }
    if (!/^(0|[1-9]\d*)$/.test(value) || !/^(0|[1-9]\d*)$/.test(maximum)) {
      throw new TypeError("seed and maximum must be canonical unsigned decimal strings");
    }

    const parsed = BigInt(value);
    const parsedMaximum = BigInt(maximum);
    if (parsed > parsedMaximum) {
      throw new RangeError("seed exceeds the selected profile maximum");
    }
    return value;
  }

  function captureProtectedMethods(host) {
    return Object.freeze(
      Object.fromEntries(
        PROTECTED_METHODS.map(([name, getter]) => [name, getter(host)]),
      ),
    );
  }

  function assertProtectedMethodsUnchanged(snapshot, host) {
    for (const [name, getter] of PROTECTED_METHODS) {
      if (snapshot[name] !== getter(host)) {
        throw new Error(`protected host method changed: ${name}`);
      }
    }
  }

  Object.defineProperty(window, "TPFrontendContract", {
    configurable: false,
    enumerable: false,
    writable: false,
    value: Object.freeze({
      assertProtectedMethodsUnchanged,
      canonicalUnsignedDecimal,
      captureProtectedMethods,
    }),
  });
})();
