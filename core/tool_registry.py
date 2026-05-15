from skills import run_skill_mcat, run_skill_content, run_skill_spec, run_skill_intent, run_skill_seller

SKILL_DISPATCHER = {
    "run_skill_mcat": run_skill_mcat,
    "run_skill_content": run_skill_content,
    "run_skill_spec": run_skill_spec,
    "run_skill_intent": run_skill_intent,
    "run_skill_seller": run_skill_seller,
}

TOOLS = [
    {
        "name": "run_skill_mcat",
        "description": "Diagnose MCAT category mismatch. Use when title/description suggest wrong category mapping or when is_mcat_changed or is_generic_mcat are true.",
        "input_schema": {
            "type": "object",
            "properties": {
                "eto_ofr_title": {"type": "string"},
                "eto_ofr_desc": {"type": "string"},
                "eto_ofr_mcat_id": {"type": "string"},
                "is_mcat_changed": {"type": "boolean"},
                "is_generic_mcat": {"type": "boolean"},
                "ni_reason_codes": {"type": "string"},
            },
            "required": ["eto_ofr_title"],
        },
    },
    {
        "name": "run_skill_content",
        "description": "Diagnose thin or missing content. Use when ISQ fill rate is low, title/desc are short, quality is L, or rag_score_total is low.",
        "input_schema": {
            "type": "object",
            "properties": {
                "eto_ofr_title": {"type": "string"},
                "eto_ofr_desc": {"type": "string"},
                "eto_ofr_quality": {"type": "string"},
                "rag_score_total": {"type": "number"},
                "isq_fill_rate": {"type": "number"},
                "title_word_count": {"type": "integer"},
                "desc_word_count": {"type": "integer"},
                "ofr_quantity": {"type": "string"},
                "ofr_unit": {"type": "string"},
            },
            "required": ["eto_ofr_title"],
        },
    },
    {
        "name": "run_skill_spec",
        "description": "Diagnose spec or logical contradictions in the BL. Use when title, description, category, or images seem inconsistent.",
        "input_schema": {
            "type": "object",
            "properties": {
                "eto_ofr_title": {"type": "string"},
                "eto_ofr_desc": {"type": "string"},
                "eto_ofr_mcat_id": {"type": "string"},
                "ni_reason_codes": {"type": "string"},
                "photo_mismatch_flag": {"type": "boolean"},
                "why_do_you_need_reason": {"type": "string"},
            },
            "required": ["eto_ofr_title"],
        },
    },
    {
        "name": "run_skill_intent",
        "description": "Score buyer intent based on posting behaviour signals. Use for all BLs — fully rule-based, no LLM cost.",
        "input_schema": {
            "type": "object",
            "properties": {
                "is_auto_generated": {"type": "boolean"},
                "is_guest_login": {"type": "boolean"},
                "is_call_verified": {"type": "boolean"},
                "is_late_night": {"type": "boolean"},
                "posting_hour": {"type": "integer"},
                "products_viewed_before_posting": {"type": "integer"},
                "user_identifier_flag": {"type": "integer"},
                "posting_platform": {"type": "string"},
                "glusr_usr_listing_status": {"type": "string"},
                "fcp_flag": {"type": "integer"},
            },
            "required": [],
        },
    },
    {
        "name": "run_skill_seller",
        "description": "Diagnose seller-side failures: NI overload, slow response, supply gap. Use when ni_count is high or time_to_first_response_hrs is large.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ni_count": {"type": "integer"},
                "sellers_received_count": {"type": "integer"},
                "time_to_first_response_hrs": {"type": "number"},
                "ni_reason_codes": {"type": "string"},
                "eto_ofr_title": {"type": "string"},
                "eto_ofr_geography_id": {"type": "string"},
            },
            "required": [],
        },
    },
]


def get_all_tools() -> list:
    return TOOLS


def execute_skill(tool_name: str, bl_context: dict) -> dict:
    fn = SKILL_DISPATCHER.get(tool_name)
    if fn is None:
        return {"error": f"Unknown skill: {tool_name}"}
    return fn(bl_context)
