# apps/journey_insights/question_bank/peace.py

from apps.journey_insights.constants import ReflectionDimension
from apps.journey_insights.question_bank.schema import choice, question


D = ReflectionDimension


QUESTIONS = [
    question(
        code="peace_prepare_001",
        prompt="What would help you move through the next few hours with greater steadiness?",
        dimension=D.PEACE,
        secondary_dimensions=[D.REST, D.SELF_AWARENESS],
        is_brand_core=True,
        metadata={"time_context": "forward", "theme": "preparation"},
        choices=[
            choice(
                code="clear_priority",
                label="Choosing one clear priority instead of carrying everything at once",
                base_score=3.38,
                weights={D.PEACE: 1.02, D.PURPOSE: 0.86, D.REST: 0.54},
            ),
            choice(
                code="quiet_pause",
                label="Making room for silence, prayer, or reflection",
                base_score=3.44,
                weights={D.PEACE: 1.21, D.FAITH: 0.78, D.REST: 0.64},
            ),
            choice(
                code="support_contact",
                label="Letting someone know I may need support",
                base_score=3.31,
                weights={D.PEACE: 0.66, D.CONNECTION: 1.08, D.COURAGE: 0.61},
            ),
            choice(
                code="accept_uncertainty",
                label="Accepting that I may not resolve everything immediately",
                base_score=3.47,
                weights={D.PEACE: 1.16, D.RESILIENCE: 0.74, D.SELF_AWARENESS: 0.61},
            ),
        ],
    ),
    question(
        code="peace_tension_002",
        prompt="When tension rises, which signal do you usually notice first?",
        dimension=D.PEACE,
        secondary_dimensions=[D.SELF_AWARENESS, D.REST],
        difficulty=2,
        metadata={"time_context": "general_pattern", "theme": "signals"},
        choices=[
            choice(
                code="racing_thoughts",
                label="My thoughts begin moving faster",
                base_score=2.96,
                weights={D.PEACE: 0.34, D.SELF_AWARENESS: 1.12, D.REST: 0.42},
            ),
            choice(
                code="body_tension",
                label="My body becomes tight or restless",
                base_score=3.02,
                weights={D.PEACE: 0.31, D.SELF_AWARENESS: 1.18, D.REST: 0.56},
            ),
            choice(
                code="control_impulse",
                label="I feel an urge to control every detail",
                base_score=3.08,
                weights={D.PEACE: 0.24, D.SELF_AWARENESS: 1.09, D.RESILIENCE: 0.46},
            ),
            choice(
                code="withdraw_impulse",
                label="I want to step away from people or decisions",
                base_score=3.04,
                weights={D.PEACE: 0.28, D.SELF_AWARENESS: 1.03, D.CONNECTION: 0.32},
            ),
        ],
    ),
    question(
        code="peace_conflict_003",
        prompt="In a difficult conversation, what would peace most likely require from you?",
        dimension=D.PEACE,
        secondary_dimensions=[D.COURAGE, D.CONNECTION],
        difficulty=4,
        sensitivity=2,
        metadata={"time_context": "forward", "theme": "conflict"},
        choices=[
            choice(
                code="listen_longer",
                label="Listen longer before defending my position",
                base_score=3.46,
                weights={D.PEACE: 1.04, D.CONNECTION: 0.91, D.COMPASSION: 0.72},
            ),
            choice(
                code="speak_clearly",
                label="Say something truthful that I have been avoiding",
                base_score=3.43,
                weights={D.PEACE: 0.72, D.COURAGE: 1.18, D.CONNECTION: 0.64},
            ),
            choice(
                code="slow_timing",
                label="Wait until the timing allows both people to respond thoughtfully",
                base_score=3.35,
                weights={D.PEACE: 1.12, D.SELF_AWARENESS: 0.62, D.REST: 0.41},
            ),
            choice(
                code="accept_limit",
                label="Accept that reconciliation may require more than one conversation",
                base_score=3.49,
                weights={D.PEACE: 1.08, D.RESILIENCE: 0.88, D.HOPE: 0.52},
            ),
        ],
    ),
    question(
        code="peace_inner_space_004",
        prompt="What most often competes with your inner sense of peace?",
        dimension=D.PEACE,
        secondary_dimensions=[D.PURPOSE, D.SELF_AWARENESS],
        difficulty=2,
        metadata={"time_context": "general_pattern", "theme": "pressure"},
        choices=[
            choice(
                code="unfinished_tasks",
                label="The feeling that something important is still unfinished",
                base_score=2.93,
                weights={D.PEACE: 0.22, D.PURPOSE: 0.72, D.SELF_AWARENESS: 0.63},
            ),
            choice(
                code="others_expectations",
                label="Trying to meet expectations I have not examined",
                base_score=3.06,
                weights={D.PEACE: 0.28, D.SELF_AWARENESS: 1.06, D.COURAGE: 0.43},
            ),
            choice(
                code="unclear_future",
                label="Not knowing what the next step will bring",
                base_score=3.01,
                weights={D.PEACE: 0.24, D.HOPE: 0.62, D.FAITH: 0.48},
            ),
            choice(
                code="internal_replay",
                label="Replaying a past moment that I cannot change",
                base_score=2.98,
                weights={D.PEACE: 0.21, D.SELF_AWARENESS: 0.91, D.RESILIENCE: 0.46},
            ),
        ],
    ),
    question(
        code="peace_practice_005",
        prompt="Which practice would be most meaningful for you to protect this week?",
        dimension=D.PEACE,
        secondary_dimensions=[D.REST, D.FAITH],
        metadata={"time_context": "forward", "theme": "practice"},
        choices=[
            choice(
                code="unhurried_prayer",
                label="A brief but unhurried time of prayer or reflection",
                base_score=3.43,
                weights={D.PEACE: 1.14, D.FAITH: 0.96, D.REST: 0.58},
            ),
            choice(
                code="honest_boundary",
                label="A clear boundary around something that is draining me",
                base_score=3.39,
                weights={D.PEACE: 0.96, D.REST: 1.02, D.COURAGE: 0.62},
            ),
            choice(
                code="reliable_rhythm",
                label="A simple rhythm I can repeat without pressure",
                base_score=3.34,
                weights={D.PEACE: 1.03, D.GROWTH: 0.64, D.RESILIENCE: 0.51},
            ),
            choice(
                code="reconciling_step",
                label="One careful step toward repairing a strained relationship",
                base_score=3.47,
                weights={D.PEACE: 0.84, D.CONNECTION: 1.12, D.COURAGE: 0.72},
            ),
        ],
    ),
]


QUESTIONS += [
    question(
        code="peace_unspoken_weight_006",
        prompt="When something remains unspoken within you, what usually brings the most relief?",
        dimension=D.PEACE,
        secondary_dimensions=[D.SELF_AWARENESS, D.CONNECTION],
        difficulty=4,
        sensitivity=3,
        metadata={"time_context": "general_pattern", "theme": "unspoken_weight"},
        choices=[
            choice(
                code="name_privately",
                label="Name it honestly to myself before deciding what to do",
                base_score=3.42,
                weights={D.PEACE: 0.94, D.SELF_AWARENESS: 1.19, D.COURAGE: 0.51},
            ),
            choice(
                code="share_trusted_person",
                label="Share it with someone trustworthy who can listen carefully",
                base_score=3.51,
                weights={D.PEACE: 0.91, D.CONNECTION: 1.18, D.COURAGE: 0.64},
            ),
            choice(
                code="bring_to_prayer",
                label="Bring it honestly into prayer without needing immediate clarity",
                base_score=3.55,
                weights={D.PEACE: 1.16, D.FAITH: 1.12, D.SELF_AWARENESS: 0.58},
            ),
            choice(
                code="identify_next_action",
                label="Identify whether it requires action, acceptance, or more time",
                base_score=3.48,
                weights={D.PEACE: 1.07, D.PURPOSE: 0.91, D.GROWTH: 0.63},
            ),
        ],
    ),
    question(
        code="peace_old_pain_007",
        prompt="What helps you respond gently when an old pain is unexpectedly stirred?",
        dimension=D.PEACE,
        secondary_dimensions=[D.COMPASSION, D.RESILIENCE],
        difficulty=5,
        sensitivity=4,
        allow_for_new_users=False,
        minimum_journey_entries=5,
        metadata={"time_context": "triggered_memory", "theme": "old_pain"},
        choices=[
            choice(
                code="recognize_present",
                label="Remind myself that the present is not identical to the past",
                base_score=3.54,
                weights={D.PEACE: 1.13, D.RESILIENCE: 1.04, D.SELF_AWARENESS: 0.74},
            ),
            choice(
                code="slow_response",
                label="Slow my response until I understand what has been stirred",
                base_score=3.51,
                weights={D.PEACE: 1.21, D.SELF_AWARENESS: 1.02, D.COURAGE: 0.47},
            ),
            choice(
                code="seek_safe_support",
                label="Seek support from someone who respects the weight of the experience",
                base_score=3.57,
                weights={D.PEACE: 0.94, D.CONNECTION: 1.18, D.COMPASSION: 0.82},
            ),
            choice(
                code="allow_emotion_without_control",
                label="Allow the emotion to be real without letting it direct every decision",
                base_score=3.59,
                weights={D.PEACE: 1.16, D.SELF_AWARENESS: 1.08, D.RESILIENCE: 0.91},
            ),
        ],
    ),
    question(
        code="peace_control_008",
        prompt="Which kind of uncertainty most tempts you to seek too much control?",
        dimension=D.PEACE,
        secondary_dimensions=[D.SELF_AWARENESS, D.FAITH],
        difficulty=3,
        metadata={"time_context": "general_pattern", "theme": "control"},
        choices=[
            choice(
                code="relationship_uncertainty",
                label="Not knowing how another person will respond",
                base_score=3.07,
                weights={D.PEACE: 0.38, D.CONNECTION: 0.54, D.SELF_AWARENESS: 1.02},
            ),
            choice(
                code="future_security",
                label="Not knowing whether future needs will be met",
                base_score=3.11,
                weights={D.PEACE: 0.41, D.HOPE: 0.52, D.FAITH: 0.69},
            ),
            choice(
                code="performance_outcome",
                label="Not knowing whether my effort will succeed",
                base_score=3.04,
                weights={D.PEACE: 0.34, D.PURPOSE: 0.58, D.SELF_AWARENESS: 0.91},
            ),
            choice(
                code="health_change",
                label="Not knowing how a physical or emotional concern may develop",
                base_score=3.09,
                weights={D.PEACE: 0.36, D.RESILIENCE: 0.62, D.SELF_AWARENESS: 0.86},
            ),
        ],
    ),
    question(
        code="peace_forgiveness_009",
        prompt="What can peace require when forgiveness and trust are not the same thing?",
        dimension=D.PEACE,
        secondary_dimensions=[D.COMPASSION, D.COURAGE],
        difficulty=5,
        sensitivity=4,
        metadata={"time_context": "relationship_reflection", "theme": "forgiveness_and_trust"},
        choices=[
            choice(
                code="release_revenge",
                label="Release the desire for revenge without ignoring what happened",
                base_score=3.58,
                weights={D.PEACE: 1.14, D.COMPASSION: 0.91, D.RESILIENCE: 0.68},
            ),
            choice(
                code="rebuild_slowly",
                label="Allow trust to be rebuilt slowly through consistent evidence",
                base_score=3.61,
                weights={D.PEACE: 1.08, D.CONNECTION: 0.94, D.COURAGE: 0.79},
            ),
            choice(
                code="keep_boundary",
                label="Maintain a necessary boundary without feeding hatred",
                base_score=3.63,
                weights={D.PEACE: 1.17, D.COURAGE: 1.12, D.COMPASSION: 0.72},
            ),
            choice(
                code="accept_no_reconciliation",
                label="Accept that peace may not always include restored closeness",
                base_score=3.57,
                weights={D.PEACE: 1.21, D.SELF_AWARENESS: 0.82, D.RESILIENCE: 0.76},
            ),
        ],
    ),
    question(
        code="peace_inner_dialogue_010",
        prompt="Which change in your inner dialogue would create more peace?",
        dimension=D.PEACE,
        secondary_dimensions=[D.SELF_AWARENESS, D.COMPASSION],
        metadata={"time_context": "forward", "theme": "inner_dialogue"},
        choices=[
            choice(
                code="from_perfect_to_faithful",
                label="Replace “I must do this perfectly” with “I can act faithfully and learn”",
                base_score=3.54,
                weights={D.PEACE: 1.13, D.GROWTH: 1.07, D.SELF_AWARENESS: 0.72},
            ),
            choice(
                code="from_alone_to_support",
                label="Replace “I must carry this alone” with “I can seek appropriate support”",
                base_score=3.57,
                weights={D.PEACE: 1.06, D.CONNECTION: 1.16, D.COURAGE: 0.63},
            ),
            choice(
                code="from_failure_to_information",
                label="Replace “This proves I failed” with “This gives me information”",
                base_score=3.52,
                weights={D.PEACE: 1.02, D.GROWTH: 1.14, D.RESILIENCE: 0.83},
            ),
            choice(
                code="from_urgency_to_discernment",
                label="Replace “Everything is urgent” with “I can discern the next responsibility”",
                base_score=3.59,
                weights={D.PEACE: 1.19, D.PURPOSE: 1.04, D.REST: 0.68},
            ),
        ],
    ),
]