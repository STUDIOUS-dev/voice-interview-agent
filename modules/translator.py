import json

import google.generativeai as genai


def translate_questions(
    questions: list,
    target_language: str,
    settings,
) -> list:
    
    if target_language == "English":
        return [
            {**q, "translated_question": q["question"]}
            for q in questions
        ]

    
    numbered_questions = "\n".join(
        f"{i + 1}. {q['question']}"
        for i, q in enumerate(questions)
    )

    prompt = (
        f"Translate the following interview questions to {target_language}.\n"
        f"Return ONLY a valid JSON array of strings in the same order as the input.\n"
        f"Preserve all technical terms in English (e.g. ORM, REST, API, Python, "
        f"decorator, generator, iterator, tuple, list).\n"
        f"Do not add any explanation, preamble, or markdown fencing.\n\n"
        f"Questions:\n{numbered_questions}"
    )

    try:
        model = genai.GenerativeModel(model_name=settings.llm_model)
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(temperature=0.3),
        )

        raw = response.text.strip()

        
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(
                line for line in lines
                if not line.startswith("```")
            ).strip()

        translated_list = json.loads(raw)

        
        if (
            not isinstance(translated_list, list)
            or len(translated_list) != len(questions)
            or not all(isinstance(t, str) for t in translated_list)
        ):
            raise ValueError(
                f"Unexpected translation structure: got {type(translated_list)} "
                f"with {len(translated_list) if isinstance(translated_list, list) else '?'} items"
            )

        
        result = [
            {**q, "translated_question": translated}
            for q, translated in zip(questions, translated_list)
        ]

        print(f"[Translation complete for {target_language}]")
        return result

    except (json.JSONDecodeError, ValueError, Exception) as e:
        
        print(f"[Translation failed ({e}). Falling back to English questions.]")
        return [
            {**q, "translated_question": q["question"]}
            for q in questions
        ]
