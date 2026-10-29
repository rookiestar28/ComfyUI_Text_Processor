// Authored graph facades, not execution of the upstream frontend.
import { expect, test } from "@playwright/test";
import fs from "node:fs/promises";
import { loadExtension, eventPayload } from "./seed_host_harness.mjs";

const tiers = JSON.parse(await fs.readFile(new URL("../fixtures/host_compatibility_matrix_v1.json", import.meta.url), "utf8")).tiers;

async function graphFacade(page) {
  await page.evaluate(() => {
    window.__graph = () => ({
      nodes: new Map(), calls: 0,
      getNodeById(id) { this.calls++; return this.nodes.get(id); },
    });
    window.__node = (graph, id, values = {}) => {
      const node = window.__makeNode("999", values);
      window.__host.nodes.delete(node.id);
      node.id = id;
      graph.nodes.set(id, node);
      return node;
    };
    window.__subgraph = (graph, id, child = window.__graph()) => {
      graph.nodes.set(id, { id, isSubgraphNode: () => true, subgraph: child });
      return child;
    };
    window.__values = (node) => node.widgets.map((widget) => widget.value);
    window.__counts = (node) => node.widgets.map((widget) => widget.callbackCount);
    window.__root = window.__graph();
    window.__host.app.rootGraph = window.__root;
    window.__host.app.graph = window.__root;
  });
}

for (const tier of tiers) {
  test(`${tier.id}: root control retains exact callback and queued values`, async ({ page }) => {
    await loadExtension(page, tier);
    await graphFacade(page);
    const result = await page.evaluate((payload) => {
      const id = (value) => window.__host.tierId === "desktop_floor" ? Number(value) : value;
      const c = window.__node(window.__root, id("1"), { value: "0", last_seed: "0" });
      const t = window.__node(window.__root, id("2"), { seed: 7 });
      window.__dispatchSeed(payload);
      return [window.__values(c), window.__values(t), window.__counts(c), window.__counts(t)];
    }, eventPayload());
    expect(result).toEqual([["4294967295", "4294967295"], [4294967295], [1, 1], [1]]);
  });

  for (const open of [false, true]) {
    test(`${tier.id}: ${open ? "open" : "closed"} nested instance paths update only addressed widgets`, async ({ page }) => {
      await loadExtension(page, tier);
      await graphFacade(page);
      const result = await page.evaluate(({ payload, open }) => {
        const id = (value) => window.__host.tierId === "desktop_floor" ? Number(value) : value;
        const nested = window.__subgraph(window.__subgraph(window.__root, id("10")), "inner");
        const other = window.__subgraph(window.__root, id("11"));
        const c = window.__node(nested, "controller", { value: "0", last_seed: "0" });
        const t = window.__node(nested, "target", { seed: 17, other: 9 });
        const rootDecoy = window.__node(window.__root, "target", { seed: 21 });
        const otherDecoy = window.__node(other, "target", { seed: 23 });
        // A literal ID loses to the verified path, as in the pinned source resolver.
        const literalDecoy = window.__node(window.__root, "10:inner:target", { seed: 25 });
        if (open) {
          window.__host.app.graph = nested;
          window.__host.app.canvas = { graph: other };
        }
        window.__dispatchSeed(payload);
        const queued = [window.__values(c), window.__values(t)];
        const serialized = JSON.parse(JSON.stringify(queued));
        // Replay through the public setters, retaining exact decimal controller text.
        [c, t].forEach((node, i) => node.widgets.forEach((widget, j) => { widget.value = serialized[i][j]; }));
        return { queued, restored: [window.__values(c), window.__values(t)],
          callbacks: [window.__counts(c), window.__counts(t)],
          decoys: [rootDecoy, otherDecoy, literalDecoy].map(window.__values),
          state: tierState(c, t) };
        function tierState(...nodes) { return nodes.flatMap((node) => node.widgets.map((widget) => widget.state.value)); }
      }, { open, payload: eventPayload({ controller_id: "10:inner:controller", seed_width: "uint53",
        applied_seed: "9007199254740991", next_value: "9007199254740991",
        targets: [{ node_id: "10:inner:target", inputs: [{ name: "seed", seed: "9007199254740991" }] }] }) });
      expect(result.queued).toEqual([["9007199254740991", "9007199254740991"], [9007199254740991, 9]]);
      expect(result.restored).toEqual(result.queued);
      expect(result.callbacks).toEqual([[1, 1], [1, 0]]);
      expect(result.decoys).toEqual([[21], [23], [25]]);
      if (tier.widget_facade === "state_backed") expect(result.state).toEqual(["9007199254740991", "9007199254740991", 9007199254740991, 9]);
    });
  }

  test(`${tier.id}: literal colon and unsafe numeric-looking opaque IDs retain exact lookup`, async ({ page }) => {
    await loadExtension(page, tier);
    await graphFacade(page);
    const result = await page.evaluate((payload) => {
      const c = window.__node(window.__root, "opaque:controller", { value: "0", last_seed: "0" });
      const graph = window.__subgraph(window.__root, "opaque:host");
      const target = window.__node(graph, "9007199254740993", { noise_seed: 3 });
      const decoy = window.__node(graph, 9007199254740992, { noise_seed: 5 });
      window.__dispatchSeed(payload);
      return [window.__values(c), window.__values(target), window.__values(decoy)];
    }, eventPayload({ controller_id: "opaque:controller", targets: [{ node_id: "opaque:host:9007199254740993", inputs: [{ name: "noise_seed", seed: "4294967295" }] }] }));
    expect(result).toEqual([["4294967295", "4294967295"], [4294967295], [5]]);
  });

  test(`${tier.id}: nested uint64 updates text while missing and unsafe numeric widgets remain untouched`, async ({ page }) => {
    await loadExtension(page, tier);
    await graphFacade(page);
    const result = await page.evaluate((payload) => {
      const child = window.__subgraph(window.__root, "host");
      const c = window.__node(child, "controller", { value: "0", last_seed: "0" });
      const t = window.__node(child, "target", { seed: 17 });
      const absent = window.__node(child, "absent", { other: 19 });
      window.__dispatchSeed(payload);
      return [window.__values(c), window.__values(t), window.__values(absent), window.__counts(t), window.__counts(absent)];
    }, eventPayload({ controller_id: "host:controller", seed_width: "uint64", applied_seed: "18446744073709551615", next_value: "18446744073709551615",
      targets: [{ node_id: "host:target", inputs: [{ name: "seed", seed: "18446744073709551615" }] },
        { node_id: "host:absent", inputs: [{ name: "seed", seed: "1" }] }] }));
    expect(result).toEqual([["18446744073709551615", "18446744073709551615"], [17], [19], [0], [0]]);
  });
}

for (const scenario of ["missing", "ambiguous", "cycle", "malformed", "throwing", "numeric-collision", "root-miss"]) {
  test(`${scenario}: no fallback can mutate an unrelated instance`, async ({ page }) => {
    await loadExtension(page, tiers[2]);
    await graphFacade(page);
    const result = await page.evaluate(({ scenario, payload }) => {
      const root = window.__root;
      const other = window.__graph();
      const decoys = [window.__node(other, "target", { seed: 11 }), window.__node(other, "a:b:target", { seed: 13 })];
      window.__host.app.graph = other;
      window.__host.app.canvas = { graph: other };
      let nodeId = "a:b:target";
      if (scenario === "ambiguous") {
        const a = window.__subgraph(root, "a");
        decoys.push(window.__node(a, "b:target", { seed: 17 }));
        const ab = window.__subgraph(root, "a:b");
        decoys.push(window.__node(ab, "target", { seed: 19 }));
        decoys.push(window.__node(root, nodeId, { seed: 23 }));
      } else if (scenario === "cycle") {
        window.__subgraph(root, "a", root);
        decoys.push(window.__node(root, nodeId, { seed: 23 }));
      } else if (scenario === "malformed") {
        window.__subgraph(root, "a", {});
        decoys.push(window.__node(root, nodeId, { seed: 23 }));
      } else if (scenario === "throwing") {
        root.nodes.set("a", { isSubgraphNode() { throw new Error("deleted interface"); } });
        decoys.push(window.__node(root, nodeId, { seed: 23 }));
      } else if (scenario === "numeric-collision") {
        nodeId = "7";
        decoys.push(window.__node(root, "7", { seed: 23 }), window.__node(root, 7, { seed: 29 }));
      } else if (scenario === "root-miss") {
        nodeId = "target";
      }
      const before = decoys.map(window.__values);
      window.__dispatchSeed({ ...payload, controller_id: "absent", targets: [{ node_id: nodeId, inputs: [{ name: "seed", seed: "1" }] }] });
      return { before, after: decoys.map(window.__values), callbacks: decoys.flatMap(window.__counts) };
    }, { scenario, payload: eventPayload() });
    expect(result.after).toEqual(result.before);
    expect(result.callbacks.every((count) => count === 0)).toBe(true);
  });
}

for (const depth of [32, 33]) {
  test(`depth ${depth}: traversal observes the 32-edge boundary`, async ({ page }) => {
    await loadExtension(page, tiers[2]);
    await graphFacade(page);
    const result = await page.evaluate(({ depth, payload }) => {
      let graph = window.__root;
      const path = [];
      for (let i = 0; i < depth; i++) { graph = window.__subgraph(graph, "h"); path.push("h"); }
      const target = window.__node(graph, "target", { seed: 17 });
      window.__dispatchSeed({ ...payload, controller_id: "absent", targets: [{ node_id: [...path, "target"].join(":"), inputs: [{ name: "seed", seed: "1" }] }] });
      return [window.__values(target), window.__counts(target)];
    }, { depth, payload: eventPayload() });
    expect(result).toEqual(depth === 32 ? [[1], [1]] : [[17], [0]]);
  });
}

for (const prefixes of [1023, 1024, 2048]) {
  test(`prefix count ${prefixes}: exact work and ID-length limits fail closed`, async ({ page }) => {
    await loadExtension(page, tiers[2]);
    await graphFacade(page);
    const result = await page.evaluate(({ prefixes, payload }) => {
      const nodeId = "x:".repeat(prefixes) + "end";
      const target = window.__node(window.__root, nodeId, { seed: 17 });
      window.__dispatchSeed({ ...payload, controller_id: "absent", targets: [{ node_id: nodeId, inputs: [{ name: "seed", seed: "1" }] }] });
      return { values: window.__values(target), callbacks: window.__counts(target), calls: window.__root.calls };
    }, { prefixes, payload: eventPayload() });
    expect(result.values).toEqual(prefixes === 1023 ? [1] : [17]);
    expect(result.callbacks).toEqual(prefixes === 1023 ? [1] : [0]);
    expect(result.calls).toBeLessThanOrEqual(1025);
    if (prefixes === 2048) expect(result.calls).toBe(1);
  });
}
