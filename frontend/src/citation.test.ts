import { describe, expect, it } from "vitest";
import { findCitationSpanRange } from "./citation";

describe("citation text matching", () => {
  it("finds a cited quote split across PDF text spans", () => {
    expect(
      findCitationSpanRange(
        ["The launch", "vehicle reached", "orbit safely."],
        "vehicle reached orbit",
      ),
    ).toEqual([1, 2]);
  });

  it("does not mark unrelated PDF text", () => {
    expect(findCitationSpanRange(["No matching source here"], "a different quote")).toEqual([]);
  });

  it("does not treat a partial quote as a match", () => {
    expect(findCitationSpanRange(["vehicle reached"], "vehicle reached orbit")).toEqual([]);
  });
});
