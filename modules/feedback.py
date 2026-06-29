import json
from datetime import datetime

import google.generativeai as genai


def generate_final_feedback(
    feedback_log: list,
    language: str,
    settings,
) -> str:
    if not feedback_log:
        return "No questions were answered during this session."

    
    scores = [entry["score"] for entry in feedback_log]
    overall = round(sum(scores) / len(scores), 1)

    
    interview_data_lines = []
    for i, entry in enumerate(feedback_log, 1):
        interview_data_lines.append(
            f"  Q{i}: {entry['question']}\n"
            f"      Score: {entry['score']}/5\n"
            f"      Notes: {entry['notes']}"
        )
    interview_data = "\n\n".join(interview_data_lines)

    prompt = (
        f"You are writing a post-interview evaluation report for a recruiter.\n"
        f"The interview was for a Python Backend Software Engineering role.\n"
        f"The interview was conducted in {language}.\n"
        f"Write the ENTIRE report in English regardless of the interview language.\n\n"
        f"Interview data:\n{interview_data}\n\n"
        f"The computed overall score is {overall}/5. Use this exact number.\n\n"
        f"Generate a structured report with EXACTLY these sections in this order:\n\n"
        f"OVERALL SCORE: {overall}/5\n"
        f"HIRING RECOMMENDATION: [Strong Yes / Yes / Maybe / No]\n\n"
        f"STRENGTHS:\n"
        f"- (bullet points, specific and evidence-based from the interview data)\n\n"
        f"AREAS FOR IMPROVEMENT:\n"
        f"- (bullet points, actionable and specific)\n\n"
        f"QUESTION-BY-QUESTION BREAKDOWN:\n"
        f"(list each question with its score and a one-sentence observation)\n\n"
        f"FINAL SUMMARY:\n"
        f"(2-3 sentences for a hiring manager who will not read the full transcript)\n\n"
        f"Important: Be specific and reference actual answers/notes. "
        f"Do not be generic. The recruiter needs actionable signal."
    )

    try:
        model = genai.GenerativeModel(model_name=settings.llm_model)
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(temperature=0.7),
        )
        return response.text.strip()

    except Exception as e:
        fallback = (
            f"OVERALL SCORE: {overall}/5\n"
            f"HIRING RECOMMENDATION: Manual review needed\n\n"
            f"Note: Report generation failed ({e}).\n"
            f"Please review the raw interview log below for evaluation details."
        )
        return fallback


def save_report(
    feedback_text: str,
    feedback_log: list,
    language: str,
) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"interview_report_{timestamp}.txt"

    SEP = "=" * 60
    header = (
        SEP + "\n"
        + "  VOICE INTERVIEW AGENT - EVALUATION REPORT\n"
        + SEP + "\n"
        + f"  Interview Language : {language}\n"
        + f"  Generated At       : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        + f"  Questions Answered : {len(feedback_log)}\n"
        + SEP + "\n\n"
    )

    raw_log_section = (
        "\n\n" + SEP + "\n"
        + "  RAW AUDIT LOG (for internal review)\n"
        + SEP + "\n"
        + json.dumps(feedback_log, indent=2, ensure_ascii=False)
        + "\n"
    )

    full_content = header + feedback_text + raw_log_section

    with open(filename, "w", encoding="utf-8") as f:
        f.write(full_content)

    print(f"[Report saved to {filename}]")
    return filename
