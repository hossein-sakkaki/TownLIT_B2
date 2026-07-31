# apps/journey_insights/question_bank/courage.py

from apps.journey_insights.constants import ReflectionDimension
from apps.journey_insights.question_bank.schema import choice, question


D = ReflectionDimension


QUESTIONS = [
    question(
        code="courage_next_step_001",
        prompt="Which kind of courage is most relevant to your next step?",
        dimension=D.COURAGE,
        secondary_dimensions=[D.PURPOSE, D.CONNECTION],
        metadata={"time_context": "forward", "theme": "next_step"},
        choices=[
            choice(
                code="begin_imperfectly",
                label="Begin before I feel completely ready",
                base_score=3.42,
                weights={D.COURAGE: 1.18, D.GROWTH: 0.83, D.PURPOSE: 0.62},
            ),
            choice(
                code="speak_truthfully",
                label="Speak truthfully while remaining respectful",
                base_score=3.51,
                weights={D.COURAGE: 1.22, D.CONNECTION: 0.86, D.COMPASSION: 0.51},
            ),
            choice(
                code="ask_help",
                label="Ask for help instead of hiding the difficulty",
                base_score=3.47,
                weights={D.COURAGE: 1.03, D.CONNECTION: 1.02, D.SELF_AWARENESS: 0.71},
            ),
            choice(
                code="stop_unhealthy",
                label="Stop something that is no longer healthy or responsible",
                base_score=3.49,
                weights={D.COURAGE: 1.17, D.PEACE: 0.72, D.SELF_AWARENESS: 0.84},
            ),
        ],
    ),
    question(
        code="courage_fear_signal_002",
        prompt="What does fear most often ask you to do?",
        dimension=D.COURAGE,
        secondary_dimensions=[D.SELF_AWARENESS, D.RESILIENCE],
        difficulty=3,
        metadata={"time_context": "general_pattern", "theme": "fear"},
        choices=[
            choice(
                code="delay_indefinitely",
                label="Delay until certainty becomes impossible to achieve",
                base_score=3.01,
                weights={D.COURAGE: 0.32, D.SELF_AWARENESS: 0.96, D.PURPOSE: 0.37},
            ),
            choice(
                code="overprepare",
                label="Prepare beyond what the situation reasonably requires",
                base_score=3.09,
                weights={D.COURAGE: 0.41, D.SELF_AWARENESS: 0.91, D.RESILIENCE: 0.36},
            ),
            choice(
                code="protect_image",
                label="Protect how I appear rather than address what is true",
                base_score=3.04,
                weights={D.COURAGE: 0.35, D.SELF_AWARENESS: 1.03, D.CONNECTION: 0.31},
            ),
            choice(
                code="carry_alone",
                label="Carry the situation alone so no one sees my uncertainty",
                base_score=2.98,
                weights={D.COURAGE: 0.28, D.SELF_AWARENESS: 0.88, D.CONNECTION: 0.41},
            ),
        ],
    ),
    question(
        code="courage_wisdom_003",
        prompt="How can you distinguish courage from unnecessary risk?",
        dimension=D.COURAGE,
        secondary_dimensions=[D.PURPOSE, D.GROWTH],
        difficulty=4,
        metadata={"time_context": "general_pattern", "theme": "discernment"},
        choices=[
            choice(
                code="clear_good",
                label="The risk serves a clear good rather than excitement alone",
                base_score=3.49,
                weights={D.COURAGE: 1.03, D.PURPOSE: 1.16, D.SELF_AWARENESS: 0.54},
            ),
            choice(
                code="count_cost",
                label="I have considered the likely cost to myself and others",
                base_score=3.52,
                weights={D.COURAGE: 0.98, D.COMPASSION: 0.77, D.PURPOSE: 0.94},
            ),
            choice(
                code="wise_input",
                label="Wise people can question the plan without being dismissed",
                base_score=3.46,
                weights={D.COURAGE: 0.86, D.GROWTH: 1.03, D.CONNECTION: 0.71},
            ),
            choice(
                code="accept_revision",
                label="I remain willing to revise the action as new information appears",
                base_score=3.48,
                weights={D.COURAGE: 0.92, D.GROWTH: 1.12, D.SELF_AWARENESS: 0.66},
            ),
        ],
    ),
    question(
        code="courage_failure_004",
        prompt="What response to failure requires the most courage from you?",
        dimension=D.COURAGE,
        secondary_dimensions=[D.RESILIENCE, D.GROWTH],
        difficulty=4,
        metadata={"time_context": "general_pattern", "theme": "failure"},
        choices=[
            choice(
                code="name_failure",
                label="Name what went wrong without reshaping the story",
                base_score=3.51,
                weights={D.COURAGE: 1.17, D.SELF_AWARENESS: 1.02, D.GROWTH: 0.62},
            ),
            choice(
                code="repair_damage",
                label="Repair harm even when my intentions were good",
                base_score=3.58,
                weights={D.COURAGE: 1.22, D.COMPASSION: 1.01, D.CONNECTION: 0.72},
            ),
            choice(
                code="learn_continue",
                label="Learn from it without allowing it to define my identity",
                base_score=3.55,
                weights={D.COURAGE: 1.02, D.RESILIENCE: 1.16, D.GROWTH: 0.82},
            ),
            choice(
                code="receive_grace",
                label="Receive forgiveness or kindness without continuing to punish myself",
                base_score=3.53,
                weights={D.COURAGE: 0.91, D.PEACE: 1.04, D.FAITH: 0.69},
            ),
        ],
    ),
    question(
        code="courage_quiet_005",
        prompt="Which quiet form of courage is easiest to underestimate?",
        dimension=D.COURAGE,
        secondary_dimensions=[D.RESILIENCE, D.COMPASSION],
        metadata={"time_context": "general_pattern", "theme": "quiet_courage"},
        choices=[
            choice(
                code="daily_return",
                label="Returning to a responsibility after a discouraging day",
                base_score=3.46,
                weights={D.COURAGE: 0.96, D.RESILIENCE: 1.16, D.PURPOSE: 0.71},
            ),
            choice(
                code="gentle_answer",
                label="Choosing a gentle answer when a harsh one would feel easier",
                base_score=3.54,
                weights={D.COURAGE: 0.89, D.COMPASSION: 1.18, D.PEACE: 0.74},
            ),
            choice(
                code="admit_limit",
                label="Admitting a limit before exhaustion makes the decision for me",
                base_score=3.49,
                weights={D.COURAGE: 1.08, D.REST: 1.06, D.SELF_AWARENESS: 0.76},
            ),
            choice(
                code="remain_teachable",
                label="Remaining teachable when I would rather protect my pride",
                base_score=3.52,
                weights={D.COURAGE: 0.98, D.GROWTH: 1.19, D.SELF_AWARENESS: 0.72},
            ),
        ],
    ),
]


QUESTIONS += [
    question(
        code="courage_hidden_fear_006",
        prompt="Which fear is easiest to hide behind responsible-looking behavior?",
        dimension=D.COURAGE,
        secondary_dimensions=[D.SELF_AWARENESS, D.PURPOSE],
        difficulty=4,
        metadata={"time_context": "general_pattern", "theme": "hidden_fear"},
        choices=[
            choice(
                code="perfection_preparation",
                label="Fear of failure hidden behind endless preparation",
                base_score=3.08,
                weights={D.COURAGE: 0.46, D.SELF_AWARENESS: 1.17, D.GROWTH: 0.42},
            ),
            choice(
                code="overcommitment_rejection",
                label="Fear of rejection hidden behind saying yes to everything",
                base_score=3.05,
                weights={D.COURAGE: 0.41, D.CONNECTION: 0.53, D.SELF_AWARENESS: 1.09},
            ),
            choice(
                code="control_care",
                label="Fear of uncertainty hidden behind trying to manage everyone",
                base_score=3.11,
                weights={D.COURAGE: 0.43, D.SELF_AWARENESS: 1.14, D.PEACE: 0.36},
            ),
            choice(
                code="silence_peace",
                label="Fear of conflict hidden behind calling silence peace",
                base_score=3.07,
                weights={D.COURAGE: 0.51, D.PEACE: 0.42, D.SELF_AWARENESS: 1.06},
            ),
        ],
    ),
    question(
        code="courage_wound_voice_007",
        prompt="When a painful experience has made your voice smaller, what could courage look like?",
        dimension=D.COURAGE,
        secondary_dimensions=[D.RESILIENCE, D.CONNECTION],
        difficulty=5,
        sensitivity=5,
        allow_for_new_users=False,
        minimum_journey_entries=8,
        metadata={"time_context": "healing", "theme": "recovering_voice"},
        choices=[
            choice(
                code="name_truth_safe_place",
                label="Name the truth first in a safe and trustworthy place",
                base_score=3.62,
                weights={D.COURAGE: 1.24, D.CONNECTION: 1.09, D.SELF_AWARENESS: 0.82},
            ),
            choice(
                code="practice_small_preference",
                label="Practice expressing smaller preferences and limits",
                base_score=3.57,
                weights={D.COURAGE: 1.17, D.GROWTH: 0.98, D.PEACE: 0.61},
            ),
            choice(
                code="refuse_false_blame",
                label="Refuse responsibility for harm that was not mine to carry",
                base_score=3.66,
                weights={D.COURAGE: 1.27, D.RESILIENCE: 1.04, D.SELF_AWARENESS: 0.91},
            ),
            choice(
                code="accept_support_speaking",
                label="Allow someone supportive to stand with me while I speak",
                base_score=3.61,
                weights={D.COURAGE: 1.13, D.CONNECTION: 1.18, D.RESILIENCE: 0.72},
            ),
        ],
    ),
    question(
        code="courage_strength_008",
        prompt="Which form of courage already appears in your life more than you usually recognize?",
        dimension=D.COURAGE,
        secondary_dimensions=[D.GRATITUDE, D.RESILIENCE],
        metadata={"time_context": "self_reflection", "theme": "existing_courage"},
        choices=[
            choice(
                code="showing_up",
                label="Continuing to show up during a difficult season",
                base_score=3.51,
                weights={D.COURAGE: 1.08, D.RESILIENCE: 1.17, D.GRATITUDE: 0.62},
            ),
            choice(
                code="admitting_unknown",
                label="Admitting when I do not know or understand",
                base_score=3.49,
                weights={D.COURAGE: 1.13, D.GROWTH: 0.98, D.SELF_AWARENESS: 0.72},
            ),
            choice(
                code="protecting_without_harming",
                label="Protecting a necessary boundary without trying to harm another person",
                base_score=3.57,
                weights={D.COURAGE: 1.21, D.COMPASSION: 0.91, D.PEACE: 0.72},
            ),
            choice(
                code="trying_after_failure",
                label="Trying again after a result that disappointed me",
                base_score=3.55,
                weights={D.COURAGE: 1.16, D.RESILIENCE: 1.14, D.HOPE: 0.64},
            ),
        ],
    ),
    question(
        code="courage_truth_cost_009",
        prompt="When truth may carry a cost, what helps you speak responsibly?",
        dimension=D.COURAGE,
        secondary_dimensions=[D.COMPASSION, D.PURPOSE],
        difficulty=5,
        metadata={"time_context": "difficult_conversation", "theme": "costly_truth"},
        choices=[
            choice(
                code="check_motive",
                label="Examine whether my motive is repair, protection, or self-display",
                base_score=3.58,
                weights={D.COURAGE: 1.04, D.SELF_AWARENESS: 1.14, D.PURPOSE: 0.81},
            ),
            choice(
                code="choose_accurate_words",
                label="Use accurate words rather than the most emotionally powerful ones",
                base_score=3.61,
                weights={D.COURAGE: 1.16, D.PEACE: 0.91, D.COMPASSION: 0.72},
            ),
            choice(
                code="consider_vulnerable_people",
                label="Consider how the timing and method may affect vulnerable people",
                base_score=3.62,
                weights={D.COURAGE: 1.03, D.COMPASSION: 1.23, D.PURPOSE: 0.74},
            ),
            choice(
                code="accept_consequence",
                label="Accept that responsible truthfulness may still be misunderstood",
                base_score=3.64,
                weights={D.COURAGE: 1.27, D.RESILIENCE: 0.93, D.PEACE: 0.61},
            ),
        ],
    ),
    question(
        code="courage_next_boundary_010",
        prompt="Which boundary would require the most courage for you to communicate?",
        dimension=D.COURAGE,
        secondary_dimensions=[D.REST, D.CONNECTION],
        difficulty=4,
        sensitivity=3,
        metadata={"time_context": "forward", "theme": "boundary_expression"},
        choices=[
            choice(
                code="time_limit",
                label="A limit around my time or availability",
                base_score=3.43,
                weights={D.COURAGE: 1.08, D.REST: 1.04, D.PURPOSE: 0.58},
            ),
            choice(
                code="conversation_limit",
                label="A limit around how I am willing to be spoken to",
                base_score=3.56,
                weights={D.COURAGE: 1.23, D.CONNECTION: 0.78, D.PEACE: 0.71},
            ),
            choice(
                code="responsibility_limit",
                label="A limit around responsibility that does not belong only to me",
                base_score=3.51,
                weights={D.COURAGE: 1.17, D.PURPOSE: 0.91, D.REST: 0.76},
            ),
            choice(
                code="privacy_limit",
                label="A limit around personal information I am not ready to share",
                base_score=3.54,
                weights={D.COURAGE: 1.14, D.SELF_AWARENESS: 0.96, D.PEACE: 0.68},
            ),
        ],
    ),
]