"""
RAG 골든 데이터셋 평가 스크립트

골든 데이터셋의 48개 Q&A로 RAG 에이전트 품질을 측정합니다.
A2A 네트워크를 거치지 않고 InternalRAGAgent를 직접 import해서 평가합니다.

측정 지표:
  - retrieval_success: "찾지 못했습니다" 메시지 없이 실제 답변 반환 여부
  - faithfulness:     생성 답변이 정답과 의미적으로 일치하는지 (LLM-as-Judge, 0~1)
  - pass_rate:        faithfulness ≥ 0.7인 비율

사용법:
  cd ai_llm/internal_rag_agent
  python ../../eval_rag_golden.py [--golden <경로>] [--limit N] [--out <결과파일>]
"""

import argparse
import asyncio
import json
import logging
import sys
import os
from datetime import datetime
from typing import Optional

from openai import OpenAI

logging.basicConfig(level=logging.WARNING)

FAIL_PHRASES = [
    "답변할 수 없습니다",
    "찾지 못했습니다",
    "관련 문서를 찾을 수 없습니다",
    "인덱싱된 문서에서 관련 내용을 찾지 못했습니다",
]

_openai_client = OpenAI()

JUDGE_SYSTEM = """당신은 RAG 시스템의 답변 품질을 평가하는 전문 평가자입니다.

평가 기준:
- 1.0: 정답의 핵심 내용을 모두 포함하며 사실적으로 정확함
- 0.7: 핵심 내용의 70% 이상 포함, 주요 오류 없음
- 0.5: 부분적으로 정확하나 중요 내용이 일부 누락되거나 부정확함
- 0.3: 관련 내용이 언급되나 핵심에서 크게 벗어남
- 0.0: 완전히 틀리거나 빈 응답 / 검색 실패 메시지

반드시 JSON으로만 응답하세요: {"score": <0.0~1.0>, "reason": "<한 줄 이유>"}"""


def judge(question: str, golden_answer: str, rag_answer: str) -> dict:
    """LLM이 RAG 답변의 faithfulness를 0~1로 평가."""
    if not rag_answer or any(p in rag_answer for p in FAIL_PHRASES):
        return {"score": 0.0, "reason": "검색 실패 또는 빈 응답"}

    prompt = f"""질문: {question}

[정답]
{golden_answer}

[RAG 답변]
{rag_answer[:2000]}

위 RAG 답변을 정답 기준으로 평가하세요."""

    try:
        resp = _openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        return {"score": 0.0, "reason": f"Judge 오류: {e}"}


async def ask_rag_direct(agent, question: str, debug: bool = False) -> str:
    """InternalRAGAgent를 직접 호출해 최종 답변 반환."""
    items_seen = []
    try:
        async for item in agent.stream(question):
            items_seen.append(item)
            if debug:
                print(f"\n    [DBG] item: {item}")
            if item.get("is_task_complete"):
                return item.get("content", "")
    except Exception as e:
        err = f"[ERROR] {type(e).__name__}: {e}"
        if debug:
            import traceback
            print(f"\n    [DBG] 예외: {traceback.format_exc()}")
        return err
    # is_task_complete 없이 스트림 종료
    if debug:
        print(f"\n    [DBG] 스트림 종료 (완료 이벤트 없음, items={len(items_seen)})")
    return ""


async def evaluate(golden_path: str, limit: Optional[int], out_path: str, args=None):
    # InternalRAGAgent import — cwd 또는 스크립트 옆 경로에서 찾기
    rag_agent_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "ai_llm", "internal_rag_agent",
    )
    cwd = os.getcwd()
    for p in [cwd, rag_agent_dir]:
        if p not in sys.path:
            sys.path.insert(0, p)

    try:
        from agent import InternalRAGAgent
    except ImportError as e:
        print(f"❌ Import 실패: {e}")
        print("   실행 위치: ai_llm/internal_rag_agent 또는 Morning-Agent-Hub 루트")
        sys.exit(1)

    with open(golden_path, encoding="utf-8") as f:
        dataset = json.load(f)

    if limit:
        dataset = dataset[:limit]

    total = len(dataset)
    agent = InternalRAGAgent()
    results = []
    retrieval_ok = 0
    score_sum = 0.0

    print(f"\n{'='*65}")
    print(f"RAG 골든 데이터셋 평가  |  총 {total}개")
    print(f"{'='*65}\n")

    for i, item in enumerate(dataset, 1):
        qid = item.get("id", f"Q{i:03d}")
        question = item["question"]
        golden = item["answer"]

        print(f"[{i:02d}/{total}] {qid}: {question[:42]}...", end=" ", flush=True)

        rag_answer = await ask_rag_direct(agent, question, debug=args.debug)

        is_success = bool(rag_answer) and not any(p in rag_answer for p in FAIL_PHRASES) and not rag_answer.startswith("[ERROR]")
        verdict = judge(question, golden, rag_answer)
        score = verdict.get("score", 0.0)

        if is_success:
            retrieval_ok += 1
        score_sum += score

        if score >= 0.7:
            status = "[PASS]"
        elif score >= 0.4:
            status = "[WARN]"
        else:
            status = "[FAIL]"
        print(f"{status} {score:.2f}  {verdict.get('reason', '')[:55]}")

        results.append({
            "id": qid,
            "question": question,
            "golden_answer": golden,
            "rag_answer": rag_answer,
            "retrieval_success": is_success,
            "faithfulness": score,
            "reason": verdict.get("reason", ""),
            "source_section": item.get("source_section", ""),
            "source_page": item.get("source_page", ""),
        })

    avg_faithfulness = score_sum / total
    retrieval_rate = retrieval_ok / total * 100
    pass_count = sum(1 for r in results if r["faithfulness"] >= 0.7)
    pass_rate = pass_count / total * 100

    print(f"\n{'='*65}")
    print(f"[결과] 평가 요약")
    print(f"{'='*65}")
    print(f"  검색 성공률 (retrieval_success):  {retrieval_ok}/{total} = {retrieval_rate:.1f}%")
    print(f"  Pass율 (faithfulness ≥ 0.7):      {pass_count}/{total} = {pass_rate:.1f}%")
    print(f"  평균 Faithfulness:                {avg_faithfulness:.3f}")
    print(f"{'='*65}\n")

    # 실패 케이스
    failed = sorted([r for r in results if r["faithfulness"] < 0.4], key=lambda x: x["faithfulness"])
    if failed:
        print(f"[FAIL] 낮은 점수 케이스 ({len(failed)}개):")
        for r in failed:
            print(f"  {r['id']} [{r['source_section'][:40]}] score={r['faithfulness']:.2f}")
            print(f"       {r['reason']}")
        print()

    report = {
        "evaluated_at": datetime.now().isoformat(),
        "total": total,
        "retrieval_success_count": retrieval_ok,
        "retrieval_success_rate": round(retrieval_rate, 1),
        "pass_count": pass_count,
        "pass_rate_07": round(pass_rate, 1),
        "avg_faithfulness": round(avg_faithfulness, 3),
        "results": results,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"[저장] 결과 파일: {out_path}")

    return report


def main():
    parser = argparse.ArgumentParser(description="RAG 골든 데이터셋 평가")
    parser.add_argument(
        "--golden",
        default=r"C:\Users\82105\Documents\카카오톡 받은 파일\golden_dataset.json",
        help="골든 데이터셋 JSON 경로",
    )
    parser.add_argument("--limit", type=int, default=None, help="평가할 최대 문항 수 (기본: 전체)")
    parser.add_argument(
        "--out",
        default=None,
        help="결과 JSON 저장 경로",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="첫 번째 질문만 실행하고 스트림 이벤트 상세 출력",
    )
    args = parser.parse_args()

    out = args.out or f"eval_result_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    limit = 1 if args.debug else args.limit
    asyncio.run(evaluate(args.golden, limit, out, args))


if __name__ == "__main__":
    main()
