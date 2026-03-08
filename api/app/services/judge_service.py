"""LLM-as-Judge: оценка выходов агента по структурированным rubrics.

Ключевые принципы:
- Structured rubrics: каждый критерий оценивается отдельно (0..1)
- Bias mitigation: judge не видит expected answer, только rubric
- Reasoning first: judge сначала рассуждает, потом ставит оценку
- Weighted scoring: итоговый score = weighted average по критериям
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from app.schemas.evaluation import (
    CriterionScore,
    JudgeRequest,
    JudgeResponse,
    RubricCriterion,
)

logger = logging.getLogger(__name__)

JUDGE_SYSTEM_PROMPT = """\
You are an expert code reviewer and AI agent evaluator. Your job is to evaluate \
an AI agent's output against a specific rubric.

## Instructions

1. Read the TASK that was given to the agent.
2. Read the AGENT OUTPUT (the agent's response).
3. For each CRITERION in the rubric, evaluate the output:
   - Provide detailed reasoning for your score.
   - Assign a score from 0.0 to 1.0.
4. Be strict but fair. A score of 1.0 means perfect adherence to the criterion.
5. Do NOT invent criteria beyond what's specified in the rubric.

## Bias Mitigation Rules

- Evaluate the CONTENT, not the style or length of the response.
- Do not penalize for different but equally valid approaches.
- Focus on correctness and completeness, not verbosity.
- If the criterion is ambiguous, interpret it charitably.

## Output Format

Respond with a JSON object (and nothing else) matching this schema:
{
  "criteria_scores": [
    {
      "name": "<criterion name>",
      "score": <0.0-1.0>,
      "reasoning": "<detailed explanation>"
    }
  ],
  "overall_reasoning": "<high-level summary of evaluation>"
}
"""


def _build_judge_user_prompt(request: JudgeRequest) -> str:
    """Собрать user prompt для judge из задачи, вывода агента и rubric."""
    parts: list[str] = []

    parts.append("## TASK\n")
    parts.append(request.task_prompt)

    if request.context_files:
        parts.append("\n\n## CONTEXT FILES\n")
        for path, content in request.context_files.items():
            parts.append(f"\n### {path}\n```\n{content}\n```")

    if request.expected_artifacts:
        parts.append("\n\n## EXPECTED ARTIFACTS\n")
        for artifact in request.expected_artifacts:
            parts.append(f"- {artifact}")

    parts.append("\n\n## AGENT OUTPUT\n")
    parts.append(request.agent_output)

    parts.append("\n\n## RUBRIC\n")
    parts.append("Evaluate the agent output against each of the following criteria:\n")
    for i, criterion in enumerate(request.rubric, 1):
        parts.append(
            f"{i}. **{criterion.name}** (weight: {criterion.weight}, "
            f"pass threshold: {criterion.pass_threshold}): {criterion.description}"
        )

    parts.append(
        "\n\nRespond with the JSON evaluation object only. No markdown fences."
    )

    return "\n".join(parts)


def _parse_judge_response(
    raw: str, rubric: list[RubricCriterion]
) -> JudgeResponse:
    """Распарсить JSON-ответ judge в структурированный JudgeResponse."""
    # Убрать markdown code fences если judge всё-таки их добавил
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    data: dict[str, Any] = json.loads(text)

    criteria_scores: list[CriterionScore] = []
    for item in data.get("criteria_scores", []):
        criteria_scores.append(
            CriterionScore(
                name=item["name"],
                score=max(0.0, min(1.0, float(item["score"]))),
                reasoning=item.get("reasoning", ""),
            )
        )

    # Weighted average score
    total_weight = sum(c.weight for c in rubric) or 1.0
    weighted_sum = 0.0
    for criterion in rubric:
        matching = next(
            (cs for cs in criteria_scores if cs.name == criterion.name), None
        )
        if matching:
            weighted_sum += matching.score * criterion.weight

    overall_score = weighted_sum / total_weight

    # Verdict: pass если каждый критерий >= его threshold (weighted)
    all_pass = True
    for criterion in rubric:
        matching = next(
            (cs for cs in criteria_scores if cs.name == criterion.name), None
        )
        if not matching or matching.score < criterion.pass_threshold:
            all_pass = False
            break

    return JudgeResponse(
        verdict="pass" if all_pass else "fail",
        score=round(overall_score, 3),
        criteria_scores=criteria_scores,
        reasoning=data.get("overall_reasoning", ""),
    )


async def judge_agent_output(
    request: JudgeRequest,
    model: str = "claude-sonnet-4-20250514",
    api_key: str | None = None,
) -> JudgeResponse:
    """Вызвать LLM-as-Judge для оценки выхода агента.

    Args:
        request: задача + выход агента + rubric
        model: модель для judge (default: Sonnet — дешевле Opus, достаточно умна)
        api_key: Anthropic API key (если None — берётся из ANTHROPIC_API_KEY env)

    Returns:
        JudgeResponse с verdict, score, criteria_scores и reasoning
    """
    client = anthropic.AsyncAnthropic(api_key=api_key) if api_key else anthropic.AsyncAnthropic()

    user_prompt = _build_judge_user_prompt(request)

    logger.info(
        "Judging agent output: model=%s, criteria=%d",
        model,
        len(request.rubric),
    )

    message = await client.messages.create(
        model=model,
        max_tokens=4096,
        system=JUDGE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_response = message.content[0].text
    token_usage = {
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
    }

    logger.info(
        "Judge response: tokens=%s",
        token_usage,
    )

    response = _parse_judge_response(raw_response, request.rubric)

    return response, token_usage
