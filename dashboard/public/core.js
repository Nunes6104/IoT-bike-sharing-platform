(function (root) {
  "use strict";

  function parseDateTime(value) {
    const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
    if (!match) throw new Error("Enter a date and time.");
    const year = Number(match[1]);
    const month = Number(match[2]);
    const day = Number(match[3]);
    const hour = Number(match[4]);
    const minute = Number(match[5]);
    const date = new Date(0);
    date.setUTCFullYear(year, month - 1, day);
    date.setUTCHours(hour, minute, 0, 0);
    if (year < 1 || date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1
      || date.getUTCDate() !== day || hour > 23 || minute > 59) {
      throw new Error("Enter a valid calendar date and time.");
    }
    return String(year).padStart(4, "0") + "-" + String(month).padStart(2, "0")
      + "-" + String(day).padStart(2, "0") + "T" + String(hour).padStart(2, "0")
      + ":" + String(minute).padStart(2, "0") + ":00-04:00";
  }

  function formatTimestamp(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "—";
    const local = new Date(date.getTime() - 4 * 60 * 60 * 1000);
    return String(local.getUTCDate()).padStart(2, "0") + "/"
      + String(local.getUTCMonth() + 1).padStart(2, "0") + "/"
      + String(local.getUTCFullYear()).padStart(4, "0") + " "
      + String(local.getUTCHours()).padStart(2, "0") + ":"
      + String(local.getUTCMinutes()).padStart(2, "0");
  }

  function minimumEnd(value) {
    const time = Date.parse(parseDateTime(value)) - 4 * 60 * 60 * 1000 + 60 * 1000;
    const result = new Date(time).toISOString();
    if (!/^\d{4}-/.test(result)) throw new Error("End time is outside the supported range.");
    return result.slice(0, 16);
  }

  function formatBucket(value, bucket) {
    if (bucket === "hour") {
      if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}[+-]\d{2}:\d{2}$/.test(value)) {
        return formatTimestamp(value);
      }
      if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) {
        return formatTimestamp(value + ":00-04:00");
      }
      return "—";
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return "—";
    return formatTimestamp(value + "T00:00:00-04:00");
  }

  const api = { parseDateTime: parseDateTime, minimumEnd: minimumEnd, formatTimestamp: formatTimestamp, formatBucket: formatBucket };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.BikeDashboardCore = api;
}(typeof window !== "undefined" ? window : globalThis));
