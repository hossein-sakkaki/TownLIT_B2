# apps/journey_insights/question_bank/compassion.py

from apps.journey_insights.constants import ReflectionDimension
from apps.journey_insights.question_bank.schema import choice, question


D = ReflectionDimension


QUESTIONS = [
    question(
        code="compassion_notice_001",
        prompt="What helps you notice when someone may need care?",
        dimension=D.COMPASSION,
        secondary_dimensions=[D.CONNECTION, D.SELF_AWARENESS],
        metadata={"time_context": "general_pattern", "theme": "attention"},
        choices=[
            choice(
                code="changes_behavior",
                label="Small changes in their usual behavior",
                base_score=3.34,
                weights={D.COMPASSION: 1.04, D.CONNECTION: 0.82, D.SELF_AWARENESS: 0.48},
            ),
            choice(
                code="listen_between",
                label="Listening for what is difficult for them to say directly",
                base_score=3.49,
                weights={D.COMPASSION: 1.21, D.CONNECTION: 1.03, D.PEACE: 0.42},
            ),
            choice(
                code="practical_pressure",
                label="Noticing practical pressures that may be wearing them down",
                base_score=3.41,
                weights={D.COMPASSION: 1.12, D.PURPOSE: 0.66, D.CONNECTION: 0.63},
            ),
            choice(
                code="ask_not_assume",
                label="Asking a respectful question instead of assuming",
                base_score=3.53,
                weights={D.COMPASSION: 1.08, D.CONNECTION: 1.14, D.GROWTH: 0.54},
            ),
        ],
    ),
    question(
        code="compassion_help_002",
        prompt="What makes help respectful rather than controlling?",
        dimension=D.COMPASSION,
        secondary_dimensions=[D.CONNECTION, D.PURPOSE],
        difficulty=4,
        metadata={"time_context": "general_pattern", "theme": "healthy_help"},
        choices=[
            choice(
                code="ask_needed",
                label="Ask what would actually be useful before acting",
                base_score=3.55,
                weights={D.COMPASSION: 1.19, D.CONNECTION: 1.06, D.SELF_AWARENESS: 0.57},
            ),
            choice(
                code="preserve_choice",
                label="Preserve the other person's ability to make meaningful choices",
                base_score=3.58,
                weights={D.COMPASSION: 1.22, D.CONNECTION: 0.92, D.COURAGE: 0.48},
            ),
            choice(
                code="appropriate_limit",
                label="Offer what I can sustain rather than promise too much",
                base_score=3.49,
                weights={D.COMPASSION: 0.94, D.REST: 0.91, D.PURPOSE: 0.74},
            ),
            choice(
                code="without_display",
                label="Help without turning their need into my public story",
                base_score=3.61,
                weights={D.COMPASSION: 1.26, D.CONNECTION: 0.82, D.FAITH: 0.54},
            ),
        ],
    ),
    question(
        code="compassion_difficult_person_003",
        prompt="What can compassion look like toward someone whose behavior is difficult?",
        dimension=D.COMPASSION,
        secondary_dimensions=[D.PEACE, D.COURAGE],
        difficulty=5,
        sensitivity=2,
        metadata={"time_context": "general_pattern", "theme": "difficult_relationships"},
        choices=[
            choice(
                code="humanity_without_excuse",
                label="Recognize their humanity without excusing harmful behavior",
                base_score=3.57,
                weights={D.COMPASSION: 1.19, D.COURAGE: 0.84, D.SELF_AWARENESS: 0.65},
            ),
            choice(
                code="firm_boundary",
                label="Set a firm boundary without seeking humiliation or revenge",
                base_score=3.61,
                weights={D.COMPASSION: 0.98, D.COURAGE: 1.18, D.PEACE: 0.74},
            ),
            choice(
                code="truthful_consequence",
                label="Allow truthful consequences rather than rescuing them from every result",
                base_score=3.53,
                weights={D.COMPASSION: 0.91, D.COURAGE: 1.04, D.PURPOSE: 0.68},
            ),
            choice(
                code="release_hatred",
                label="Refuse to let their behavior shape me into hatred",
                base_score=3.59,
                weights={D.COMPASSION: 1.03, D.PEACE: 1.13, D.RESILIENCE: 0.72},
            ),
        ],
    ),
    question(
        code="compassion_self_004",
        prompt="What would responsible compassion toward yourself look like?",
        dimension=D.COMPASSION,
        secondary_dimensions=[D.REST, D.SELF_AWARENESS],
        difficulty=3,
        metadata={"time_context": "current_season", "theme": "self_compassion"},
        choices=[
            choice(
                code="honest_limit",
                label="Acknowledge a real limit without turning it into an excuse",
                base_score=3.48,
                weights={D.COMPASSION: 0.94, D.SELF_AWARENESS: 1.08, D.REST: 0.76},
            ),
            choice(
                code="support_earlier",
                label="Seek support before the situation becomes overwhelming",
                base_score=3.52,
                weights={D.COMPASSION: 0.97, D.CONNECTION: 1.04, D.COURAGE: 0.68},
            ),
            choice(
                code="rest_without_shame",
                label="Receive needed rest without treating it as moral failure",
                base_score=3.55,
                weights={D.COMPASSION: 1.06, D.REST: 1.21, D.PEACE: 0.61},
            ),
            choice(
                code="correct_without_contempt",
                label="Correct my course without speaking to myself with contempt",
                base_score=3.58,
                weights={D.COMPASSION: 1.14, D.GROWTH: 0.93, D.SELF_AWARENESS: 0.72},
            ),
        ],
    ),
    question(
        code="compassion_action_005",
        prompt="Which compassionate action could remain meaningful even if no one noticed it?",
        dimension=D.COMPASSION,
        secondary_dimensions=[D.PURPOSE, D.FAITH],
        metadata={"time_context": "forward", "theme": "hidden_service"},
        choices=[
            choice(
                code="private_encouragement",
                label="Send a private word of encouragement",
                base_score=3.44,
                weights={D.COMPASSION: 1.12, D.CONNECTION: 0.91, D.HOPE: 0.63},
            ),
            choice(
                code="reduce_burden",
                label="Quietly reduce a practical burden for someone",
                base_score=3.51,
                weights={D.COMPASSION: 1.18, D.PURPOSE: 0.92, D.CONNECTION: 0.54},
            ),
            choice(
                code="patient_response",
                label="Respond patiently to someone who is under pressure",
                base_score=3.49,
                weights={D.COMPASSION: 1.14, D.PEACE: 0.83, D.RESILIENCE: 0.46},
            ),
            choice(
                code="pray_for_person",
                label="Pray faithfully for someone without needing to announce it",
                base_score=3.55,
                weights={D.COMPASSION: 1.02, D.FAITH: 1.17, D.HOPE: 0.56},
            ),
        ],
    ),
]


QUESTIONS += [
    question(
        code="compassion_hidden_pain_006",
        prompt="How can you respond when someone may be carrying pain they have not explained?",
        dimension=D.COMPASSION,
        secondary_dimensions=[D.CONNECTION, D.PEACE],
        difficulty=4,
        sensitivity=3,
        metadata={"time_context": "general_pattern", "theme": "hidden_pain"},
        choices=[
            choice(
                code="gentle_invitation",
                label="Offer a gentle invitation without demanding disclosure",
                base_score=3.59,
                weights={D.COMPASSION: 1.24, D.CONNECTION: 1.03, D.PEACE: 0.72},
            ),
            choice(
                code="consistent_kindness",
                label="Remain consistently kind even if they are not ready to explain",
                base_score=3.56,
                weights={D.COMPASSION: 1.19, D.RESILIENCE: 0.78, D.CONNECTION: 0.67},
            ),
            choice(
                code="practical_offer",
                label="Offer a specific form of practical support they can accept or decline",
                base_score=3.54,
                weights={D.COMPASSION: 1.16, D.PURPOSE: 0.86, D.CONNECTION: 0.71},
            ),
            choice(
                code="respect_privacy",
                label="Respect their privacy while keeping the relationship open",
                base_score=3.61,
                weights={D.COMPASSION: 1.21, D.CONNECTION: 1.07, D.PEACE: 0.78},
            ),
        ],
    ),
    question(
        code="compassion_self_wound_007",
        prompt="What would it mean to treat a wounded part of yourself with compassion?",
        dimension=D.COMPASSION,
        secondary_dimensions=[D.SELF_AWARENESS, D.PEACE],
        difficulty=5,
        sensitivity=5,
        allow_for_new_users=False,
        minimum_journey_entries=8,
        metadata={"time_context": "healing", "theme": "inner_wound"},
        choices=[
            choice(
                code="listen_without_mocking",
                label="Listen to what the pain is revealing without mocking or dismissing it",
                base_score=3.63,
                weights={D.COMPASSION: 1.26, D.SELF_AWARENESS: 1.18, D.PEACE: 0.68},
            ),
            choice(
                code="separate_wound_identity",
                label="Recognize that the wound affects me without becoming my whole identity",
                base_score=3.66,
                weights={D.COMPASSION: 1.14, D.RESILIENCE: 1.17, D.HOPE: 0.83},
            ),
            choice(
                code="seek_appropriate_care",
                label="Seek appropriate care instead of expecting time alone to repair everything",
                base_score=3.68,
                weights={D.COMPASSION: 1.21, D.CONNECTION: 1.08, D.COURAGE: 0.91},
            ),
            choice(
                code="stop_repeating_harm",
                label="Stop repeating the harmful message the wound taught me",
                base_score=3.65,
                weights={D.COMPASSION: 1.18, D.GROWTH: 1.13, D.COURAGE: 0.82},
            ),
        ],
    ),
    question(
        code="compassion_strength_008",
        prompt="Which compassionate strength do you most naturally bring to others?",
        dimension=D.COMPASSION,
        secondary_dimensions=[D.CONNECTION, D.GRATITUDE],
        metadata={"time_context": "self_reflection", "theme": "compassion_strength"},
        choices=[
            choice(
                code="notice_quiet_needs",
                label="I notice needs that are not expressed loudly",
                base_score=3.49,
                weights={D.COMPASSION: 1.17, D.CONNECTION: 0.91, D.SELF_AWARENESS: 0.54},
            ),
            choice(
                code="remain_present",
                label="I can remain present when another person's pain is uncomfortable",
                base_score=3.57,
                weights={D.COMPASSION: 1.23, D.RESILIENCE: 0.91, D.CONNECTION: 0.76},
            ),
            choice(
                code="practical_care",
                label="I turn concern into practical and responsible care",
                base_score=3.54,
                weights={D.COMPASSION: 1.21, D.PURPOSE: 0.96, D.CONNECTION: 0.62},
            ),
            choice(
                code="protect_dignity",
                label="I try to protect another person's dignity while helping",
                base_score=3.61,
                weights={D.COMPASSION: 1.27, D.CONNECTION: 0.98, D.COURAGE: 0.52},
            ),
        ],
    ),
    question(
        code="compassion_exhaustion_009",
        prompt="How can compassion remain healthy when you feel emotionally tired?",
        dimension=D.COMPASSION,
        secondary_dimensions=[D.REST, D.SELF_AWARENESS],
        difficulty=4,
        metadata={"time_context": "tired_season", "theme": "compassion_fatigue"},
        choices=[
            choice(
                code="offer_specific_limit",
                label="Offer one specific form of care rather than unlimited availability",
                base_score=3.58,
                weights={D.COMPASSION: 1.09, D.REST: 1.02, D.PURPOSE: 0.81},
            ),
            choice(
                code="share_care",
                label="Invite others to share responsibility for the care needed",
                base_score=3.61,
                weights={D.COMPASSION: 1.13, D.CONNECTION: 1.16, D.REST: 0.72},
            ),
            choice(
                code="rest_without_abandoning",
                label="Take needed rest without interpreting it as abandonment",
                base_score=3.63,
                weights={D.COMPASSION: 1.06, D.REST: 1.24, D.PEACE: 0.81},
            ),
            choice(
                code="recognize_capacity",
                label="Recognize when another kind of support is more appropriate than mine",
                base_score=3.59,
                weights={D.COMPASSION: 1.14, D.SELF_AWARENESS: 1.06, D.GROWTH: 0.68},
            ),
        ],
    ),
    question(
        code="compassion_truth_010",
        prompt="When can compassion require saying something difficult?",
        dimension=D.COMPASSION,
        secondary_dimensions=[D.COURAGE, D.CONNECTION],
        difficulty=5,
        metadata={"time_context": "difficult_relationship", "theme": "compassionate_truth"},
        choices=[
            choice(
                code="harm_continues",
                label="When silence allows preventable harm to continue",
                base_score=3.64,
                weights={D.COMPASSION: 1.17, D.COURAGE: 1.23, D.PURPOSE: 0.72},
            ),
            choice(
                code="pattern_denied",
                label="When a destructive pattern is repeatedly denied",
                base_score=3.61,
                weights={D.COMPASSION: 1.08, D.COURAGE: 1.19, D.GROWTH: 0.79},
            ),
            choice(
                code="boundary_unclear",
                label="When an unclear boundary is creating greater confusion",
                base_score=3.59,
                weights={D.COMPASSION: 1.03, D.COURAGE: 1.11, D.PEACE: 0.84},
            ),
            choice(
                code="truth_serves_restoration",
                label="When the truth can serve protection, repentance, or restoration",
                base_score=3.67,
                weights={D.COMPASSION: 1.22, D.COURAGE: 1.16, D.HOPE: 0.73},
            ),
        ],
    ),
]