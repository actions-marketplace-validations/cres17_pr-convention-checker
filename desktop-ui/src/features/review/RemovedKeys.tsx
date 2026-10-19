import type { Scan } from "../../bridge";

/** Advisories remain visible even when a rule has no blocking violation. */
export default function RemovedKeys({ scan, onChange }: {
  scan: Scan;
  onChange?: (action: "exclude" | "disable", key: string) => void;
}) {
  const advisories = scan.result.advisories ?? [];
  const stale = scan.result.rule_decisions.flatMap((d) => d.unsatisfied_groups.flatMap((g) =>
    (g.removed_env_keys ?? []).map((key) => ({ key, rule_id: d.rule_id, message: g.evidence ?? "" }))));
  const rows = [...stale, ...advisories];
  if (!rows.length) return null;
  return <section className="card removed-keys" aria-label="삭제된 환경 변수 확인">
    <h2>삭제된 환경 변수 확인</h2>
    <p className="hint">저장소 밖에서 사용하는 키는 키 하나만 예외로 둘 수 있습니다. 설정을 저장하기 전에 확인창이 열립니다.</p>
    <ul>{rows.map((row, i) => <li key={`${row.rule_id}:${row.key}:${i}`}>
      <strong>{row.key}</strong><p>{row.message}</p>
      {onChange && <div className="fix-actions">
        <button className="secondary" onClick={() => onChange("exclude", row.key)}>{row.key} 키는 앞으로 탐지하지 않기</button>
        <button className="secondary" onClick={() => onChange("disable", row.key)}>삭제 키 검사 끄기</button>
      </div>}
    </li>)}</ul>
  </section>;
}
