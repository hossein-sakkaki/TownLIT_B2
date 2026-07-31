# apps/journey_insights/question_bank/purpose.py

from apps.journey_insights.constants import ReflectionDimension
from apps.journey_insights.question_bank.schema import choice, question


D = ReflectionDimension


QUESTIONS = [
    question(
        code="purpose_priority_001",
        prompt="What would make the next part of your day feel meaningfully used?",
        dimension=D.PURPOSE,
        secondary_dimensions=[D.PEACE, D.GROWTH],
        metadata={"time_context": "forward", "theme": "priority"},
        choices=[
            choice(
                code="complete_needed_task",
                label="Complete one necessary task with care",
                base_score=3.34,
                weights={D.PURPOSE: 1.08, D.GROWTH: 0.57, D.PEACE: 0.46},
            ),
            choice(
                code="serve_person",
                label="Give thoughtful attention to someone who needs it",
                base_score=3.49,
                weights={D.PURPOSE: 0.92, D.COMPASSION: 1.13, D.CONNECTION: 0.78},
            ),
            choice(
                code="make_space",
                label="Create space to recover before taking on more",
                base_score=3.38,
                weights={D.PURPOSE: 0.63, D.REST: 1.14, D.SELF_AWARENESS: 0.69},
            ),
            choice(
                code="clarify_direction",
                label="Clarify what deserves attention before acting",
                base_score=3.43,
                weights={D.PURPOSE: 1.15, D.SELF_AWARENESS: 0.86, D.PEACE: 0.52},
            ),
        ],
    ),
    question(
        code="purpose_alignment_002",
        prompt="Which sign most suggests that a commitment is aligned with your deeper values?",
        dimension=D.PURPOSE,
        secondary_dimensions=[D.FAITH, D.PEACE],
        difficulty=3,
        metadata={"time_context": "general_pattern", "theme": "alignment"},
        choices=[
            choice(
                code="good_beyond_self",
                label="It contributes to something good beyond my own recognition",
                base_score=3.51,
                weights={D.PURPOSE: 1.22, D.COMPASSION: 0.82, D.FAITH: 0.54},
            ),
            choice(
                code="responsible_peace",
                label="It brings a responsible sense of peace, even when demanding",
                base_score=3.47,
                weights={D.PURPOSE: 1.02, D.PEACE: 0.96, D.RESILIENCE: 0.57},
            ),
            choice(
                code="consistent_character",
                label="It encourages the kind of character I want to practice",
                base_score=3.49,
                weights={D.PURPOSE: 1.12, D.GROWTH: 1.03, D.SELF_AWARENESS: 0.58},
            ),
            choice(
                code="wise_confirmation",
                label="Trusted people can recognize its value as well",
                base_score=3.38,
                weights={D.PURPOSE: 0.91, D.CONNECTION: 0.82, D.GROWTH: 0.63},
            ),
        ],
    ),
    question(
        code="purpose_competing_good_003",
        prompt="When several good responsibilities compete, what helps you choose?",
        dimension=D.PURPOSE,
        secondary_dimensions=[D.SELF_AWARENESS, D.COURAGE],
        difficulty=4,
        metadata={"time_context": "general_pattern", "theme": "discernment"},
        choices=[
            choice(
                code="current_responsibility",
                label="Identify what is truly mine to carry in this season",
                base_score=3.48,
                weights={D.PURPOSE: 1.18, D.SELF_AWARENESS: 0.96, D.PEACE: 0.62},
            ),
            choice(
                code="consequence_delay",
                label="Consider what will be harmed most if it is delayed",
                base_score=3.36,
                weights={D.PURPOSE: 1.08, D.COURAGE: 0.62, D.CONNECTION: 0.42},
            ),
            choice(
                code="seek_counsel",
                label="Seek counsel from someone who understands the larger context",
                base_score=3.42,
                weights={D.PURPOSE: 0.94, D.CONNECTION: 0.91, D.GROWTH: 0.67},
            ),
            choice(
                code="accept_tradeoff",
                label="Choose deliberately and accept that another good thing may wait",
                base_score=3.52,
                weights={D.PURPOSE: 1.21, D.COURAGE: 0.86, D.PEACE: 0.58},
            ),
        ],
    ),
    question(
        code="purpose_hidden_work_004",
        prompt="What gives value to work that few people notice?",
        dimension=D.PURPOSE,
        secondary_dimensions=[D.FAITH, D.GRATITUDE],
        metadata={"time_context": "general_pattern", "theme": "hidden_work"},
        choices=[
            choice(
                code="faithful_quality",
                label="The care and integrity with which it is done",
                base_score=3.54,
                weights={D.PURPOSE: 1.14, D.FAITH: 0.76, D.GROWTH: 0.64},
            ),
            choice(
                code="future_support",
                label="The way it quietly supports someone else's future",
                base_score=3.47,
                weights={D.PURPOSE: 1.04, D.COMPASSION: 0.96, D.HOPE: 0.58},
            ),
            choice(
                code="formed_character",
                label="The character being formed through consistent responsibility",
                base_score=3.51,
                weights={D.PURPOSE: 1.09, D.GROWTH: 1.02, D.RESILIENCE: 0.61},
            ),
            choice(
                code="received_stewardship",
                label="The opportunity to use what I have been given responsibly",
                base_score=3.49,
                weights={D.PURPOSE: 1.16, D.GRATITUDE: 0.76, D.FAITH: 0.58},
            ),
        ],
    ),
    question(
        code="purpose_release_005",
        prompt="Which kind of activity may need less space in your life?",
        dimension=D.PURPOSE,
        secondary_dimensions=[D.REST, D.SELF_AWARENESS],
        difficulty=3,
        metadata={"time_context": "season", "theme": "release"},
        choices=[
            choice(
                code="automatic_commitment",
                label="A commitment I continue mainly because it has become automatic",
                base_score=3.12,
                weights={D.PURPOSE: 0.52, D.SELF_AWARENESS: 0.98, D.COURAGE: 0.44},
            ),
            choice(
                code="approval_work",
                label="Work driven mainly by the need to prove my value",
                base_score=3.08,
                weights={D.PURPOSE: 0.48, D.SELF_AWARENESS: 1.09, D.REST: 0.42},
            ),
            choice(
                code="constant_reaction",
                label="Responding to every request as if it were equally urgent",
                base_score=3.04,
                weights={D.PURPOSE: 0.42, D.REST: 0.76, D.SELF_AWARENESS: 0.84},
            ),
            choice(
                code="low_value_distraction",
                label="A distraction that repeatedly takes energy from what matters",
                base_score=3.15,
                weights={D.PURPOSE: 0.74, D.GROWTH: 0.62, D.SELF_AWARENESS: 0.73},
            ),
        ],
    ),
]


QUESTIONS += [
    question(
        code="purpose_inner_drive_006",
        prompt="Which inner drive most often shapes the way you pursue responsibilities?",
        dimension=D.PURPOSE,
        secondary_dimensions=[D.SELF_AWARENESS, D.GROWTH],
        difficulty=4,
        metadata={"time_context": "general_pattern", "theme": "inner_drive"},
        choices=[
            choice(
                code="desire_contribute",
                label="A desire to contribute something genuinely useful",
                base_score=3.49,
                weights={D.PURPOSE: 1.18, D.COMPASSION: 0.86, D.GROWTH: 0.54},
            ),
            choice(
                code="desire_prove",
                label="A desire to prove that I am capable or valuable",
                base_score=3.08,
                weights={D.PURPOSE: 0.48, D.SELF_AWARENESS: 1.12, D.GROWTH: 0.42},
            ),
            choice(
                code="fear_disappoint",
                label="A fear of disappointing people who depend on me",
                base_score=3.12,
                weights={D.PURPOSE: 0.56, D.CONNECTION: 0.53, D.SELF_AWARENESS: 1.01},
            ),
            choice(
                code="sense_calling",
                label="A sense that the responsibility belongs to my present calling",
                base_score=3.54,
                weights={D.PURPOSE: 1.22, D.FAITH: 0.91, D.PEACE: 0.58},
            ),
        ],
    ),
    question(
        code="purpose_lost_direction_007",
        prompt="When you lose a sense of direction, what is the most helpful place to begin?",
        dimension=D.PURPOSE,
        secondary_dimensions=[D.PEACE, D.GROWTH],
        difficulty=3,
        metadata={"time_context": "uncertain_season", "theme": "lost_direction"},
        choices=[
            choice(
                code="current_responsibility",
                label="Return to the responsibility that is already clear",
                base_score=3.47,
                weights={D.PURPOSE: 1.14, D.RESILIENCE: 0.71, D.PEACE: 0.64},
            ),
            choice(
                code="review_values",
                label="Review the values I want my choices to reflect",
                base_score=3.52,
                weights={D.PURPOSE: 1.21, D.SELF_AWARENESS: 1.04, D.GROWTH: 0.59},
            ),
            choice(
                code="seek_counsel",
                label="Invite wise counsel from someone who knows me well",
                base_score=3.48,
                weights={D.PURPOSE: 1.01, D.CONNECTION: 1.06, D.GROWTH: 0.72},
            ),
            choice(
                code="rest_before_decision",
                label="Create enough rest and space to think without panic",
                base_score=3.49,
                weights={D.PURPOSE: 0.86, D.REST: 1.13, D.PEACE: 0.92},
            ),
        ],
    ),
    question(
        code="purpose_unused_strength_008",
        prompt="Which strength may be underused in your present responsibilities?",
        dimension=D.PURPOSE,
        secondary_dimensions=[D.GROWTH, D.COURAGE],
        metadata={"time_context": "current_season", "theme": "underused_strength"},
        choices=[
            choice(
                code="creative_thinking",
                label="My ability to imagine a different approach",
                base_score=3.43,
                weights={D.PURPOSE: 1.02, D.GROWTH: 1.11, D.COURAGE: 0.61},
            ),
            choice(
                code="patient_listening",
                label="My ability to listen before deciding",
                base_score=3.49,
                weights={D.PURPOSE: 0.91, D.CONNECTION: 1.08, D.COMPASSION: 0.84},
            ),
            choice(
                code="clear_organization",
                label="My ability to bring clarity and order",
                base_score=3.45,
                weights={D.PURPOSE: 1.17, D.GROWTH: 0.73, D.PEACE: 0.54},
            ),
            choice(
                code="courage_to_challenge",
                label="My ability to question a pattern that no longer serves the good",
                base_score=3.52,
                weights={D.PURPOSE: 1.14, D.COURAGE: 1.18, D.GROWTH: 0.62},
            ),
        ],
    ),
    question(
        code="purpose_pain_009",
        prompt="How can pain inform your purpose without being allowed to define it completely?",
        dimension=D.PURPOSE,
        secondary_dimensions=[D.RESILIENCE, D.COMPASSION],
        difficulty=5,
        sensitivity=4,
        allow_for_new_users=False,
        minimum_journey_entries=8,
        metadata={"time_context": "life_story", "theme": "pain_and_purpose"},
        choices=[
            choice(
                code="deeper_empathy",
                label="Let it deepen empathy for others with similar struggles",
                base_score=3.59,
                weights={D.PURPOSE: 1.04, D.COMPASSION: 1.24, D.RESILIENCE: 0.68},
            ),
            choice(
                code="clarify_values",
                label="Let it clarify what I now understand to be important",
                base_score=3.61,
                weights={D.PURPOSE: 1.18, D.SELF_AWARENESS: 1.07, D.GROWTH: 0.74},
            ),
            choice(
                code="protect_from_repeat",
                label="Let it guide healthier boundaries or responsible change",
                base_score=3.62,
                weights={D.PURPOSE: 1.13, D.COURAGE: 1.11, D.RESILIENCE: 0.83},
            ),
            choice(
                code="not_owe_meaning",
                label="Accept that I do not have to turn every pain into a public mission",
                base_score=3.64,
                weights={D.PURPOSE: 0.94, D.REST: 1.06, D.SELF_AWARENESS: 1.02},
            ),
        ],
    ),
    question(
        code="purpose_future_self_010",
        prompt="What would you like your future self to thank you for beginning now?",
        dimension=D.PURPOSE,
        secondary_dimensions=[D.HOPE, D.GROWTH],
        metadata={"time_context": "forward", "theme": "future_investment"},
        choices=[
            choice(
                code="healthy_rhythm",
                label="A healthier rhythm of work, rest, and attention",
                base_score=3.54,
                weights={D.PURPOSE: 1.02, D.REST: 1.13, D.GROWTH: 0.72},
            ),
            choice(
                code="important_skill",
                label="A skill that will take time and consistent practice",
                base_score=3.49,
                weights={D.PURPOSE: 1.14, D.GROWTH: 1.18, D.RESILIENCE: 0.61},
            ),
            choice(
                code="honest_relationship",
                label="A more honest and dependable relationship",
                base_score=3.57,
                weights={D.PURPOSE: 0.98, D.CONNECTION: 1.19, D.COURAGE: 0.76},
            ),
            choice(
                code="unfinished_healing",
                label="Giving appropriate attention to healing I have postponed",
                base_score=3.59,
                weights={D.PURPOSE: 0.91, D.SELF_AWARENESS: 1.13, D.PEACE: 0.84},
            ),
        ],
    ),
]