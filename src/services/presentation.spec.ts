import { describe, expect, it } from "vitest";
import type { RunCaseDetail, RunSummary } from "@/api/contracts";
import {
  caseTitle,
  readable,
  runTitle,
  scoreText,
  shortDate,
} from "./presentation";

describe("presentation labels", () => {
  it("does not put technical UUIDs into the run label", () => {
    const id = "acce5279-c6a0-46c0-a3ee-8dcdd6ba2fc7";
    const run = {
      run_id: id,
      label: id,
      dataset: "mvtec",
      created_at: "2026-11-11T00:00:00Z",
    } as RunSummary;
    expect(runTitle(run)).not.toContain(id);
    expect(runTitle({ ...run, label: "瓶体检测" })).toBe("瓶体检测");
    expect(
      runTitle({ ...run, label: "MVTEC · mvtec_noisy_0001" }),
    ).not.toContain("mvtec_noisy_0001");
    expect(runTitle({ ...run, source_filename: "/uploads/bottle.png" })).toBe(
      "bottle",
    );
  });
  it("identifies synthetic examples and formats missing data without fake precision", () => {
    expect(
      caseTitle({
        case_id: "mvtec_fixture_clean_scratch",
        generated_evidence: { fixture_type: "controlled_synthetic" },
      } as RunCaseDetail),
    ).toContain("合成");
    expect(scoreText(null)).toBe("未提供");
    expect(scoreText(NaN)).toBe("未提供");
    expect(scoreText(0.8)).toBe("0.80");
    expect(shortDate("bad-date")).toBe("时间未记录");
    expect(shortDate("2026-11-11T00:00:00Z")).toContain("08:00");
    expect(readable("None")).toBe("未命名");
  });
});
