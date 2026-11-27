"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const core = require("../public/core.js");

test("strict filter parser emits an explicit UTC-04:00 timestamp", function () {
  assert.equal(core.parseDateTime("2024-03-09T06:07"), "2024-03-09T06:07:00-04:00");
  assert.equal(core.parseDateTime("2024-02-29T23:59"), "2024-02-29T23:59:00-04:00");
});

test("filter parser rejects invalid calendar dates and non-padded input", function () {
  assert.throws(function () { core.parseDateTime("2024-02-31T12:00"); });
  assert.throws(function () { core.parseDateTime("2024-03-1T12:00"); });
  assert.throws(function () { core.parseDateTime(""); });
  assert.throws(function () { core.parseDateTime("2024-03-01T24:00"); });
});

test("exclusive end minimum advances one source-local minute including day boundaries", function () {
  assert.equal(core.minimumEnd("2024-03-20T14:30"), "2024-03-20T14:31");
  assert.equal(core.minimumEnd("2024-02-29T23:59"), "2024-03-01T00:00");
  assert.equal(core.minimumEnd("2024-12-31T23:59"), "2025-01-01T00:00");
  assert.throws(function () { core.minimumEnd(""); });
  assert.throws(function () { core.minimumEnd("9999-12-31T23:59"); });
});

test("formatter uses fixed UTC-04:00 dd/mm/yyyy hh:mm regardless of host timezone", function () {
  assert.equal(core.formatTimestamp("2024-03-20T12:34:00Z"), "20/03/2024 08:34");
  assert.equal(core.formatBucket("2024-03-20", "day"), "20/03/2024 00:00");
  assert.equal(core.formatBucket("2024-03-20T08:00-04:00", "hour"), "20/03/2024 08:00");
});

test("dashboard shell asset URLs resolve through the Node-RED allowlist", function () {
  const dashboard = path.join(__dirname, "..");
  const html = fs.readFileSync(path.join(dashboard, "public", "index.html"), "utf8");
  const flows = JSON.parse(fs.readFileSync(path.join(dashboard, "flows.json"), "utf8"));
  const route = flows.find(function (node) { return node.id === "dash-assets-in"; });
  const resolver = flows.find(function (node) { return node.id === "dash-assets-allowlist"; });
  assert.equal(route.url, "/assets/:asset");
  const resolve = new Function("msg", resolver.func);
  const urls = Array.from(html.matchAll(/(?:href|src)="(\/assets\/[^"]+)"/g), function (match) { return match[1]; });
  assert.ok(urls.length > 0);
  for (const url of urls) {
    const asset = url.slice("/assets/".length);
    assert.ok(asset && !asset.includes("/"), `${url} does not match ${route.url}`);
    const [allowed, rejected] = resolve({ req: { params: { asset } } });
    assert.ok(allowed && !rejected, `${url} is not allowlisted`);
  }
});
