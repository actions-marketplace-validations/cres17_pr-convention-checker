// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import fixture from "../../preview-fixture.json";
import type { Scan } from "../../bridge";
import RemovedKeys from "./RemovedKeys";
afterEach(cleanup);
const scan: Scan = { ...fixture, result: { ...fixture.result, result: "warn", advisories: [
  { rule_id: "env", key: "LEGACY_TOKEN", kind: "config", paths: ["launch.sh"], message: "launch.sh에서 사용 여부 확인" },
] } };
it("shows advisory-only results and requests the two explicit policy actions", () => {
  const change = vi.fn();
  render(<RemovedKeys scan={scan} onChange={change} />);
  expect(screen.getByText(/launch.sh에서/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "LEGACY_TOKEN 키는 앞으로 탐지하지 않기" }));
  expect(change).toHaveBeenLastCalledWith("exclude", "LEGACY_TOKEN");
  fireEvent.click(screen.getByRole("button", { name: "삭제 키 검사 끄기" }));
  expect(change).toHaveBeenLastCalledWith("disable", "LEGACY_TOKEN");
});
it("keeps historical results read-only", () => {
  render(<RemovedKeys scan={scan} />);
  expect(screen.queryAllByRole("button")).toHaveLength(0);
});
it("also offers actions on confirmed stale keys", () => {
  const value: Scan = { ...scan, result: { ...scan.result, advisories: [], rule_decisions: [{
    rule_id: "env", status: "fail", reason: "stale", trigger_files: ["src/a.py"], satisfied_groups: [],
    unsatisfied_groups: [{ name: "Environment", evidence: "코드에서 제거됐는데 문서에 남음", removed_env_keys: ["OLD_KEY"] }],
  }] } };
  render(<RemovedKeys scan={value} onChange={vi.fn()} />);
  expect(screen.getByRole("button", { name: "OLD_KEY 키는 앞으로 탐지하지 않기" })).toBeTruthy();
});
